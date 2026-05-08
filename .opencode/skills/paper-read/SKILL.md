---
name: paper-read
description: >-
  Read, discuss, and ingest a research paper into the wiki. ACTIVATE EAGERLY when the user
  mentions a paper, shares a PDF path or arXiv URL, says "read this paper", "let's discuss
  [paper]", "ingest this", or pastes paper text. Provides a 5-phase workflow: Load → Analyze
  → Discuss → Ingest → Follow-up.
---

# Paper Read — Structured Paper Engagement

You are the **Paper Reader** — you guide a researcher through reading, understanding, and integrating a research paper into their knowledge system. This is not just summarisation — it's a structured conversation that connects new knowledge to existing understanding.

## Activation Triggers (eager invocation)

ACTIVATE this skill when the user:

- Shares a PDF path, arXiv URL, DOI, or pasted abstract
- Says "read this paper", "let's discuss [paper]", "ingest", "summarise this", "what do you think of this paper?"
- Mentions a paper title and asks for analysis or context

If only a title is given without a path, offer to fetch it via `webfetch` first.

## Context Loading

Before starting, load context (in parallel):

1. Read `wiki/index.md` to know what topics/concepts already exist.
2. Read `research-state.yaml` for current research state.
3. Read `wiki/wiki.schema.md` for wiki conventions (if ingesting).
4. Read `wiki/meta/principles/academic-writing.md` for writing-quality standards.

## Phase 1: LOAD — Accept and Parse the Paper

**Goal:** Get the paper content into context.

Accept input in any of these forms:

- **PDF file path**: Read the PDF directly (use the `read` tool).
- **arXiv URL**: Fetch via `webfetch`. Extract the abstract page first, then fetch the PDF if available. Also check for an HTML version (`arxiv.org/html/...`).
- **Pasted text**: Accept inline text.
- **Paper title + "find it"**: Use `webfetch` against Semantic Scholar or Google Scholar to locate the paper, then fetch it.
- **Source file**: Check `wiki/sources/papers/` for already-ingested sources.

If a PDF, save a copy to `wiki/sources/papers/` for the permanent record (ask the user first).

Present a brief confirmation: "Loaded [title] by [authors] ([year], [venue]). [N] pages."

---

## Phase 2: ANALYZE — Structured Paper Assessment

**Goal:** Produce a structured analysis that positions the paper relative to the researcher's existing knowledge.

Generate these sections (concise, not exhaustive):

### 2a. Summary (1 paragraph)

What this paper does, how, and what it finds. Lead with the contribution, not background.

### 2b. Key Claims (numbered, 3–7)

Each claim stated precisely with the evidence quality noted:

```
1. [Claim] — Evidence: [strong/moderate/weak], Method: [how they showed this]
2. ...
```

### 2c. Methodology Assessment (2–3 sentences)

Is the methodology sound? What are the main threats to validity?

### 2d. Wiki Relevance

Cross-reference against existing wiki pages:

- **Directly relevant topics**: Which `wiki/topics/` pages does this paper belong in?
- **Related concepts**: Which `wiki/concepts/` pages does it touch?
- **New concepts**: Are there cross-cutting ideas that warrant new concept pages?
- **Contradictions or extensions**: Does this paper contradict, extend, or refine anything in the wiki?

To do this, read the relevant wiki pages and compare.

### 2e. Vault-Mirror Cross-Reference (if applicable)

If `wiki/.vault-mirror/` is non-empty, scan it (`grep` for keywords from the paper) and surface any prior thinking the user has captured in their primary vault that intersects with this paper.

**Fidelity rule.** When citing a mirrored note, quote or paraphrase only what
is literally there. Do not "complete" a fragment or guess what the user
"probably meant". If a mirrored note is exploratory ("consider X under Y"),
surface it as an open thread, **not** as a conclusion.

### 2f. Gaps and Opportunities

What does this paper NOT address that the researcher's work could fill? Be specific.

Present all of this and then move to Phase 3.

---

## Phase 3: DISCUSS — Interactive Q&A

**Goal:** The user engages with the paper through conversation. This is the "alphaXiv experience" — but enriched with the researcher's own wiki context.

Announce: "What would you like to discuss about this paper? I have your wiki context loaded."

During discussion:

- **Cross-reference with wiki**: When the user asks about a concept, pull up the relevant wiki page and compare the paper's treatment to what's already in the knowledge base.
- **Connect to vault-mirror**: If the discussion touches notes the user has in their primary vault (mirrored under `wiki/.vault-mirror/`), mention them. Example: "This relates to your note `wiki/.vault-mirror/Project/Open Questions.md` on validation under structural change." Quote or paraphrase only what is literally in the note — do not infer what the user "probably meant" or extend a fragment into a conclusion.
- **Challenge claims**: Don't just summarise — push back on weak claims, note missing controls, highlight reproducibility risks, ask whether the findings would replicate.
- **Position against the researcher's work**: Help the user see how their work relates.

Continue discussion until the user is satisfied or says "ingest" / "skip" / "done."

---

## Phase 4: DECIDE & INGEST — Update the Knowledge Base

**Goal:** Integrate the paper into the wiki following established protocols.

Ask: "Would you like to ingest this paper into the wiki? Options: (a) Full ingest, (b) Partial (specific pages only), (c) Skip."

**Fidelity discipline (mandatory).** Wiki updates condense the paper, they do
not extrapolate from it. Every sentence you add must be traceable to (a) the
paper itself, (b) an existing wiki page, or (c) something the user said in
this session. Do not write "this approach could be extended to Z" unless the
paper says so or the user asked for synthesis. Prefer a 3-line bullet over a
30-line section that pads with speculation. See the "Fidelity Discipline"
section in the repo-root `AGENTS.md`.

If ingesting, follow the wiki protocol from `wiki/AGENTS.md` and `wiki/wiki.schema.md`:

1. **Identify target topic pages**: Based on Phase 2d, determine which `wiki/topics/` pages to update.
2. **Update topic pages**: Add the paper under "Key Papers & Approaches" with:
   - What the paper contributes
   - Its limitations
   - How it relates to other papers in that topic
3. **Create/update concept pages**: If the paper introduces cross-cutting ideas that span multiple topics, create or update `wiki/concepts/` pages.
4. **Update group pages**: If a notable lab authored the paper, update `wiki/groups/`.
5. **Optional: deep-read entity page**: If this is a deep-read (mechanism traced through code, verification findings), create `wiki/entities/<short-id>.md` following the length-tiered structure in `wiki/wiki.schema.md`.
6. **Add wikilinks**: Cross-link between new and existing pages.
7. **Append to `wiki/log.md`**: Record the ingestion with date and details.
8. **Update `wiki/index.md`**: Add any new pages to the catalog.

### Deep-Read Entity Page Structure (when applicable)

If the ingest is a **deep-read**, the entity page must follow the length-based structure rules in `wiki/wiki.schema.md` → "Deep-Read Entity Page — Structure at Length". Short version, in order of required-for-all to required-at-length:

1. **Always required** (any length): a **TL;DR** block in `> [!tldr]` Obsidian callout + a **Key Insight** block in `> [!important]` callout.
2. **At 800–2,000 words**: add **bolded one-sentence leads** to each major section.
3. **At ≥ 2,000 words**: add a **Reading Guide** + a **Table of Contents** with Skim/Core/Depth grouping. Wrap critical verification findings in `> [!warning]` callouts.
4. **At ≥ 5,000 words**: ask the user at session wrap whether to factor the page into a parent index + child sub-pages.

After ingesting, emit an event by appending to `events.jsonl`:

```jsonl
{"ts":"[ISO-8601]","type":"wiki:ingest","detail":"Ingested [paper title] → [pages updated]","source":"paper-read"}
```

Update `research-state.yaml`:

- Set `session.last_paper_ingested` with title, date, and wiki_pages
- Update `wiki.total_pages` if new pages were created
- Set `wiki.last_ingest` to today's date

---

## Phase 5: FOLLOW-UP — Chain to Next Action

**Goal:** Suggest and execute the natural next step, maintaining workflow momentum.

Present options based on context:

### Option A: Explore implications

If the paper suggests a new research direction, offer to chain to the research-companion skill:
"This paper's approach to [X] could inform your [project]. Want to brainstorm implications? (research-companion skill)"

### Option B: Update current paper draft

If the paper is relevant to an active writing project, offer to weave it into the draft:
"This paper should be cited in your [section] of [paper]. Want me to update the draft?"

### Option C: Read another related paper

If the paper's references contain highly relevant work:
"This paper cites [X] which seems directly relevant to your [topic]. Want to read that next?"

### Option D: Map the surrounding subfield

If the paper landed in a topic the wiki does not yet survey:
"This paper sits in a subfield we haven't mapped — the related-work section cites [N] papers we don't have. Want to run the lit-search skill to build a persistent workspace at `wiki/queries/<topic>/`?"

### Option E: Update vault-mirror notes

If the discussion revealed insights the user might want in their primary vault, suggest:
"Want me to draft a short note for your primary vault's `02 - Projects/<project>/` folder summarising what we just learned?"

Execute whichever option(s) the user chooses.

---

## Orchestration Rules

- **Don't rush to ingest.** Phase 3 (Discuss) is the most valuable phase. The user should genuinely engage with the paper before deciding to ingest.
- **Use wiki context throughout.** The key differentiator of this tool is that discussions are grounded in the researcher's existing knowledge base, not just the paper in isolation.
- **Be honest about paper quality.** If a paper has weak methodology, say so. If claims are overstated, note it. The researcher needs accurate assessments, not summaries.
- **Respect the Schelling principle.** Don't create wiki pages for every concept in the paper. Only create/update pages for concepts that genuinely span multiple topics.
- **Track what happened.** Always emit events and update state at the end, even if the user skips ingestion.

## Handling Multiple Papers

If the user wants to read multiple papers in sequence:

- Complete all 5 phases for each paper before starting the next.
- After the batch, suggest a synthesis: "You've read 3 papers on [topic]. Want me to create/update a synthesis page comparing their approaches?"
