---
name: weekly-review
description: >-
  Generate a weekly research digest — activity summary, knowledge growth, priorities.
  ACTIVATE EAGERLY when the user asks for a weekly review, research summary, progress
  check, or "what did I do this week". Reads events.jsonl, research-state.yaml, wiki, and
  vault-mirror to produce a structured report.
---

# Weekly Review — Research Digest

You produce a structured research digest that helps the researcher see their trajectory, identify gaps, and set priorities. This is reflection and planning, not just reporting.

## Activation Triggers (eager invocation)

ACTIVATE this skill when the user says:

- "weekly review", "research summary", "progress check"
- "what did I do this week?", "give me a digest", "what happened recently?"
- Or at the end of a Friday session as a wrap-up suggestion

## Context Loading

Read all sources in parallel:

1. **`events.jsonl`** — filter to the review period (default: last 7 days). Count events by type.
2. **`research-state.yaml`** — current wiki and session state.
3. **Wiki pages** — Glob all pages, check `last_reviewed` dates, count by type. Include `wiki/research-evaluations/`.
4. **Git log** — run `git log --oneline --since="7 days ago"` for commit activity.
5. **`wiki/.vault-mirror/`** — check timestamps for recently-changed mirrored notes.

If a date range is provided (e.g., "last 14 days", "March 1–7"), adjust the filter period accordingly. Default is 7 days from today.

## Report Structure

Present the digest in this format:

```
Weekly Research Digest — [Start Date] to [End Date]
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Activity Summary
  Papers ingested: [N] ([list titles if any])
  Wiki pages updated: [N]
  Research evaluations saved: [N] ([verdicts])
  Lit-search workspaces touched: [N]
  Experiments run: [N]
  Writing reviews: [N]
  Vault-mirror syncs: [N]
  Commits: [N]

Knowledge Growth
  Wiki: [total pages] pages ([+N new] this week, includes research-evaluations/)
  New concepts added: [list]
  Topics with most attention: [list]

Decisions made this week
  [list each research-evaluations/ page touched this week with its verdict,
   e.g. "agent-populations-for-polling — PURSUE",
        "simulators-as-survey-instruments — PARK (revisit: Q3 data release)"]
  [omit this block if empty]

Research Trajectory
  Active threads: [from recent events]
  Decisions made: [any PURSUE/PARK/KILL from research-companion]
  Dots connected: [any new connections identified]
  Questions answered: [any wiki queries promoted]

Health Checks
  Stale wiki pages (>60 days): [list]
  Orphan wiki pages: [list]
  Unresolved review findings: [count and file]
  Vault-mirror drift: [N notes changed in primary vault since last sync]
```

## Analysis Layer

After the report, add a brief analysis section (3–5 bullet points):

### Patterns

- What topics are getting the most attention? Is this aligned with priorities?
- Are there blind spots — topics that haven't been touched?
- Is the read → ingest → ideate flywheel running, or is one step being skipped?

### Connections

- Did any papers ingested this week connect to each other or to existing work?
- Are there research-evaluations whose revisit conditions are now met?

### Risks

- Is any project stuck or losing momentum?
- Are there stale wiki pages in areas of active research?
- Is the researcher learning broadly but not deeply, or vice versa?

### Parked ideas ready to revisit (soft heuristic)

Scan `wiki/research-evaluations/*.md` for any PARK verdict where:

- `revisit_conditions` in frontmatter is non-empty, AND
- the evaluation `date` is older than 30 days before today, AND
- the topic (or a close keyword) appears in events from the review period (e.g. a paper ingestion or wiki edit that touched the same area).

Flag these gently — "PARKed idea '[topic]' may be worth revisiting: condition was '[revisit_conditions]', and [event] this week touches that area." Do not auto-promote; this is a nudge.

## Priorities for Next Week

Based on the analysis, suggest 3–5 priorities ranked by impact:

```
Priorities for [Next Week Dates]
  1. [Priority] — [why it matters] — [specific action]
  2. ...
  3. ...
```

Priority categories:

- **Knowledge gaps**: Topics with low coverage that are needed for active work
- **Stale knowledge**: Wiki pages that need refreshing
- **Momentum**: Projects that need a push to stay on track
- **Opportunities**: New connections or ideas worth exploring
- **Maintenance**: Wiki lint, review findings, sync drift

## Optional Actions

After presenting the digest, offer:

1. **Graduate mature ideas** — "These IDEAS items seem ready to become wiki pages: [list]. Want to promote them?"
2. **Wiki lint** — "There are [N] health issues in the wiki. Want me to run a full lint and fix them?"
3. **Set focus for next week** — "Want to set a specific focus for next week? I'll adjust your `research-state.yaml` suggested actions."
4. **Sync from primary vault** — "[N] mirrored notes have drifted. Want to run vault-sync to refresh `wiki/.vault-mirror/`?"
5. **Share as event** — Emit a weekly review event:

```jsonl
{"ts":"...","type":"review:weekly","detail":"Week of [dates]: [N] papers, [N] decisions, [N] wiki updates","source":"weekly-review"}
```

## Orchestration Rules

- **Be honest about low activity.** If nothing happened this week, say so without judgement. "Quiet week — that's fine. Here's what might be worth picking up."
- **Spot patterns the researcher might miss.** You see the data across all tools — use that holistic view.
- **Don't moralise about streaks.** Report them factually. Some weeks are for thinking, not training.
- **Suggest, don't prescribe.** Present priorities as suggestions. The researcher knows their context better.
- **Keep it scannable.** The digest should be readable in 2 minutes. Use the structured format above.
