---
name: article-writing
description: Use this skill when writing any long-form content — blog posts, technical articles, white papers, medical summaries, case studies, research briefs, LinkedIn posts, or newsletter content. Also trigger for: writing without AI-sounding language, adopting a specific voice, structuring arguments, writing with authority on technical topics, translating jargon for non-expert audiences. The goal is writing that sounds like a specific, knowledgeable human — not a committee or a chatbot.
---

# Article Writing — Long-Form Without the AI Stench

Most AI-generated articles have the same problem: they sound like they were written by someone who has read everything and experienced nothing. They are technically accurate, deeply forgettable, and instantly recognisable as machine-produced.

This skill produces writing that sounds like a specific human with a point of view.

---

## The Structure of a Good Article

Every article is a promise to the reader: "Read this and you will understand X / be able to do Y / see Z differently." The structure must deliver on that promise efficiently.

```
Hook (first 3 sentences) — stop the scroll
↓
Problem or tension — why this matters now
↓
Insight or revelation — the thing most people get wrong
↓
Evidence — specific, not abstract
↓
Implications — so what?
↓
Conclusion — what the reader should do or think differently
```

---

## The Hook

The hook is not an introduction. It is not "In this article, I will discuss..." It is the sentence that makes someone stop scrolling.

**Types of hooks that work:**

**The counter-intuitive claim:**
> "OpenEvidence reached 40% of US physicians without a single sales call."

**The specific, surprising number:**
> "India has 1.4 million registered doctors. Zero of them have a purpose-built clinical decision support tool."

**The provocative question:**
> "If your medical AI hallucinates a dosage and a doctor acts on it, who is liable?"

**The scene:**
> "It's 3am in a district hospital in Uttarakhand. The only doctor on call has a patient in septic shock and no internet access. She types a WhatsApp message."

**Rules for hooks:**
- Maximum 2-3 sentences
- Specific over general (a person, a number, a place — not "many doctors")
- No "In today's rapidly changing world..."
- No throat-clearing — start in motion

---

## Voice and Tone

### The Register Spectrum

```
Academic ←────────────────────────────────→ Conversational
"The evidence suggests significant..."     "The data is clear:"
"It is worth noting that..."               "Here's what most people miss:"
"This has implications for..."             "This changes everything about..."
```

Match register to audience:
- **Investors/executives** — confident, specific, forward-looking
- **Doctors** — peer-to-peer, evidence-first, direct
- **Technical engineers** — precise, code-first, no marketing language
- **General public** — concrete metaphors, no jargon

### The AI-Sounding Patterns to Purge

```
BAD: "It is important to note that..."
GOOD: [Just note it. The importance is in the noting.]

BAD: "In conclusion, we have seen that..."
GOOD: [Just conclude. Don't announce that you're concluding.]

BAD: "This cutting-edge technology leverages advanced AI..."
GOOD: "This system retrieves, verifies, and delivers evidence."

BAD: "It goes without saying that..."
GOOD: [If it goes without saying, don't say it.]

BAD: Transitions like "Furthermore," "Moreover," "In addition,"
GOOD: [Just continue. Or use a short, punchy transition: "And yet." "But here's the problem."]

BAD: Passive voice throughout ("The evidence was retrieved by the system")
GOOD: Active voice ("The system retrieves evidence")

BAD: Ending with "In summary, this article has discussed..."
GOOD: Ending with the thing the reader should remember or do.
```

---

## Writing Medical Evidence Articles

### The Hierarchy of Evidence in Prose

When writing about medical research, the language must match the strength of the evidence:

```
RCT / Meta-analysis: "[Drug] reduces [outcome] by X% [RR 0.69, 95% CI...]"
Cohort study: "[Drug] was associated with lower [outcome] in [N] patients"
Expert guideline: "IDSA 2021 guidelines recommend [drug] for [indication]"
Expert opinion: "Experts suggest [approach], though evidence is limited"
Animal study: [Don't cite for clinical decisions]
```

Never write "studies show" — name which studies. Never write "evidence suggests" — say what the evidence says specifically.

### The Attribution Rule

Every factual claim needs a traceable source. In medical articles:

```
WEAK: "Fidaxomicin is preferred over vancomycin."
STRONG: "Fidaxomicin is preferred over vancomycin for initial CDI episodes, based on the 2021 IDSA/SHEA guideline update and a 2022 meta-analysis of 3,944 patients showing a 31% reduction in recurrence (RR 0.69, 95% CI 0.52-0.91)."
```

The reader should be able to find the source from your description without needing a citation number.

---

## Technical Articles for Engineers

### Code First, Words Second

Engineers trust code over prose. Lead with the working example:

```python
# Show the 5-line version first
results = await hybrid_retrieve(query, qdrant_client, limit=50)
ranked = cohere_rerank(query, [r.content for r in results], top_n=5)
response = await generate_with_citations(query, ranked)
await verify_citations(response, ranked)
```

Then explain what each step does and why. Never explain before showing.

### The "You Built This Wrong" Opening

The most-read technical articles are those that explain why the common approach is wrong:

> "Most RAG tutorials tell you to retrieve 5 documents and pass them to the LLM. This is wrong, and here's why it degrades quality at scale."

Engineers stop scrolling when you challenge their existing approach. Confirm what they're doing right, then explain what they're doing wrong.

---

## Structure Templates by Format

### Blog Post (1,000-2,000 words)
```
Hook (3 sentences)
The problem (150 words)
What most people get wrong (200 words)
The correct approach (500 words, with code/evidence)
Implications (150 words)
Call to action (50 words)
```

### LinkedIn Post
```
Line 1: The hook — one punchy line
(line break)
3-5 short paragraphs, each with one idea
(line break)
1-2 sentence call to action or question
```

### Technical White Paper (3,000-5,000 words)
```
Abstract (150 words — the TL;DR)
Problem Statement (300 words)
Current Approaches and Their Limitations (500 words)
Proposed Architecture/Solution (1,500 words — the meat)
Implementation Details (500 words)
Results/Evidence (500 words)
Conclusion and Future Work (300 words)
References
```
