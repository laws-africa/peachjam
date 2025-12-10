"""
This runs the ASGI application using Uvicorn with auto-reload enabled for development purposes. This allows us to
test true asynchronous capabilities during development. In particular, streaming LLM responses for peachjam_ml's
chat features.
"""

import os

import uvicorn

if __name__ == "__main__":
    uvicorn.run(
        "peachjam.asgi:application",
        reload=True,
        port=int(os.environ.get("UVICORN_PORT", 8080)),
    )
