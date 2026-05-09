# VeriLens AI – Fact-Check Agent

VeriLens AI is an AI-powered fact-checking dashboard that extracts verifiable claims from PDF documents and cross-references them against live web sources using Google Gemini and Tavily Search.

## Features

- **PDF Text Extraction**: Uses PyMuPDF to process uploaded documents.
- **AI-Driven Claim Identification**: Extracts specific, verifiable factual claims (statistics, dates, figures).
- **Live Evidence Retrieval**: Queries the live web via Tavily Search for real-time verification.
- **Structured Verdicts**: Provides "Verified", "Inaccurate", "False", or "Unverifiable" status for every claim.
- **Corrected Facts**: Suggests corrections for inaccurate or false claims.
- **Source Transparency**: Links directly to the most relevant sources found.
- **Exportable Reports**: Download the full audit as a CSV file.

## Tech Stack

- **Frontend**: Streamlit
- **LLM**: Google Gemini (via `google-genai` SDK)
- **Search API**: Tavily Search
- **PDF Processing**: PyMuPDF (fitz)

## Setup

1. Clone the repository:
   ```bash
   git clone https://github.com/subodhshukla26/VeriLens-AI.git
   cd VeriLens-AI
   ```

2. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```

3. Configure environment variables in a `.env` file:
   ```env
   GOOGLE_API_KEY=your_gemini_api_key
   TAVILY_API_KEY=your_tavily_api_key
   ```

4. Run the application:
   ```bash
   streamlit run app.py
   ```

## License

MIT
