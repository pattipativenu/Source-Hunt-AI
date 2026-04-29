"""
Hunt AI — Reranker Playground Dashboard

Run locally:
    cd /Users/admin/Documents/hunt.ai
    pip install streamlit
    streamlit run scripts/dashboard/app.py

What this tests:
  - Side-by-side reranker comparison: Cohere vs BGE vs Jina vs MedCPT
  - Gemini generation comparison: Flash vs Pro on the same reranked chunks
  - OpenEvidence 10-query benchmark (easy / medium / hard)
  - Ranking quality on Indian medical queries (your golden test set)
  - Latency for each model
"""

from __future__ import annotations

import os
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

# Allow imports from project root
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

import streamlit as st

from scripts.dashboard.reranker_compare import (
    RerankerOutput,
    rerank_bge,
    rerank_cohere,
    rerank_jina,
    rerank_medcpt,
)
from scripts.dashboard.openevidence_benchmark import (
    BENCHMARK_QUERIES,
    BenchmarkQuery,
    get_queries_by_difficulty,
)

# ── Page config ───────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="Hunt AI · Reranker Playground",
    page_icon="🩺",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ── Session state ─────────────────────────────────────────────────────────────
if "hf_model_cache" not in st.session_state:
    st.session_state["hf_model_cache"] = {}

# ── Sidebar — configuration ───────────────────────────────────────────────────
with st.sidebar:
    st.title("🩺 Hunt AI Playground")
    st.caption("Compare rerankers + Gemini models on medical queries")

    st.subheader("🔑 API Keys")
    cohere_key = st.text_input(
        "Cohere API Key",
        value=os.getenv("COHERE_API_KEY", ""),
        type="password",
        help="Get free trial at cohere.com",
    )

    st.subheader("⚙️ Rerankers to test")
    use_cohere = st.checkbox("Cohere Rerank 3.5 (cloud)", value=bool(cohere_key))
    use_bge = st.checkbox("BGE Reranker v2-m3 · BAAI (local, 568M)", value=True)
    use_jina = st.checkbox("Jina Reranker v2 Multilingual (local, 278M)", value=True)
    use_medcpt = st.checkbox("MedCPT Cross-Encoder · NCBI (local, 110M)", value=True)

    st.subheader("🤖 Gemini Generation")
    enable_gemini = st.checkbox("Enable Gemini answer generation", value=True)
    gemini_models_selected = st.multiselect(
        "Models to compare:",
        ["gemini-2.5-flash-preview-05-20", "gemini-2.5-pro-preview-05-06"],
        default=["gemini-2.5-flash-preview-05-20", "gemini-2.5-pro-preview-05-06"],
    )

    st.subheader("📄 Query source")
    query_source = st.radio(
        "Use:",
        ["Custom query", "OpenEvidence benchmark"],
        index=0,
    )

    st.subheader("📄 Document source")
    doc_source = st.radio(
        "Use:",
        ["Paste documents manually", "Load from golden test set"],
        index=0,
    )

    st.subheader("🔡 Embedding backend")
    embedding_backend = st.radio(
        "For live Qdrant queries:",
        ["BGE-M3 (dense + sparse, local)", "Google text-embedding-004 (dense only, Vertex AI)"],
        index=0,
        help="BGE-M3 requires the embedding service running. Google uses Vertex AI (ADC).",
    )

    st.divider()
    st.caption(
        "BGE + Jina + MedCPT models are downloaded from HuggingFace on first use "
        "(500–600 MB each). They are cached in `~/.cache/huggingface/`."
    )


# ── Gemini generation helper ─────────────────────────────────────────────────

# ── Dashboard generation prompt (simplified version of main generation prompt) ─
# Agent: Dashboard / Evaluation (testing only — NOT the production pipeline)
# Model: Gemini Flash or Pro (user-selected in sidebar)
# Purpose: Quick generation for side-by-side reranker comparison. Uses a lighter
#          prompt than the production pipeline to isolate reranking quality signal.
_GENERATION_PROMPT = """\
<system_instruction>
  <identity>
    <role>Evidence-based medical assistant</role>
    <name>Hunt AI</name>
    <audience>Indian doctors</audience>
  </identity>

  <rules>
    <rule>Start with a "Practice Guideline" section summarizing the key recommendation.</rule>
    <rule>Use inline citations [1], [2], etc. referencing the chunk numbers.</rule>
    <rule>Include specific drug names, dosages, and trial names where available.</rule>
    <rule>End with a follow-up question suggestion.</rule>
    <rule>Be thorough but concise — target OpenEvidence-level quality.</rule>
  </rules>

  <input>
    <query>{query}</query>
    <retrieved_evidence description="ranked by relevance">
{chunks}
    </retrieved_evidence>
  </input>
</system_instruction>

Provide your evidence-based answer:"""


def _generate_gemini(
    query: str,
    top_chunks: list[str],
    model_name: str,
) -> dict:
    """Generate an answer using Gemini via Vertex AI ADC. Returns {answer, latency_ms, error}."""
    try:
        from shared.utils.gemini_client import get_gemini_model, make_generation_config
    except ImportError:
        return {"answer": "", "latency_ms": 0, "error": "shared module not importable — check PYTHONPATH"}

    try:
        model = get_gemini_model(model_name)
        chunks_text = "\n\n".join(
            f"[{i+1}] {chunk}" for i, chunk in enumerate(top_chunks)
        )
        prompt = _GENERATION_PROMPT.format(query=query, chunks=chunks_text)
        config = make_generation_config(temperature=0.2, max_output_tokens=2048, json_mode=False)

        t0 = time.perf_counter()
        response = model.generate_content(prompt, generation_config=config)
        latency_ms = (time.perf_counter() - t0) * 1000

        return {
            "answer": response.text,
            "latency_ms": latency_ms,
            "error": None,
        }
    except Exception as e:
        return {"answer": "", "latency_ms": 0, "error": str(e)}


# ── Main panel ────────────────────────────────────────────────────────────────
st.title("🔬 Reranker + Generation Comparison")
st.caption(
    "Compare reranker rankings and Gemini answer quality side-by-side. "
    "Use the OpenEvidence benchmark to measure accuracy against reference answers."
)

# ── Query input ────────────────────────────────────────────────────────────────
if query_source == "OpenEvidence benchmark":
    st.subheader("📋 OpenEvidence Benchmark Queries")

    difficulty_filter = st.radio(
        "Difficulty:",
        ["All", "Easy", "Medium", "Hard"],
        horizontal=True,
    )
    filtered = get_queries_by_difficulty(
        None if difficulty_filter == "All" else difficulty_filter.lower()
    )

    query_options = {
        f"[{q.difficulty.upper()}] Q{q.id}: {q.query[:80]}...": q
        for q in filtered
    }
    selected_label = st.selectbox("Select benchmark query:", list(query_options.keys()))
    selected_bq: BenchmarkQuery = query_options[selected_label]

    query = selected_bq.query
    st.text_area("**Selected Query**", value=query, height=100, disabled=True)

    # Show expected topics for manual quality assessment
    with st.expander("📝 Expected answer topics (reference)"):
        st.caption("A good answer should mention these key concepts:")
        for topic in selected_bq.expected_topics:
            st.markdown(f"- {topic}")
        st.divider()
        st.markdown(f"**Reference summary:** {selected_bq.reference_summary}")
else:
    selected_bq = None
    query = st.text_area(
        "**Medical Query**",
        value="What is ICMR recommended first-line treatment for drug-sensitive tuberculosis?",
        height=80,
    )

# ── Document input ────────────────────────────────────────────────────────────
_DEFAULT_DOCS = [
    "ICMR Standard Treatment Guidelines recommend the 2RHZE/4RH regimen as first-line therapy for new drug-sensitive TB cases. The intensive phase consists of Rifampicin, Isoniazid, Pyrazinamide, and Ethambutol for 2 months, followed by a continuation phase of Rifampicin and Isoniazid for 4 months.",
    "WHO recommends a 6-month rifampicin-based regimen (2RHZE/4RH) for treatment of drug-susceptible TB in adults and children. This regimen has >95% treatment success rates in clinical trials.",
    "The ACCORD trial demonstrated intensive glycemic control reduced microvascular complications in type 2 diabetes but increased mortality. Target HbA1c of 7.0-7.9% is recommended for most adults.",
    "Azithromycin 500mg once daily for 7 days is recommended by ICMR for typhoid fever (enteric fever) in adults. It is preferred over fluoroquinolones due to increasing resistance patterns in India.",
    "Multidrug-resistant tuberculosis (MDR-TB) requires treatment with second-line drugs. The BPaL regimen (Bedaquiline, Pretomanid, Linezolid) has shown high efficacy in the ZeNix trial for pre-XDR TB.",
    "Metformin remains the first-line pharmacological therapy for type 2 diabetes. It reduces HbA1c by 1-2%, has a favourable safety profile, and is inexpensive — critical for India's healthcare context.",
    "Dengue management focuses on fluid replacement therapy. ICMR guidelines recommend crystalloid IV fluids at 5-7 ml/kg/hour for dengue with warning signs. NSAIDs and aspirin are contraindicated due to bleeding risk.",
    "The DAPA-HF trial demonstrated dapagliflozin (SGLT2 inhibitor) reduced the risk of worsening heart failure or cardiovascular death by 26% in patients with HFrEF, regardless of diabetes status.",
]

if doc_source == "Paste documents manually":
    raw_docs = st.text_area(
        "**Documents** (one per line — paste retrieved chunks here)",
        value="\n\n".join(_DEFAULT_DOCS),
        height=300,
    )
    documents = [d.strip() for d in raw_docs.split("\n\n") if d.strip()]
else:
    golden_path = Path(__file__).parent.parent / "eval_data" / "golden_set.json"
    if golden_path.exists():
        import json
        golden = json.loads(golden_path.read_text())
        st.info(f"Loaded {len(golden)} golden queries. Using default documents above.")
        documents = _DEFAULT_DOCS
    else:
        st.warning("Golden set not found — using default documents.")
        documents = _DEFAULT_DOCS

st.caption(f"**{len(documents)} documents** ready for reranking")

# ── Run button ────────────────────────────────────────────────────────────────
col_run, col_clear = st.columns([1, 5])
with col_run:
    run_clicked = st.button("▶ Run Comparison", type="primary", use_container_width=True)
with col_clear:
    if st.button("↺ Reset", use_container_width=False):
        st.rerun()

# ── Execute rerankers in parallel ─────────────────────────────────────────────
if run_clicked:
    if not query.strip():
        st.error("Please enter a query.")
        st.stop()
    if not documents:
        st.error("No documents to rerank.")
        st.stop()

    active_rerankers: list[tuple[str, callable]] = []
    if use_cohere:
        if not cohere_key:
            st.warning("Cohere key missing — skipping Cohere.")
        else:
            active_rerankers.append(
                ("cohere", lambda q, d: rerank_cohere(q, d, cohere_key))
            )
    if use_bge:
        active_rerankers.append(
            ("bge", lambda q, d: rerank_bge(q, d, st.session_state["hf_model_cache"]))
        )
    if use_jina:
        active_rerankers.append(
            ("jina", lambda q, d: rerank_jina(q, d, st.session_state["hf_model_cache"]))
        )
    if use_medcpt:
        active_rerankers.append(
            ("medcpt", lambda q, d: rerank_medcpt(q, d, st.session_state["hf_model_cache"]))
        )

    if not active_rerankers:
        st.error("Select at least one reranker.")
        st.stop()

    wall_t0 = time.perf_counter()
    results: dict[str, RerankerOutput] = {}

    with st.spinner(f"Running {len(active_rerankers)} reranker(s) in parallel..."):
        with ThreadPoolExecutor(max_workers=len(active_rerankers)) as pool:
            futures = {
                pool.submit(fn, query, documents): name
                for name, fn in active_rerankers
            }
            for future in as_completed(futures):
                name = futures[future]
                results[name] = future.result()

    wall_ms = (time.perf_counter() - wall_t0) * 1000
    st.success(f"Done — total wall time: **{wall_ms:.0f} ms** (parallel execution)")

    # ── Results display ────────────────────────────────────────────────────────
    st.divider()

    # Summary latency bar chart
    latency_data = {
        r.name: r.total_latency_ms
        for r in results.values()
        if r.error is None
    }
    if latency_data:
        st.subheader("⏱ Latency Comparison")
        cols = st.columns(len(latency_data))
        for col, (name, ms) in zip(cols, latency_data.items()):
            with col:
                st.metric(label=name, value=f"{ms:.0f} ms")

    st.divider()
    st.subheader("📊 Rankings Side-by-Side")
    st.caption(
        "Each column shows how a reranker sorted the documents. "
        "Position 1 = most relevant. Color intensity = relevance score."
    )

    output_cols = st.columns(len(results))
    for col, (name, output) in zip(output_cols, results.items()):
        with col:
            st.markdown(f"**{output.name}**")
            st.caption(f"`{output.model_id}` · {output.total_latency_ms:.0f} ms")

            if output.error:
                st.error(f"Error: {output.error}")
                continue

            for result in output.results:
                all_scores = [r.score for r in output.results]
                min_s, max_s = min(all_scores), max(all_scores)
                norm = (result.score - min_s) / (max_s - min_s + 1e-9)
                green = int(norm * 180)
                bg_colour = f"rgba(0, {green + 60}, 0, 0.15)"

                with st.container():
                    st.markdown(
                        f"""<div style="
                            background:{bg_colour};
                            border-radius:6px;
                            padding:8px 10px;
                            margin-bottom:6px;
                            border-left: 3px solid rgba(0,{green+80},0,0.6);
                        ">
                        <span style="font-weight:700;font-size:0.8rem;">#{result.rank}</span>
                        <span style="color:#888;font-size:0.75rem;margin-left:6px;">
                            score: {result.score:.3f}
                        </span><br/>
                        <span style="font-size:0.82rem;line-height:1.4;">
                            {result.text[:200]}{"..." if len(result.text) > 200 else ""}
                        </span>
                        </div>""",
                        unsafe_allow_html=True,
                    )

    # ── Rank agreement analysis ────────────────────────────────────────────────
    st.divider()
    st.subheader("🤝 Rank Agreement (top-3 overlap)")

    valid_outputs = [o for o in results.values() if not o.error and o.results]
    if len(valid_outputs) >= 2:
        for i, a in enumerate(valid_outputs):
            for b in valid_outputs[i + 1 :]:
                top3_a = {r.index for r in a.results[:3]}
                top3_b = {r.index for r in b.results[:3]}
                overlap = len(top3_a & top3_b)
                st.write(
                    f"**{a.name}** vs **{b.name}**: "
                    f"{overlap}/3 documents in common in top-3 "
                    f"({'High agreement' if overlap >= 2 else 'Low agreement'})"
                )
    else:
        st.info("Run 2+ rerankers to see agreement analysis.")

    # ── Raw score table ───────────────────────────────────────────────────────
    with st.expander("🔢 Raw score table"):
        import pandas as pd

        rows = []
        for output in results.values():
            if output.error or not output.results:
                continue
            for result in output.results:
                rows.append({
                    "Reranker": output.name,
                    "Rank": result.rank,
                    "Score": round(result.score, 4),
                    "Doc (first 100 chars)": result.text[:100],
                })
        if rows:
            st.dataframe(pd.DataFrame(rows), use_container_width=True)

    # ── Gemini Generation Comparison ──────────────────────────────────────────
    if enable_gemini and gemini_models_selected:
        st.divider()
        st.subheader("🤖 Gemini Answer Generation")
        st.caption(
            "Using top-5 chunks from the best-performing reranker to generate answers. "
            "Compare Flash vs Pro quality and latency."
        )

        # Pick the best reranker's top-5 for generation context
        best_reranker = None
        for output in valid_outputs:
            if best_reranker is None or output.total_latency_ms < best_reranker.total_latency_ms:
                # Prefer Cohere if available, otherwise fastest
                if "Cohere" in output.name:
                    best_reranker = output
                    break
                best_reranker = output

        if best_reranker and best_reranker.results:
            top_k = 5
            top_chunks = [r.text for r in best_reranker.results[:top_k]]
            st.caption(
                f"Context: top-{top_k} chunks from **{best_reranker.name}** "
                f"(best available reranker)"
            )

            # Run Gemini models in parallel
            gemini_results: dict[str, dict] = {}
            with st.spinner(f"Generating answers with {len(gemini_models_selected)} Gemini model(s)..."):
                with ThreadPoolExecutor(max_workers=len(gemini_models_selected)) as pool:
                    gemini_futures = {
                        pool.submit(
                            _generate_gemini, query, top_chunks, model_name
                        ): model_name
                        for model_name in gemini_models_selected
                    }
                    for future in as_completed(gemini_futures):
                        model_name = gemini_futures[future]
                        gemini_results[model_name] = future.result()

            # Display latency comparison
            gen_latency = {
                name: r["latency_ms"]
                for name, r in gemini_results.items()
                if r["error"] is None
            }
            if gen_latency:
                gen_cols = st.columns(len(gen_latency))
                for col, (name, ms) in zip(gen_cols, gen_latency.items()):
                    with col:
                        short_name = "Flash" if "flash" in name else "Pro"
                        st.metric(label=f"Gemini {short_name}", value=f"{ms:.0f} ms")

            # Display answers side by side
            answer_cols = st.columns(len(gemini_results))
            for col, (model_name, result) in zip(answer_cols, gemini_results.items()):
                with col:
                    short_name = "Flash" if "flash" in model_name else "Pro"
                    st.markdown(f"**Gemini {short_name}**")
                    st.caption(f"`{model_name}`")

                    if result["error"]:
                        st.error(f"Error: {result['error']}")
                    else:
                        st.markdown(result["answer"])

            # If benchmark query, show quality assessment helper
            if selected_bq:
                st.divider()
                st.subheader("📝 Quality Assessment")
                st.caption(
                    "Check each generated answer against the expected topics from "
                    "the OpenEvidence reference."
                )

                for model_name, result in gemini_results.items():
                    if result["error"] or not result["answer"]:
                        continue
                    short_name = "Flash" if "flash" in model_name else "Pro"
                    answer_lower = result["answer"].lower()

                    st.markdown(f"**Gemini {short_name} — Topic Coverage:**")
                    covered = 0
                    for topic in selected_bq.expected_topics:
                        # Simple keyword check — not perfect but useful
                        keywords = [w.lower() for w in topic.split() if len(w) > 3]
                        matches = sum(1 for kw in keywords if kw in answer_lower)
                        hit = matches >= len(keywords) * 0.5
                        if hit:
                            covered += 1
                        icon = "✅" if hit else "❌"
                        st.write(f"  {icon} {topic}")

                    total = len(selected_bq.expected_topics)
                    pct = (covered / total * 100) if total else 0
                    color = "green" if pct >= 70 else "orange" if pct >= 40 else "red"
                    st.markdown(
                        f"**Coverage: {covered}/{total} ({pct:.0f}%)** "
                        f":{color}[{'Good' if pct >= 70 else 'Needs improvement'}]"
                    )
                    st.write("")
        else:
            st.warning("No valid reranker results to use as generation context.")
