import logging
from abc import ABC, abstractmethod

from openai import OpenAI

log = logging.getLogger(__name__)


class BaseExtractor(ABC):
    """
    Common interface for all extraction services.
    """

    model = "gpt-5-mini"

    def __init__(self, judgment):
        self.judgment = judgment
        self.client = OpenAI()

    @abstractmethod
    def build_prompt(self) -> str:
        pass

    @abstractmethod
    def get_response_format(self):
        """
        The structured response that LLM will use
        """
        pass

    @abstractmethod
    def save(self, parsed_output):
        """
        Save the result
        """
        pass

    def run(self):
        """
        Call the LLM service
        """

        response = self.client.responses.parse(
            model=self.model,
            instructions=self.system_prompt(),
            input=self.build_prompt(),
            text_format=self.get_response_format(),
        )

        parsed = response.output_parsed
        return self.save(parsed)

    def system_prompt(self) -> str:
        return "You extract structured legal data from court judgments."
