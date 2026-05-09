"""
VeriLens AI – Fact-Check Agent
Streamlit dashboard for PDF claim verification.
"""

import io
import os
import time

import pandas as pd
import streamlit as st
from dotenv import load_dotenv

from agent.checker import run_fact_check
from agent.claims import extract_claims
from agent.extractor import extract_text_from_pdf
from agent.models import Claim

# ── Environment ──────────────────────────────────────────────────────────────
load_dotenv()

# ── Page config ───────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="VeriLens AI – Fact-Check Agent",
    page_icon="🔍",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ── Custom CSS ────────────────────────────────────────────────────────────────
st.markdown(
    """
<style>
/* ---------- Global ---------- */
html, body, [class*="css"] { font-family: "Inter", sans-serif; }

/* ---------- Sidebar ---------- */
[data-testid="stSidebar"] {
    background: #1e293b;
}
[data-testid="stSidebar"] * { color: #e2e8f0 !important; }
[data-testid="stSidebar"] .stButton > button {
    width: 100%;
    background: #4f46e5;
    color: #ffffff !important;
    border: none;
    border-radius: 8px;
    font-weight: 600;
    font-size: 1rem;
    padding: 0.6rem 0;
    margin-top: 0.5rem;
    transition: background 0.2s;
}
[data-testid="stSidebar"] .stButton > button:hover {
    background: #4338ca;
}

/* ---------- Metric cards ---------- */
[data-testid="metric-container"] {
    background: #ffffff;
    border: 1px solid #e2e8f0;
    border-radius: 12px;
    padding: 1rem 1.25rem;
    box-shadow: 0 1px 3px rgba(0,0,0,.06);
}
[data-testid="stMetricLabel"]  { font-size: 0.8rem; color: #64748b !important; font-weight: 600; text-transform: uppercase; letter-spacing: .05em; }
[data-testid="stMetricValue"]  { font-size: 2rem; font-weight: 700; }

/* ---------- Status badges ---------- */
.badge {
    display: inline-block;
    padding: 3px 12px;
    border-radius: 999px;
    font-size: 0.78rem;
    font-weight: 700;
    letter-spacing: .04em;
    text-transform: uppercase;
}
.badge-verified    { background: #dcfce7; color: #166534; }
.badge-inaccurate  { background: #fef9c3; color: #854d0e; }
.badge-false       { background: #fee2e2; color: #991b1b; }
.badge-unverifiable{ background: #f1f5f9; color: #475569; }

/* ---------- Claim cards (expanders) ---------- */
[data-testid="stExpander"] {
    background: #ffffff;
    border: 1px solid #e2e8f0 !important;
    border-radius: 10px;
    margin-bottom: 0.5rem;
    box-shadow: 0 1px 2px rgba(0,0,0,.04);
}
[data-testid="stExpander"] summary {
    font-weight: 600;
    font-size: 0.92rem;
}

/* ---------- Download button ---------- */
.stDownloadButton > button {
    background: #4f46e5;
    color: #fff !important;
    border: none;
    border-radius: 8px;
    font-weight: 600;
    padding: 0.45rem 1.2rem;
    transition: background 0.2s;
}
.stDownloadButton > button:hover { background: #4338ca; }

/* ---------- Info banner ---------- */
.info-banner {
    background: #eff6ff;
    border-left: 4px solid #4f46e5;
    border-radius: 6px;
    padding: 0.75rem 1rem;
    font-size: 0.88rem;
    color: #1e3a8a;
    margin-bottom: 1rem;
}

/* ---------- Welcome card ---------- */
.welcome-card {
    background: #ffffff;
    border: 1px solid #e2e8f0;
    border-radius: 14px;
    padding: 2.5rem 2rem;
    text-align: center;
    margin-top: 2rem;
    box-shadow: 0 2px 8px rgba(0,0,0,.06);
}
.welcome-card h2 { color: #1e293b; margin-bottom: 0.5rem; }
.welcome-card p  { color: #64748b; font-size: 0.95rem; }

/* ---------- Source link ---------- */
.src-link { font-size: 0.82rem; color: #4f46e5; text-decoration: none; }
.src-link:hover { text-decoration: underline; }

/* ---------- Corrected fact box ---------- */
.correction-box {
    background: #fff7ed;
    border-left: 3px solid #f59e0b;
    border-radius: 5px;
    padding: 0.5rem 0.85rem;
    font-size: 0.88rem;
    color: #78350f;
    margin-top: 0.5rem;
}
</style>
""",
    unsafe_allow_html=True,
)

# ── Session-state defaults ────────────────────────────────────────────────────
for key, default in {
    "results": None,
    "extracted_text": None,
    "claims_list": None,
    "run_complete": False,
}.items():
    if key not in st.session_state:
        st.session_state[key] = default

# ── Helpers ───────────────────────────────────────────────────────────────────
STATUS_BADGE = {
    "Verified":      '<span class="badge badge-verified">✓ Verified</span>',
    "Inaccurate":    '<span class="badge badge-inaccurate">⚠ Inaccurate</span>',
    "False":         '<span class="badge badge-false">✕ False</span>',
    "Unverifiable":  '<span class="badge badge-unverifiable">? Unverifiable</span>',
}

STATUS_EMOJI = {
    "Verified": "✅",
    "Inaccurate": "⚠️",
    "False": "❌",
    "Unverifiable": "❓",
}

STATUS_COLOR_METRIC = {
    "Verified":     "#22c55e",
    "Inaccurate":   "#f59e0b",
    "False":        "#ef4444",
    "Unverifiable": "#94a3b8",
}


def _claims_to_df(claims: list[Claim]) -> pd.DataFrame:
    rows = []
    for c in claims:
        rows.append(
            {
                "#": c.id,
                "Claim": c.text,
                "Status": c.status,
                "Explanation": c.explanation,
                "Source": c.source_title or "—",
                "Source URL": c.source_url or "",
                "Corrected Fact": c.corrected_fact or "",
            }
        )
    return pd.DataFrame(rows)


def _to_csv(df: pd.DataFrame) -> bytes:
    return df.to_csv(index=False).encode("utf-8")


# ── Sidebar ───────────────────────────────────────────────────────────────────
with st.sidebar:
    st.markdown("## 🔍 VeriLens AI")
    st.caption("Fact-Check Agent")
    st.divider()

    uploaded_file = st.file_uploader(
        "Upload PDF",
        type=["pdf"],
        help="Upload the document whose claims you want to verify.",
    )

    st.markdown("### ⚙️ Settings")

    num_claims = st.slider(
        "Number of claims to check",
        min_value=3,
        max_value=25,
        value=10,
        step=1,
        help="How many factual claims to extract and verify from the document.",
    )

    strictness = st.selectbox(
        "Strictness level",
        options=["Lenient", "Standard", "Strict"],
        index=1,
        help=(
            "Lenient – only flag clearly wrong claims.  \n"
            "Standard – balanced journalistic rigor.  \n"
            "Strict – flag even minor inaccuracies."
        ),
    )

    source_types = st.multiselect(
        "Source type preference",
        options=["General", "News", "Academic", "Government"],
        default=["General"],
        help="Preferred types of sources to consult when verifying claims.",
    )

    st.divider()
    run_clicked = st.button("🚀 Run Fact Check", use_container_width=True)

    st.divider()
    st.markdown(
        "<small style='color:#94a3b8;'>Checks stats, dates, financial figures, "
        "and technical claims against live web sources.</small>",
        unsafe_allow_html=True,
    )

# ── Main area header ──────────────────────────────────────────────────────────
st.title("🔍 Fact-Check Agent")
st.markdown(
    "Upload a PDF and verify its claims against **live web sources** in seconds."
)
st.markdown(
    '<div class="info-banner">🛡️ This tool checks <b>statistics</b>, <b>dates</b>, '
    "<b>financial numbers</b>, and <b>technical claims</b> using AI-powered search and reasoning.</div>",
    unsafe_allow_html=True,
)

# ── Run pipeline ──────────────────────────────────────────────────────────────
if run_clicked:
    if uploaded_file is None:
        st.warning("⬅️  Please upload a PDF first using the sidebar.")
        st.stop()

    # Reset previous results
    st.session_state.results = None
    st.session_state.run_complete = False

    pdf_bytes = uploaded_file.read()
    progress_placeholder = st.empty()

    with progress_placeholder.container():
        # ── Step 1: Extract text ──────────────────────────────────────────
        status_msg = st.status("⏳ Analyzing document…", expanded=True)
        with status_msg:
            st.write("📄 Extracting text from PDF…")
            bar = st.progress(0)
            time.sleep(0.3)

            try:
                extracted = extract_text_from_pdf(pdf_bytes)
            except Exception as e:
                st.error(f"Failed to read PDF: {e}")
                st.stop()

            if not extracted.strip():
                st.error("No readable text found in the PDF. Is it a scanned image?")
                st.stop()

            st.session_state.extracted_text = extracted
            bar.progress(15)

            # ── Step 2: Extract claims ────────────────────────────────────
            st.write("🔎 Identifying verifiable claims…")
            try:
                claims_list = extract_claims(extracted, num_claims)
            except Exception as e:
                st.error(f"Claim extraction failed: {e}")
                st.stop()

            if not claims_list:
                st.warning("No verifiable claims were found in the document.")
                st.stop()

            st.session_state.claims_list = claims_list
            bar.progress(30)

            # ── Step 3: Fact-check each claim ─────────────────────────────
            st.write(f"🌐 Checking {len(claims_list)} claims against live sources…")

            checked: list[Claim] = []
            step_size = 70 / max(len(claims_list), 1)

            def _progress_cb(idx: int, total: int, claim_text: str):
                short = claim_text[:80] + ("…" if len(claim_text) > 80 else "")
                st.write(f"  → [{idx + 1}/{total}] {short}")
                bar.progress(int(30 + idx * step_size))

            try:
                checked = run_fact_check(
                    claims_list,
                    strictness=strictness,
                    source_types=source_types,
                    progress_callback=_progress_cb,
                )
            except Exception as e:
                st.error(f"Fact-checking failed: {e}")
                st.stop()

            bar.progress(100)
            st.write("✅ Analysis complete!")
            status_msg.update(label="✅ Fact-check complete!", state="complete")

        st.session_state.results = checked
        st.session_state.run_complete = True

    progress_placeholder.empty()

# ── Results area ──────────────────────────────────────────────────────────────
results: list[Claim] | None = st.session_state.results

if results is None and not st.session_state.run_complete:
    # Welcome state
    st.markdown(
        """
        <div class="welcome-card">
            <h2>Welcome to VeriLens AI</h2>
            <p>Upload a PDF document using the sidebar, configure your settings,<br>
            then click <b>Run Fact Check</b> to get a full claim-by-claim audit report.</p>
            <br>
            <p style="font-size:0.85rem; color:#94a3b8;">
                Powered by Google Gemini · Tavily Search · PyMuPDF
            </p>
        </div>
        """,
        unsafe_allow_html=True,
    )
    st.stop()

if not results:
    st.info("No claims were found or verified. Try uploading a different document.")
    st.stop()

# ── Summary metrics ───────────────────────────────────────────────────────────
total       = len(results)
verified    = sum(1 for c in results if c.status == "Verified")
inaccurate  = sum(1 for c in results if c.status == "Inaccurate")
false_count = sum(1 for c in results if c.status == "False")
unverifiable= sum(1 for c in results if c.status == "Unverifiable")

st.markdown("### 📊 Summary")
col1, col2, col3, col4, col5 = st.columns(5)
col1.metric("Total Claims",   total)
col2.metric("✅ Verified",     verified,     delta=None)
col3.metric("⚠️ Inaccurate",  inaccurate,   delta=None)
col4.metric("❌ False",        false_count,  delta=None)
col5.metric("❓ Unverifiable", unverifiable, delta=None)

st.divider()

# ── Filter + Download row ─────────────────────────────────────────────────────
filter_col, dl_col = st.columns([3, 1])

with filter_col:
    status_filter = st.multiselect(
        "Filter by status",
        options=["Verified", "Inaccurate", "False", "Unverifiable"],
        default=["Verified", "Inaccurate", "False", "Unverifiable"],
        label_visibility="collapsed",
    )

df = _claims_to_df(results)

with dl_col:
    st.download_button(
        label="⬇️  Download CSV",
        data=_to_csv(df),
        file_name="verilens_fact_check_report.csv",
        mime="text/csv",
        use_container_width=True,
    )

# ── Summary table ─────────────────────────────────────────────────────────────
st.markdown("### 📋 Results Table")

filtered_df = df[df["Status"].isin(status_filter)].copy()

# Color-map the Status column using Styler
def _color_status(val: str) -> str:
    colors = {
        "Verified":     "background-color:#dcfce7; color:#166534; font-weight:600;",
        "Inaccurate":   "background-color:#fef9c3; color:#854d0e; font-weight:600;",
        "False":        "background-color:#fee2e2; color:#991b1b; font-weight:600;",
        "Unverifiable": "background-color:#f1f5f9; color:#475569; font-weight:600;",
    }
    return colors.get(val, "")


display_df = filtered_df[["#", "Claim", "Status", "Explanation", "Source"]].copy()
styled = display_df.style.map(_color_status, subset=["Status"])

st.dataframe(styled, use_container_width=True, hide_index=True)

st.divider()

# ── Claim-by-claim expanders ──────────────────────────────────────────────────
st.markdown("### 🔬 Claim-by-Claim Evidence")

filtered_results = [c for c in results if c.status in status_filter]

if not filtered_results:
    st.info("No claims match the selected filter.")
else:
    for claim in filtered_results:
        badge_html = STATUS_BADGE.get(claim.status, claim.status)
        emoji = STATUS_EMOJI.get(claim.status, "")
        label = f"{emoji} Claim #{claim.id}  —  {claim.text[:100]}{'…' if len(claim.text) > 100 else ''}"

        with st.expander(label):
            left, right = st.columns([3, 1])

            with left:
                st.markdown("**Full Claim**")
                st.markdown(f"> {claim.text}")

                st.markdown("**Verdict**")
                st.markdown(badge_html, unsafe_allow_html=True)

                st.markdown("**Explanation**")
                st.markdown(claim.explanation)

                if claim.corrected_fact:
                    st.markdown(
                        f'<div class="correction-box">📝 <b>Corrected fact:</b> {claim.corrected_fact}</div>',
                        unsafe_allow_html=True,
                    )

            with right:
                st.markdown("**Source**")
                if claim.source_url:
                    title = claim.source_title or claim.source_url
                    st.markdown(
                        f'<a class="src-link" href="{claim.source_url}" target="_blank">'
                        f"🔗 {title}</a>",
                        unsafe_allow_html=True,
                    )
                    st.link_button("Open Source ↗", claim.source_url)
                else:
                    st.caption("No source available")

# ── Footer ────────────────────────────────────────────────────────────────────
st.divider()
st.markdown(
    "<small style='color:#94a3b8;'>VeriLens AI · Built with Streamlit, Gemini & Tavily</small>",
    unsafe_allow_html=True,
)
