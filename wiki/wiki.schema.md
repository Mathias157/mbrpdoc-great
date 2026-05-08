# Wiki Schema & Conventions

This file defines how the knowledge wiki is structured and maintained. The LLM
reads this when performing wiki operations (ingest, query, lint).

---

## Three-Layer Architecture

1. **Raw sources** (`sources/`): Immutable documents — papers, notes, clippings. Never modified after ingestion.
2. **Wiki pages** (`topics/`, `concepts/`, `groups/`, `syntheses/`, `queries/`, `entities/`, `research-evaluations/`): LLM-generated and maintained. The knowledge layer.
3. **This schema** (`wiki.schema.md`): Conventions and workflows. The configuration layer.

## Special Files

- **`index.md`**: Content catalog organised by type. Updated whenever pages are added/removed.
- **`log.md`**: Append-only chronological record of all wiki operations.

---

## Page Types

### Topic Page (`topics/`) — THE HEART OF THE WIKI

Thematic pages covering a subfield or major theme. Each topic page weaves
together 5–15 papers in context, compares approaches, and identifies gaps.
**When ingesting a new paper, update the relevant topic page(s) rather than
creating standalone entity pages.**

```yaml
---
type: topic
related_projects: [project-slug, ...]
key_papers: [Author Year, ...]
last_reviewed: YYYY-MM-DD
---
```

Structure:

1. `# Title`
2. `## Overview` — 2–3 paragraphs introducing the theme
3. `## Key Papers & Approaches` — each major paper/system described with contributions, limitations
4. `## Current State & Debates` — what's settled, what's contested
5. `## Gaps & Opportunities` — what's missing, where our work fits
6. `## Related` — `[[wikilinks]]` to other topics and concepts

### Group Page (`groups/`)

Research groups — who's building what, their trajectory, how they relate to our work.

```yaml
---
type: group
members: [names]
affiliation: institution
last_reviewed: YYYY-MM-DD
---
```

Structure:

1. `# Group Name`
2. `## Key Contributions` — major papers/systems
3. `## Trajectory` — where they're heading
4. `## Relevance to Our Work`
5. `## Related`

### Concept Page (`concepts/`)

Cross-cutting methodological ideas that appear across multiple topics.

```yaml
---
type: concept
aliases: [alternate names]
related_projects: [project-slug, ...]
related_concepts: [page-slug, ...]
confidence: high | medium | speculative
last_reviewed: YYYY-MM-DD
---
```

Structure:

1. `# Title`
2. One-paragraph definition (2–4 sentences)
3. `## Key Claims` — numbered, each with citation or source
4. `## Evidence` — from our research + literature
5. `## Open Questions` — what we don't know yet
6. `## Related` — `[[wikilinks]]` to other pages

### Entity Page (`entities/`) — Deep-Read Snapshots

Optional standalone pages for papers/systems that warrant a deep dive (mechanism
traced through code, verification findings, conceptual positioning). Most papers
should be summarised inside their topic page; promote to an entity page only
when the depth justifies a dedicated home.

```yaml
---
type: entity
short_id: lastnames-keyword-year
related_topics: [[topic-slug]]
last_reviewed: YYYY-MM-DD
---
```

#### Deep-Read Entity Page — Structure at Length

Length-based requirements (always required, then progressive):

1. **Always required (any length)**:
   - **TL;DR** in `> [!tldr]` Obsidian callout (descriptive: what + headline number)
   - **Key Insight** in `> [!important]` callout (interpretive: the sharp takeaway)
2. **At 800–2,000 words**: bolded one-sentence leads on each major section. A reader who skims only the leads should get the Tier-2 summary for free.
3. **At ≥ 2,000 words**: a **Reading Guide** paragraph + a **Table of Contents** with Skim/Core/Depth grouping. Wrap critical verification findings in `> [!warning]` callouts.
4. **At ≥ 5,000 words**: ask the user at session wrap whether to factor the page into a parent index + child sub-pages. Default: no; the question is the point.

### Synthesis Page (`syntheses/`)

For cross-cutting analyses that integrate multiple concepts and sources.

```yaml
---
type: synthesis
source_pages: [page-slugs this synthesizes]
related_projects: [project-slug, ...]
last_reviewed: YYYY-MM-DD
---
```

Structure:

1. `# Title`
2. `## Thesis` — 1–3 sentence core claim
3. `## Evidence & Argument` — detailed analysis with citations
4. `## Implications` — what this means for our research
5. `## Sources` — citations with `[[wikilinks]]`

### Query Result Page (`queries/`)

For promoted query results — valuable answers worth preserving.

```yaml
---
type: query
original_question: "the question that was asked"
date_answered: YYYY-MM-DD
source_pages: [pages consulted]
---
```

Structure:

1. `# Question Title`
2. `## Short Answer` — 2–3 sentences
3. `## Detailed Analysis`
4. `## Sources Consulted`
5. `## Follow-up Questions`

### Lit-Search Workspace (`queries/<topic>/`)

Persistent per-topic literature-mapping workspaces produced by the **lit-search**
skill. Unlike single-page query results above, a lit-search workspace is a
**folder** containing a living scratchpad for subfield discovery:

```
queries/<topic>/
  memory-bank.md        # Append-only list of discovered papers (short-id, venue, tier, notes)
  mind-graph.md         # Topic-centric hierarchy of sub-themes + key papers
  references.bib        # Combined BibTeX for all papers (citation key = short-id)
  discussions/          # Paper-comparison logs (optional)
```

Conventions:

- Folder name is a kebab-case topic slug (e.g., `micro-macro-validation-abm/`).
- Paper `short-id` = `firstauthorlastname-keyword-year`, matching `wiki/entities/` filenames so paper-read hand-offs are consistent.
- Lit-search workspaces are **scratchpads**, not canonical knowledge. Deep-read summaries live in `wiki/entities/` (via paper-read); survey-level summaries graduate to `wiki/topics/` or `wiki/syntheses/`.
- PDFs are NOT stored inside the workspace — they live in `wiki/sources/papers/` via paper-read.
- A workspace is "graduated" (but kept as audit trail) when its `mind-graph.md` has been promoted to a topic or synthesis page.

### Research Evaluation Page (`research-evaluations/`)

Point-in-time verdicts on research directions, produced by the
**research-companion** skill. Each page captures a snapshot of how a direction
looked when evaluated — the verdict, the dimension scores, the concerns, and
the conditions under which we should revisit.

```yaml
---
type: research_evaluation
date: YYYY-MM-DD
topic: short-topic-slug
verdict: PURSUE | PARK | KILL
nugget: "one-sentence takeaway worth remembering"
revisit_conditions: [condition 1, condition 2]
last_reviewed: YYYY-MM-DD
related_topics: [[topic-slug]]
related_projects: [project-slug, ...]
---
```

Structure:

1. `# Title` — the research direction being evaluated
2. `## Verdict` — 2–3 sentences stating the verdict and core reasoning
3. `## Dimension Scores` — the Phase 3 table from research-companion (dimension, score, rationale)
4. `## Key Concerns` — the top risks, open questions, or blockers
5. `## Watch List` — signals, papers, or results that would change the verdict
6. `## Revisit Conditions` — explicit triggers for re-opening this evaluation
7. `## Related` — `[[wikilinks]]` to topics, concepts, and prior evaluations

**Canonical verdict enum:** UPPERCASE and closed: PURSUE, PARK, or KILL. Do not
invent new values — alignment matters for dashboard queries and weekly-review scans.

**Word limit:** 600 words.

**Filename convention:** `research-evaluations/YYYY-MM-DD-<topic-slug>.md` —
explicit exception to the no-dates-in-filenames rule because evaluations are
point-in-time artifacts.

---

## Linking Conventions

- Use `[[page-slug]]` for wiki-internal links (Obsidian-compatible)
- Use `[text](../path)` for links to project files outside the wiki
- Cross-vault links to the primary Obsidian vault use `[[obsidian://vault/<vault>/<note>]]` or the configured vault alias.
- Every page must have at least one incoming link (no orphans)

## Naming Conventions

- Filenames: kebab-case, descriptive, no dates (e.g., `variance-compression.md`)
- One concept per page — split if a page covers two distinct ideas
- Prefer specificity over generality (e.g., `schelling-segregation-model.md` not `segregation.md`)
- Entity pages for papers: `lastnames-keyword-year.md` (e.g., `park-generative-agents-2023.md`)

## Page Size

- Topic pages: 800–2 500 words (room for context + cross-paper comparison)
- Concept pages: under 500 words (concise definitions, not essays)
- Entity pages: see length-tiered structure above
- Synthesis pages: under 800 words (focused arguments)
- Query pages: under 600 words
- Research-evaluation pages: under 600 words

---

## Operations

### Ingest (driven by paper-read skill)

When processing a new source (paper, article, reading notes):

1. Add the source file to `sources/papers/` or `sources/notes/`
2. Identify the relevant topic page(s) — update them rather than creating standalone entity pages by default
3. If the paper warrants depth, create an entity page in `entities/` following the deep-read template above
4. Create/update concept pages for cross-cutting ideas (only if they span multiple topics)
5. Create/update group pages if a notable lab is involved
6. Add `[[wikilinks]]` between new and existing pages
7. Append to `log.md`
8. Update `index.md`

### Query

When answering a question using the wiki:

1. Read `index.md` to identify candidate pages
2. Read relevant pages and synthesise across them
3. Cite via `[[wikilinks]]`
4. Promote valuable answers to `queries/` if worth preserving
5. Append to `log.md`

### Lint

Health checks for wiki consistency:

1. **Orphan detection**: every page must have at least one incoming `[[wikilink]]`
2. **Stale claims**: pages not reviewed in 60+ days (check `last_reviewed`)
3. **Index consistency**: all pages listed in `index.md`, no dead links
4. **Schema/path mismatches**: `type:` frontmatter must match the page's directory (a `type: topic` page in `concepts/` is a lint failure)
5. **Contradiction scan**: check synthesis pages for conflicting claims

---

## Relationship to Other Systems

- **Primary Obsidian vault** (e.g., `~/Documents/OneDrive/obs-notes`): the dashboard. Notes from `02 - Projects/<project>/` may be mirrored read-only into `vault-mirror/` via the vault-sync skill.
- **Project docs** (e.g., the repo root, `wiki/meta/`, `report/`): stay in their canonical locations. Wiki pages cross-reference but don't replace them.
- **Snakemake build outputs** (`build/`): not wiki territory. The wiki tracks the *thinking*; the snakemake DAG tracks the *running*.
