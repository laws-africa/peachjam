import dataclasses
import json
from copy import copy
from typing import List, Optional, Union

import boto3
from django.core.cache import cache

# max-tokens is 512 for cohere embed model
CHUNK_SIZE = 256
MAX_CHUNK_LENGTH = 2048
EMBEDDING_BATCH_SIZE = 96
MODEL_NAME = "cohere.embed-multilingual-v3"

# sometimes we want to inject extra text before the real text so that extra content is included in the embedding.
# we use this separator so we can strip the extra text when showing it to the user
TEXT_INJECTION_SEPARATOR = "\n-<>-\n\n"


@dataclasses.dataclass
class ContentChunk:
    """A chunk of content that is indexed for semantic search. This has slightly different semantics for different
    types of content:

    * text: plain text chunks, usually for plain HTML documents
    * page: a chunk of a page of text, from a PDF
    * provision: a chunk of a provision from AKN legislation

    Additionally, a chunk of text to be embedded has a maximum length, so a long text may be split into multiple chunks.
    This in indicated by n_chunks (total number for this piece of text) and chunk_n (the 1-based index).

    This structure is indexed directly into Elasticsearch as a nested object.
    """

    # "text", "page" or "provision"
    type: str
    text: str
    # the portion id (page number or eid)
    portion: Optional[Union[str, int]] = None
    chunk_n: int = 0
    n_chunks: int = 1
    # for provisions - mimics the format used by SearchableDocument.prepare_provisions
    provision_type: Optional[str] = None
    title: Optional[str] = None
    parent_titles: Optional[List[str]] = None
    parent_ids: Optional[List[str]] = None
    # the actual embedding
    text_embedding: List[float] = None

    def asdict(self):
        return dataclasses.asdict(self)


def make_page_chunks(text) -> List[ContentChunk]:
    """Split text on page boundaries '\f' and return chunks."""
    # pages
    return [
        ContentChunk("page", p, portion=i + 1) for i, p in enumerate(text.split("\f"))
    ]


def split_chunks(
    chunks: list[ContentChunk], chunk_size=CHUNK_SIZE, max_chunk_length=MAX_CHUNK_LENGTH
):
    """Split chunks that are too long."""
    from llama_index.core.node_parser.text.sentence import SentenceSplitter

    splitter = SentenceSplitter.from_defaults(
        chunk_size=chunk_size, chunk_overlap=int(chunk_size * 0.2)
    )
    new_chunks = []

    for chunk in chunks:
        chunk_splits = [c[:max_chunk_length] for c in splitter.split_text(chunk.text)]
        for i, text in enumerate(chunk_splits):
            chunk = copy(chunk)
            chunk.chunk_n = i
            chunk.n_chunks = len(chunk_splits)
            chunk.text = text
            new_chunks.append(chunk)

    return new_chunks


def add_chunk_embeddings(chunks: List[ContentChunk]):
    """Add text embeddings to each chunk."""
    embeddings = get_text_embedding_batch([c.text for c in chunks])
    for chunk, embedding in zip(chunks, embeddings):
        chunk.text_embedding = embedding


def get_text_embedding_batch(texts):
    """Return an array of embeddings for the given texts."""
    embeddings = []

    # batch texts
    for i in range(0, len(texts), EMBEDDING_BATCH_SIZE):
        batch = texts[i : i + EMBEDDING_BATCH_SIZE]
        embeddings.extend(
            call_bedrock_model(
                {
                    "input_type": "search_document",
                    "texts": [t[:2048] for t in batch],
                }
            )["embeddings"]
        )

    return embeddings


def get_query_embedding(query):
    """Return a single embedding array for a query string."""
    cache_key = "query-embedding::" + query
    embedding = cache.get(cache_key)

    if not embedding:
        embedding = call_bedrock_model(
            {
                "input_type": "search_query",
                "texts": [query[:2048]],
            }
        )["embeddings"][0]

        cache.set(cache_key, embedding, timeout=None)

    return embedding


def call_bedrock_model(request):
    response = get_bedrock_client().invoke_model(
        body=json.dumps(request),
        modelId=MODEL_NAME,
        accept="application/json",
        contentType="application/json",
    )
    return json.loads(response.get("body").read().decode("utf-8"))


_bedrock_client = None


def get_bedrock_client():
    global _bedrock_client

    if _bedrock_client is None:
        _bedrock_client = boto3.Session().client("bedrock-runtime")
    return _bedrock_client
