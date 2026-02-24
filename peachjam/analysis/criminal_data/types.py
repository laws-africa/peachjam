from typing import List, Optional

from pydantic import BaseModel, Field


class MentionedOffences(BaseModel):
    mentioned_offences: List[str]


class MatchedOffence(BaseModel):
    extracted_offence: str
    offence_id: Optional[int]


class MatchOffenceResult(BaseModel):
    mappings: List[MatchedOffence] = Field(default_factory=list)


class ExtractedSentence(BaseModel):
    offence_id: Optional[int] = None
    sentence_type: str
    duration_months: Optional[int] = None
    fine_amount: Optional[int] = None
    mandatory_minimum: Optional[bool] = None
    suspended: Optional[bool] = False


class SentenceExtractionResult(BaseModel):
    sentences: List[ExtractedSentence] = Field(default_factory=list)
