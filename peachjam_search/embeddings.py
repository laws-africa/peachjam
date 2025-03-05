from copy import copy

from django.core.cache import cache
from llama_index.core.node_parser.text.sentence import SentenceSplitter

# max-tokens is 512 for cohere embed model
CHUNK_SIZE = 256
MAX_CHUNK_LENGTH = 2048


def make_content_chunks(text, chunk_size=CHUNK_SIZE, max_chunk_length=MAX_CHUNK_LENGTH):
    """Split text (which could be plain text or pages separated with \f) into chunks suitable for embedding."""
    splitter = SentenceSplitter.from_defaults(
        chunk_size=chunk_size, chunk_overlap=int(chunk_size * 0.2)
    )

    if "\f" in text:
        portions = [
            {
                "type": "page",
                "portion": i + 1,
                "text": p,
            }
            for i, p in enumerate(text.split("\f"))
        ]
    else:
        portions = [
            {
                "type": "text",
                "text": text,
            }
        ]

    chunks = []
    for portion in portions:
        portion_chunks = [
            c[:max_chunk_length] for c in splitter.split_text(portion["text"])
        ]
        for i, chunk in enumerate(portion_chunks):
            portion = copy(portion)
            portion["chunk_n"] = i
            portion["n_chunks"] = len(portion_chunks)
            portion["text"] = chunk
            chunks.append(portion)

    return chunks


def add_chunk_embeddings(chunks):
    """Add text embeddings to each chunk."""
    bedrock_embedding = get_bedrock_embedding()
    embeddings = bedrock_embedding.get_text_embedding_batch([c["text"] for c in chunks])
    for chunk, embedding in zip(chunks, embeddings):
        chunk["text_embedding"] = embedding


def get_query_embedding(query):
    cache_key = "query-embedding::" + query
    embedding = cache.get(cache_key)

    if not embedding:
        embedding = get_bedrock_embedding().get_query_embedding(query)
        cache.set(cache_key, embedding, timeout=None)

    return embedding


_bedrock_embedding = None


def get_bedrock_embedding():
    global _bedrock_embedding
    if _bedrock_embedding is None:
        from llama_index.embeddings.bedrock import BedrockEmbedding

        _bedrock_embedding = BedrockEmbedding(
            model_name="cohere.embed-multilingual-v3",
            # cohere can handle up to 96 texts to embed concurrently per call
            embed_batch_size=96,
        )
    return _bedrock_embedding
