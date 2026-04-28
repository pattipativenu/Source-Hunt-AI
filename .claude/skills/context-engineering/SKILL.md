---
name: context-engineering
description: >
  Design, structure, and optimize the context window passed to Gemini for
  medical evidence synthesis. Use when designing the RAG context assembly
  step, improving response quality, reducing hallucinations, or optimizing
  token usage. Covers lost-in-the-middle mitigation, context ordering,
  system prompt design, and few-shot example selection.
argument-hint: "<optimization goal: quality|cost|latency|hallucination-reduction>"
disable-model-invocation: false
context: fork
allowed-tools: Bash, Read, Write
---

# Context Engineering

## Purpose

The quality of Noocyte AI's medical answers depends not just on *what* information is retrieved, but on *how* that information is presented to Gemini. Context engineering is the art and science of structuring the input to the LLM to maximize the quality, accuracy, and safety of the output.

This skill is relevant even if you have no programming background — the principles here are about *how to communicate with an AI*, which is a skill anyone can learn.

---

## The Lost-in-the-Middle Problem

Research has shown that LLMs like Gemini perform worse at using information that appears in the **middle** of a long context window. They are best at using information at the **beginning** and **end**.

```
Context window performance:
Position 1 (start):   ████████████ HIGH attention
Position 2:           ██████████   HIGH attention
Position 3 (middle):  ████         LOW attention ← DANGER ZONE
Position 4 (middle):  ████         LOW attention ← DANGER ZONE
Position 5 (end):     ██████████   HIGH attention

Solution: Put the BEST evidence at position 1 and position 5.
Put the LEAST important context in the middle.
```

### Implementation

```python
def assemble_context_with_lost_in_middle_mitigation(
    chunks: list[dict],
    max_tokens: int = 8000,
) -> str:
    """
    Assemble retrieved chunks into a context string.
    
    Strategy: Best chunk first, second-best chunk last.
    This ensures the most relevant evidence is in high-attention positions.
    
    Args:
        chunks: List of reranked chunks, sorted by relevance (best first)
        max_tokens: Maximum tokens for the context window
    
    Returns:
        Formatted context string for Gemini
    """
    if not chunks:
        return "No relevant evidence found in the knowledge base."
    
    if len(chunks) == 1:
        return format_chunk(chunks[0], index=1)
    
    # Reorder: best first, second-best last, rest in middle
    reordered = [chunks[0]]           # Best chunk → position 1
    reordered.extend(chunks[2:])      # Middle chunks → middle positions
    reordered.append(chunks[1])       # Second-best chunk → last position
    
    context_parts = []
    total_tokens = 0
    
    for i, chunk in enumerate(reordered, 1):
        chunk_text = format_chunk(chunk, index=i)
        chunk_tokens = estimate_tokens(chunk_text)
        
        if total_tokens + chunk_tokens > max_tokens:
            break
        
        context_parts.append(chunk_text)
        total_tokens += chunk_tokens
    
    return "\n\n---\n\n".join(context_parts)

def format_chunk(chunk: dict, index: int) -> str:
    """Format a single chunk for the context window."""
    return f"""[SOURCE {index}]
Title: {chunk.get('title', 'Unknown')}
Authors: {chunk.get('authors', 'Unknown')}
Journal: {chunk.get('journal', 'Unknown')} ({chunk.get('year', 'Unknown')})
DOI: {chunk.get('doi', 'Not available')}
Source type: {chunk.get('source_type', 'Unknown')} | Priority tier: {chunk.get('priority_tier', 'Unknown')}

{chunk.get('text', '')}"""
```

---

## System Prompt Architecture

The system prompt is the most important piece of context engineering. It defines the AI's identity, constraints, and output format.

### The Four Layers of the System Prompt

```python
SYSTEM_PROMPT = """
# LAYER 1: IDENTITY
You are Noocyte AI — a clinical decision support tool for Indian doctors.
You synthesize peer-reviewed medical evidence to answer clinical questions.
You are NOT a doctor and do NOT replace clinical judgment.

# LAYER 2: HARD CONSTRAINTS (never violate)
NEVER use: "prescribe", "administer", "give the patient", "start on"
ALWAYS use: "Guidelines recommend [N]", "Evidence supports [N]", "According to [source] [N]"
EVERY statistical claim (%, HR, p-value, NNT) MUST have an inline [N] citation.
If the query involves an Indian condition, cite ICMR guidelines BEFORE international guidelines.

# LAYER 3: OUTPUT STRUCTURE
Respond in this exact JSON format:
{
  "answer": "...",
  "citations": [...],
  "confidence_level": "HIGH|MEDIUM|LOW",
  "india_specific_note": "...",
  "follow_up_question": "..."
}

# LAYER 4: QUALITY STANDARDS
Model your answers on the OpenEvidence style:
- Lead with the direct answer (BLUF — Bottom Line Up Front)
- Include quantified comparisons (e.g., "16% vs 25% recurrence rate [2]")
- Mention alternatives when the first-line is unavailable
- End with a follow-up question to deepen engagement
"""
```

### Why This Order Matters

The layers are ordered by importance. Gemini reads the system prompt from top to bottom. The most critical constraints (identity, hard rules) come first so they are in the high-attention zone.

---

## Few-Shot Example Selection

Few-shot examples dramatically improve output quality. Choose examples that represent the hardest cases:

```python
# Select few-shot examples strategically
FEW_SHOT_STRATEGY = {
    "principle": "Show the model the hardest cases, not the easiest",
    
    "good_examples": [
        # Example 1: Drug comparison (tests quantified comparison)
        {
            "query": "Apixaban vs rivaroxaban for AF with CKD",
            "ideal_answer": "Apixaban is preferred over rivaroxaban in AF with moderate CKD (eGFR 30-50) due to lower major bleeding risk (HR 0.62, 95% CI 0.56-0.69) [1] with similar stroke prevention efficacy [2]...",
        },
        # Example 2: Indian-specific query (tests ICMR priority)
        {
            "query": "MDR-TB treatment in India",
            "ideal_answer": "ICMR recommends the BPaL regimen (bedaquiline + pretomanid + linezolid) for MDR-TB [1]. This aligns with WHO 2022 guidelines [2] and is available under India's PMDT programme...",
        },
        # Example 3: Brand name query (tests INN resolution)
        {
            "query": "Dolo 650 for fever",
            "ideal_answer": "Paracetamol (Dolo 650) 650mg is appropriate for fever management in adults [1]. Standard dosing is 500-1000mg every 4-6 hours, maximum 4g/day [2]...",
        },
    ],
    
    "bad_examples_to_avoid": [
        # Don't use examples that are too easy — they don't teach the model anything
        {"query": "What is hypertension?", "answer": "..."},
    ],
}

def build_few_shot_context(query_type: str) -> str:
    """Select the most relevant few-shot example for the current query type."""
    examples = {
        "drug_comparison": FEW_SHOT_STRATEGY["good_examples"][0],
        "india_specific": FEW_SHOT_STRATEGY["good_examples"][1],
        "drug_lookup": FEW_SHOT_STRATEGY["good_examples"][2],
    }
    
    example = examples.get(query_type, examples["drug_comparison"])
    
    return f"""
EXAMPLE QUERY: {example['query']}
EXAMPLE ANSWER: {example['ideal_answer']}

Now answer the following query in the same style:
"""
```

---

## Token Budget Management

Gemini 2.5 Flash has a large context window, but every token costs money. Manage the budget deliberately:

```python
TOKEN_BUDGET = {
    "system_prompt": 800,      # Fixed — optimize once, reuse always
    "few_shot_examples": 600,  # 1-2 examples maximum
    "retrieved_context": 6000, # The evidence chunks — most important
    "query": 200,              # The doctor's question
    "output_buffer": 1000,     # Reserve for the generated answer
    "total": 8600,             # Well within Gemini 2.5 Flash's limit
}

def estimate_tokens(text: str) -> int:
    """Rough token estimate: 1 token ≈ 4 characters for English medical text."""
    return len(text) // 4

def check_token_budget(context: str, query: str) -> dict:
    """Verify the assembled context fits within the token budget."""
    context_tokens = estimate_tokens(context)
    query_tokens = estimate_tokens(query)
    system_tokens = TOKEN_BUDGET["system_prompt"]
    
    total = context_tokens + query_tokens + system_tokens + TOKEN_BUDGET["output_buffer"]
    
    return {
        "total_estimated": total,
        "within_budget": total < 8600,
        "context_tokens": context_tokens,
        "recommendation": "Truncate context" if context_tokens > 6000 else "OK",
    }
```

---

## Hallucination Reduction Techniques

```python
# Technique 1: Grounding instruction — force the model to cite sources
GROUNDING_INSTRUCTION = """
IMPORTANT: Only use information from the provided [SOURCE N] sections above.
If the answer is not in the sources, say: "The provided evidence does not address this specific question."
Do NOT use your training knowledge to fill gaps — cite only what is in the sources.
"""

# Technique 2: Uncertainty quantification — force the model to express confidence
UNCERTAINTY_INSTRUCTION = """
Set confidence_level based on evidence quality:
- HIGH: Multiple RCTs or meta-analyses directly address the question
- MEDIUM: Guideline recommendation with limited RCT support, or indirect evidence
- LOW: Expert opinion only, or evidence is conflicting
"""

# Technique 3: Citation verification prompt — force self-check
CITATION_CHECK_INSTRUCTION = """
Before finalizing your answer, verify:
1. Every [N] in the answer body has a matching entry in the citations array
2. Every citation in the citations array is referenced in the answer body
3. No citation numbers are skipped (must be sequential: [1], [2], [3]...)
4. Every DOI in the citations array matches a source provided above
"""
```

---

## What NOT to Do

```python
# ❌ Dumping all chunks in order without lost-in-middle mitigation
context = "\n".join([c["text"] for c in chunks])  # Best chunk may be in the middle

# ❌ Putting the system prompt at the END of the context
messages = [
    {"role": "user", "content": context + "\n\n" + system_prompt},  # WRONG ORDER
]

# ❌ Using the same few-shot examples for every query type
# Drug comparison examples don't help for emergency queries

# ❌ Not reserving token budget for the output
# If the context fills the entire window, Gemini has no room to generate a response

# ✅ Always: system prompt first, few-shot examples second, context third, query last
messages = [
    {"role": "system", "content": system_prompt},
    {"role": "user", "content": few_shot_example},
    {"role": "assistant", "content": few_shot_answer},
    {"role": "user", "content": f"EVIDENCE:\n{context}\n\nQUESTION: {query}"},
]
```

---

*The context window is not a dump truck. It is a carefully curated briefing for a brilliant but literal assistant.*
