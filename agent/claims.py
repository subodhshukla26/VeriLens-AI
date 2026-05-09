import json
import os
import time

from google import genai
from google.genai import types
from agent.models import ClaimsExtraction


def extract_claims(text: str, num_claims: int = 10) -> list[str]:
    """Use Gemini to extract verifiable factual claims from document text."""
    api_key = os.getenv("GOOGLE_API_KEY", "").strip().rstrip(";").strip()
    client = genai.Client(api_key=api_key)

    prompt = f"""You are a professional fact-checker. Extract the {num_claims} most specific and verifiable \
factual claims from the text below.

Focus only on:
- Statistics and percentages
- Named dates and deadlines
- Financial figures and valuations
- Technical specifications
- Attributions to named individuals or organizations

Return a JSON object with a single key "claims" whose value is an array of claim strings.
Only include claims that can be checked against external public sources.

TEXT:
{text[:10000]}
"""

    # Retry logic for 429 Rate Limits
    for attempt in range(3):
        try:
            response = client.models.generate_content(
                model="gemini-2.5-flash-lite",
                contents=prompt,
                config=types.GenerateContentConfig(
                    response_mime_type="application/json",
                    response_schema=ClaimsExtraction,
                ),
            )
            
            if response.parsed and response.parsed.claims:
                return response.parsed.claims[:num_claims]
            break
        except Exception as e:
            if "429" in str(e) and attempt < 2:
                time.sleep(20)  # Wait 20 seconds
                continue
            raise e
    
    return []
