import hashlib
import logging
import math

from django.conf import settings
from django.contrib.postgres.fields import ArrayField
from django.db import models
from django.db.models import Avg, F
from django.forms import model_to_dict
from pgvector.django import HnswIndex, MaxInnerProduct, VectorField

from peachjam.models import CoreDocument, Work
from peachjam_ml.embeddings import TEXT_INJECTION_SEPARATOR, get_text_embedding_batch
from peachjam_search.tasks import search_model_saved

# max-tokens is 512 for cohere embed model
CHUNK_SIZE = 256
MAX_CHUNK_LENGTH = 2048

log = logging.getLogger(__name__)


def normalize_vector(vec):
    # equivalent to numpy.linalg.norm(vec) to produce a unit-length vector using the L2 norm
    norm = math.sqrt(sum(x * x for x in vec))
    if norm == 0:
        return None
    return [x / norm for x in vec]


class DocumentEmbedding(models.Model):
    """Embedding data for a document, built from the embeddings of its various content chunks."""

    document = models.OneToOneField(
        "peachjam.CoreDocument", on_delete=models.CASCADE, related_name="embedding"
    )
    # md5 sum of the content when the embedding was created
    content_text_md5 = models.CharField(max_length=50, null=True, blank=True)
    # embedding of the text content
    text_embedding = VectorField(dimensions=1024, null=True, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        indexes = [
            HnswIndex(
                name="peachjam_ml_docembedding_emb_ix",
                fields=["text_embedding"],
                m=16,
                ef_construction=64,
                # ip == inner product == dot product == the "<#>" pgvector operator
                opclasses=["vector_ip_ops"],
            )
        ]

    def __str__(self):
        return f"DocumentEmbedding<#{self.pk} {self.document}>"

    def update_or_delete(self, content_text_md5):
        """Re-calculate all the chunk embeddings and the document-level embedding."""
        self.update_content_chunks()
        self.update_embedding()

        if not self.text_embedding:
            log.info(
                f"No content chunks for {self.document} or zero vectors, deleting {self}"
            )
            self.delete()
            return None

        self.content_text_md5 = content_text_md5
        self.save()

        log.info(f"Document embedding updated for {self.document}")

        return self

    def update_embedding(self):
        """Calculate the document-level embedding from the content chunks."""
        self.text_embedding = None

        qs = ContentChunk.objects.filter(document=self.document)
        if (
            self.document.content_html
            and self.document.content_html_is_akn
            and self.document.toc_json
        ):
            # The document is AKN with a TOC and has been chunked recursively based on the TOC.
            # This means that, for example, a chapter has been chunked and embeddings calculated, and then
            # all the children of the chapter have been chunked and embeddings calculated too.
            #
            # For example, we have multiple chunks and embeddings for:
            #   chp_1
            #   chp_1__sec_1
            #   chp_2__sec_2
            #
            # If we take the average of all embeddings, it means that we're double-counting the nested children
            # of top-level TOC containers since the text of chp_1__sec_1 is in chp_1 and chp_1__sec_1.
            #
            # So, instead we only get the embeddings for the top-level TOC containers and take the average of those.
            top_level_ids = [
                item["id"] or item["type"] for item in self.document.toc_json
            ]
            qs = qs.filter(portion__in=top_level_ids)

        # get the average directly in the DB (faster) and then normalise it
        avg = qs.aggregate(avg=Avg("text_embedding"))["avg"]
        # if numpy is installed, this will be ndarray, otherwise it will be a list
        if avg is not None and len(avg):
            avg = normalize_vector(avg)

        # guard against zero vectors
        if avg:
            self.text_embedding = normalize_vector(avg)

    def update_content_chunks(self):
        ContentChunk.objects.filter(document=self.document).delete()
        # build the chunks and save them
        ContentChunk.objects.bulk_create(
            ContentChunk.make_document_chunks(self.document)
        )

    @classmethod
    def refresh_for_document(cls, document):
        """Refresh content chunks and document-level embedding for a document, if they don't exist or the document
        text has changed.

        This is the primary way of creating or updating embeddings. When refreshing, existing embeddings are deleted.
        If this document shouldn't have embeddings, none are created.
        """
        if not settings.PEACHJAM["SEARCH_SEMANTIC"]:
            return

        text_md5 = None
        text = document.get_content_as_text()
        if text:
            text_md5 = hashlib.md5(text.encode()).hexdigest()

        doc_embedding = cls.objects.filter(document=document).first()
        if text and doc_embedding and doc_embedding.content_text_md5 == text_md5:
            # nothing has changed
            return

        # clear out old data - it either shouldn't exist, or it is stale
        ContentChunk.objects.filter(document=document).delete()

        if (
            not text
            or document.doc_type
            in settings.PEACHJAM["SEARCH_SEMANTIC_EXCLUDE_DOCTYPES"]
            or not document.is_most_recent()
        ):
            log.info(
                f"Document is empty or excluded, clearing embeddings (if any): {document}"
            )
            if doc_embedding:
                doc_embedding.delete()
            return

        # ensure there's a doc_embedding object (avoids race conditions)
        doc_embedding = (
            doc_embedding
            or DocumentEmbedding.objects.get_or_create(document=document)[0]
        )
        doc_embedding = doc_embedding.update_or_delete(text_md5)

        # ensure this document is re-indexed for search
        search_model_saved(document.__class__._meta.label, document.pk, schedule=60)

        return doc_embedding

    @classmethod
    def get_average_embedding(cls, pks):
        """Get the average embedding for a set of documents."""

        avg = (
            DocumentEmbedding.objects.filter(document__in=pks)
            .aggregate(avg=Avg("text_embedding"))
            .get("avg")
        )
        if avg is not None and len(avg):
            avg = normalize_vector(avg)

        return avg

    @classmethod
    def get_similar_documents(cls, doc_ids, threshold=0.8, n_similar=10):
        weight_similarity = 0.9
        weight_authority = 0.1
        top_k = 100
        avg_embedding = cls.get_average_embedding(doc_ids)
        most_recent_docs = (
            CoreDocument.objects.all().latest_expression().values_list("pk", flat=True)
        )

        similar_docs = (
            DocumentEmbedding.objects.filter(document__pk__in=most_recent_docs)
            .exclude(document__work__in=Work.objects.filter(documents__in=doc_ids))
            .exclude(text_embedding__isnull=True)
            .annotate(
                similarity=MaxInnerProduct("text_embedding", avg_embedding) * -1,
                title=F("document__title"),
                expression_frbr_uri=F("document__expression_frbr_uri"),
                authority_score=F("document__work__authority_score"),
            )
            .filter(similarity__gt=threshold)
            .values(
                "document_id",
                "title",
                "expression_frbr_uri",
                "similarity",
                "authority_score",
            )
            .order_by("-similarity")
        )[:top_k]

        # re-rank based on a weighted average of similarity and authority score, and keep the top 10
        similar_docs = sorted(
            similar_docs,
            key=lambda x: (
                x["similarity"] * weight_similarity
                + x["authority_score"] * weight_authority
            ),
            reverse=True,
        )[:n_similar]

        return similar_docs


class ContentChunk(models.Model):
    """A chunk of content that is indexed for semantic search. This has slightly different semantics for different
    types of content:

    * text: plain text chunks, usually for plain HTML documents
    * page: a chunk of a page of text, from a PDF
    * provision: a chunk of a provision from AKN legislation

    Additionally, a chunk of text to be embedded has a maximum length, so a long text may be split into multiple chunks.
    This in indicated by n_chunks (total number for this piece of text) and chunk_n (the 1-based index).

    This structure is indexed directly into Elasticsearch as a nested object.
    """

    document = models.ForeignKey("peachjam.CoreDocument", on_delete=models.CASCADE)
    # "text", "page" or "provision"
    type = models.CharField(max_length=20)
    text = models.TextField()
    # page number (type=page), eid (type=provision), None (type=text)
    portion = models.CharField(max_length=4096, null=True, blank=True)
    chunk_n = models.IntegerField(default=0)
    n_chunks = models.IntegerField(default=1)
    # for provisions - mimics the format used by SearchableDocument.prepare_provisions
    provision_type = models.CharField(max_length=1024, null=True, blank=True)
    title = models.CharField(max_length=1024, null=True, blank=True)
    parent_titles = ArrayField(models.CharField(max_length=1024), null=True, blank=True)
    parent_ids = ArrayField(models.CharField(max_length=1024), null=True, blank=True)
    # embedding of the text field
    text_embedding = VectorField(dimensions=1024)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        indexes = [
            HnswIndex(
                name="peachjam_ml_cchunk_emb_ix",
                fields=["text_embedding"],
                m=16,
                ef_construction=64,
                # ip == inner product == dot product == the "<#>" pgvector operator
                opclasses=["vector_ip_ops"],
            )
        ]

    def clone(self):
        # walk over all the fields and clone them
        fields = {
            f.name: getattr(self, f.name)
            for f in self._meta.fields
            if f.name not in ["id"]
        }
        return ContentChunk(**fields)

    def as_dict_for_es(self):
        """Return a dict for ElasticSearch based on peachjam_search.documents."""
        return model_to_dict(
            self,
            fields=[
                "type",
                "text",
                "portion",
                "chunk_n",
                "n_chunks",
                "provision_type",
                "title",
                "parent_titles",
                "parent_ids",
                "text_embedding",
            ],
        )

    def __str__(self):
        return f'ContentChunk<#{self.pk} {self.document}: "{self.text}">'

    @classmethod
    def make_document_chunks(cls, document):
        from peachjam_search.documents import SearchableDocument

        chunks = []
        if document.content_html and document.content_html_is_akn and document.toc_json:
            # AKN provisions
            provisions = SearchableDocument().prepare_provisions(document)
            for provision in provisions:
                text = provision["body"]
                # inject the titles at the top of the text to add extra context
                titles = [
                    t for t in provision["parent_titles"] + [provision["title"]] if t
                ]
                if titles:
                    text = "\n".join(titles) + "\n" + TEXT_INJECTION_SEPARATOR + text

                for chunk in cls.split_chunks(
                    [ContentChunk(document=document, type="provision", text=text)]
                ):
                    chunk.portion = provision["id"]
                    chunk.provision_type = provision["type"]
                    chunk.title = provision["title"]
                    chunk.parent_titles = provision["parent_titles"]
                    chunk.parent_ids = provision["parent_ids"]
                    chunks.append(chunk)

        else:
            # plain html or PDF text
            text = (document.get_content_as_text() or "").strip()
            if text:
                if "\f" in text:
                    # pages
                    chunks.extend(
                        cls.split_chunks(cls.make_page_chunks(document, text))
                    )
                else:
                    chunks.extend(
                        cls.split_chunks(
                            [ContentChunk(document=document, type="text", text=text)]
                        )
                    )

        # TODO: can we re-use existing embeddings if we already have them, to save $$$?
        log.info(f"Getting embeddings for {len(chunks)} chunks for {document}")
        embeddings = get_text_embedding_batch([c.text for c in chunks])
        for chunk, embedding in zip(chunks, embeddings):
            chunk.text_embedding = embedding
        log.info("Got embeddings")

        return chunks

    @classmethod
    def make_page_chunks(cls, document, text):
        """Split text on page boundaries '\f' and return chunks."""
        # pages
        return [
            cls(document=document, type="page", text=p, portion=i + 1)
            for i, p in enumerate(text.split("\f"))
        ]

    @classmethod
    def split_chunks(
        cls, chunks, chunk_size=CHUNK_SIZE, max_chunk_length=MAX_CHUNK_LENGTH
    ):
        """Split chunks that are too long."""
        from llama_index.core.node_parser.text.sentence import SentenceSplitter

        splitter = SentenceSplitter.from_defaults(
            chunk_size=chunk_size, chunk_overlap=int(chunk_size * 0.2)
        )
        new_chunks = []

        for chunk in chunks:
            chunk_splits = [
                c[:max_chunk_length] for c in splitter.split_text(chunk.text)
            ]
            for i, text in enumerate(chunk_splits):
                chunk = chunk.clone()
                chunk.chunk_n = i
                chunk.n_chunks = len(chunk_splits)
                chunk.text = text
                new_chunks.append(chunk)

        return new_chunks
