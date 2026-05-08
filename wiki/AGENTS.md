# Wiki — Agent Quick Start

This file tells the LLM how to operate the wiki. The repo-root `AGENTS.md` has
project-wide context; this file is the wiki-specific protocol.

## First Steps

1. Read `wiki/wiki.schema.md` — it defines page types, structure, and all operations.
2. Read `wiki/index.md` — the content catalog.
3. Read `wiki/meta/principles/academic-writing.md` for prose quality.

## Fidelity Rule (read before any write)

**Wiki pages condense input. They never extrapolate from it.**

- Every claim on a wiki page must trace to a specific source: a paper in
  `wiki/sources/papers/`, a note in `wiki/.vault-mirror/`, a chat exchange, or
  an explicit user statement. If you cannot point to the source, do not write
  the claim.
- Do not "complete" half-formed notes from `wiki/.vault-mirror/`. Quote or
  paraphrase only what is literally there. Mark genuine gaps with
  `TODO: <what's missing>` rather than inventing.
- Do not generate synthesis ("X implies Y", "this generalises to Z") unless the
  source said so or the user explicitly asked. When the user asks for
  synthesis, label it: `> [!synthesis]` callout or a "Synthesis (LLM-generated)"
  heading.
- Prefer compression. Default to shorter pages. A 200-word topic update beats
  a 1500-word update built on speculation.

See the "Fidelity Discipline" section in the repo-root `AGENTS.md` for the full
rules and examples.

## Wiki Operations (Summary)

### Ingest a Source

1. Place the source document in `wiki/sources/papers/` (or `wiki/sources/notes/`).
2. Identify which topic page(s) in `wiki/topics/` the source belongs to.
3. Update those topic pages — add the source under "Key Papers & Approaches" with contributions and limitations.
4. Create/update concept pages in `wiki/concepts/` for cross-cutting ideas (only if they span multiple topics).
5. Create/update group pages in `wiki/groups/` if a notable lab is involved.
6. If the paper warrants a deep-read, create an entity page in `wiki/entities/` following the length-tiered template in `wiki.schema.md`.
7. Add `[[wikilinks]]` between new and existing pages.
8. Append to `wiki/log.md`.
9. Update `wiki/index.md`.

### Save a Research Evaluation

The canonical writer for research-evaluation pages is the
**research-companion** skill — it produces the verdict and dimension scores in
Phase 3 and hands them to the wiki. When invoked:

1. Write the page at `wiki/research-evaluations/YYYY-MM-DD-<topic-slug>.md` following the `research_evaluation` schema.
2. Wire it into the graph — add `[[wikilinks]]` from related topic/concept pages and vice versa.
3. Append an entry to `wiki/log.md` with the date, topic, and verdict.
4. Update `wiki/index.md` under the `## Research Evaluations` section.
5. Update `research-state.yaml` (`recent_research_evaluations`) with the verdict and revisit conditions so the next session briefing surfaces it.

### Query the Wiki

1. Read `wiki/index.md` to find relevant pages.
2. Read and synthesise across pages.
3. Offer to promote valuable answers to `wiki/queries/`.

### Lint

Run health checks: orphan pages, stale `last_reviewed` dates, index consistency,
schema/path mismatches, missing coverage. See `wiki.schema.md` → Lint.

## Vault-Mirror Awareness

`vault-mirror/` is a read-only mirror of project notes from the user's primary
Obsidian vault, populated by the **vault-sync** skill. Treat it as input
material for ingestion — surface insights from those notes when relevant, but
**never edit files inside `vault-mirror/`** (changes will be overwritten on the
next sync).

**Fidelity reminder.** Mirrored notes are the user's own private shorthand —
often fragmentary, exploratory, or contradictory. They are **evidence of what
the user has thought about**, not a prompt for the LLM to expand on the user's
behalf. When citing a mirrored note in a wiki page:

- Quote or paraphrase only what is literally there.
- Surface the note as an open thread (e.g., "user has flagged X as an open
  question, see `vault-mirror/<path>`") rather than inventing what the
  exploration would have concluded.
- If you need more content than the mirror provides, ask the user.
