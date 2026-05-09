from pydantic import BaseModel
from typing import Optional, Literal


class Claim(BaseModel):
    id: int
    text: str
    status: Literal["Verified", "Inaccurate", "False", "Unverifiable"]
    explanation: str
    source_url: Optional[str] = None
    source_title: Optional[str] = None
    corrected_fact: Optional[str] = None


class ClaimVerdict(BaseModel):
    status: Literal["Verified", "Inaccurate", "False", "Unverifiable"]
    explanation: str
    corrected_fact: Optional[str] = None
    best_source_url: Optional[str] = None
    best_source_title: Optional[str] = None


class ClaimsExtraction(BaseModel):
    claims: list[str]
