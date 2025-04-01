import json

import boto3
from django.core.cache import cache

EMBEDDING_BATCH_SIZE = 96
MODEL_NAME = "cohere.embed-multilingual-v3"

# sometimes we want to inject extra text before the real text so that extra content is included in the embedding.
# we use this separator so we can strip the extra text when showing it to the user
TEXT_INJECTION_SEPARATOR = "\n-<>-\n\n"


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
