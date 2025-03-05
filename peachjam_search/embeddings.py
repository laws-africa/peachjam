import json
from copy import copy

import boto3
from django.core.cache import cache

# max-tokens is 512 for cohere embed model
CHUNK_SIZE = 256
MAX_CHUNK_LENGTH = 2048
EMBEDDING_BATCH_SIZE = 96
MODEL_NAME = "cohere.embed-multilingual-v3"


def make_content_chunks(text, chunk_size=CHUNK_SIZE, max_chunk_length=MAX_CHUNK_LENGTH):
    """Split text (which could be plain text or pages separated with \f) into chunks suitable for embedding."""
    from llama_index.core.node_parser.text.sentence import SentenceSplitter

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
    embeddings = get_text_embedding_batch([c["text"] for c in chunks])
    for chunk, embedding in zip(chunks, embeddings):
        chunk["text_embedding"] = embedding


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
