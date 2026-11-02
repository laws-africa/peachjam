import nest_asyncio
from django.conf import settings
from langfuse import Langfuse
from langfuse.span_filter import is_default_export_span
from openinference.instrumentation.openai_agents import OpenAIAgentsInstrumentor

PROMPT_CACHE_TTL_SECS = 30 if settings.DEBUG else 60

# Required for Langfuse to work properly in Django views which may already have an event loop running.
# See https://langfuse.com/integrations/frameworks/openai-agents
nest_asyncio.apply()

# Setup OpenAI Agents instrumentation for observability in Langfuse.
OpenAIAgentsInstrumentor().instrument()


def should_export_span(span):
    """Apply Langfuse's default filter without Elasticsearch instrumentation noise."""
    return is_default_export_span(span) and (
        span.instrumentation_scope is None
        or span.instrumentation_scope.name != "elasticsearch-api"
    )


# Langfuse uses environment variables to configure itself.
langfuse = Langfuse(should_export_span=should_export_span)
