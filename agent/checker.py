import json
import os
from typing import Callable, Optional

from google import genai
from google.genai import types
from tavily import TavilyClient

from agent.models import Claim, ClaimVerdict

_STRICTNESS_PROMPT = {
    "Lenient": (
        "Be lenient. Only mark a claim as False if it is clearly and directly contradicted "
        "by the sources. Prefer Inaccurate over False when unsure."
    ),
    "Standard": (
        "Apply standard journalistic fact-checking rigor. Mark False when clearly wrong, "
        "Inaccurate when partially wrong or misleading."
    ),
    "Strict": (
        "Be strict. Mark as Inaccurate even if the claim is only slightly off. "
        "Mark as False if any core part of the claim is contradicted."
    ),
}


def _search_evidence(claim_text: str, source_types: list[str]) -> list[dict]:
    """Query Tavily for evidence about a claim."""
    api_key = os.getenv("TAVILY_API_KEY", "").strip().rstrip(";").strip()
    tavily = TavilyClient(api_key=api_key)

    # Map user-friendly source type labels to Tavily topic values where applicable
    topic = "general"
    if source_types and "News" in source_types:
        topic = "news"

    result = tavily.search(
        query=claim_text,
        search_depth="advanced",
        topic=topic,
        max_results=5,
    )
    return result.get("results", [])


def check_claim(
    claim_text: str,
    claim_id: int,
    strictness: str = "Standard",
    source_types: Optional[list[str]] = None,
) -> Claim:
    """Fact-check a single claim using Tavily search + Gemini verdict."""
    if source_types is None:
        source_types = ["General"]

    sources = _search_evidence(claim_text, source_types)

    source_block = "\n\n".join(
        f"[{i+1}] URL: {s['url']}\n    Title: {s['title']}\n    Excerpt: {s['content'][:400]}"
        for i, s in enumerate(sources[:5])
    )

    strictness_instruction = _STRICTNESS_PROMPT.get(strictness, _STRICTNESS_PROMPT["Standard"])

    prompt = f"""You are a senior fact-checker. Evaluate the claim below against the provided search results.

CLAIM:
"{claim_text}"

SEARCH RESULTS:
{source_block}

STRICTNESS GUIDELINE:
{strictness_instruction}

Return a JSON object with exactly these keys:
- "status": one of "Verified", "Inaccurate", "False", "Unverifiable"
- "explanation": 1–2 sentence explanation of your verdict
- "corrected_fact": corrected version of the claim if status is Inaccurate or False, otherwise null
- "best_source_url": URL of the most relevant source, or null
- "best_source_title": Title of that source, or null
"""

    api_key = os.getenv("GOOGLE_API_KEY", "").strip().rstrip(";").strip()
    client = genai.Client(api_key=api_key)
    response = client.models.generate_content(
        model="gemini-2.5-flash-lite",
        contents=prompt,
        config=types.GenerateContentConfig(
            response_mime_type="application/json",
            response_schema=ClaimVerdict,
        ),
    )

    verdict = response.parsed

    return Claim(
        id=claim_id,
        text=claim_text,
        status=verdict.status if verdict else "Unverifiable",
        explanation=verdict.explanation if verdict else "No explanation provided.",
        source_url=verdict.best_source_url if verdict else None,
        source_title=verdict.best_source_title if verdict else None,
        corrected_fact=verdict.corrected_fact if verdict else None,
    )


def run_fact_check(
    claims: list[str],
    strictness: str = "Standard",
    source_types: Optional[list[str]] = None,
    progress_callback: Optional[Callable[[int, int, str], None]] = None,
) -> list[Claim]:
    """Run fact-checking for a list of claim strings, with optional progress reporting."""
    results: list[Claim] = []
    import time
    
    for i, claim_text in enumerate(claims):
        if progress_callback:
            progress_callback(i, len(claims), claim_text)
            
        # Retry logic for 429 Rate Limits
        for attempt in range(3):
            try:
                result = check_claim(claim_text, i + 1, strictness, source_types)
                results.append(result)
                break
            except Exception as e:
                if "429" in str(e) and attempt < 2:
                    time.sleep(15)  # Wait 15 seconds
                    continue
                raise e
    return results
