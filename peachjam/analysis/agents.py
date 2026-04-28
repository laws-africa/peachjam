import logging

from agents import ReasoningItem, RunResult

log = logging.getLogger(__name__)


def log_agent_reasoning(result: RunResult):
    for item in result.new_items:
        if isinstance(item, ReasoningItem):
            for entry in item.raw_item.summary:
                log.debug("LLM reasoning: %s", entry.text)
