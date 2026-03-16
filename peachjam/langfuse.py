import nest_asyncio
from django.conf import settings
from langfuse import Langfuse
from openinference.instrumentation.openai_agents import OpenAIAgentsInstrumentor

PROMPT_CACHE_TTL_SECS = 30 if settings.DEBUG else 60

# Required for Langfuse to work properly in Django views which may already have an event loop running.
# See https://langfuse.com/integrations/frameworks/openai-agents
nest_asyncio.apply()

# Setup OpenAI Agents instrumentation for observability in Langfuse.
OpenAIAgentsInstrumentor().instrument()

# Langfuse uses environment variables to configure itself.
# We block elasticsearch-api instrumentation which comes through from the opentelemetry data.
langfuse = Langfuse(blocked_instrumentation_scopes=["elasticsearch-api"])
