# The Research-Template Pattern

This document is the higher-level argument the template embodies. Read it if
you want to fork the template, or build your own version, or convince a
collaborator that this kind of integration is worth the setup cost.

## The problem

The LLM-research toolkit you actually have is a bag of disconnected tools — a
chatbot for brainstorming, a summariser for papers, an autocomplete for
writing, a Snakemake DAG for the analysis, a LaTeX repo for the manuscript, a
private Obsidian vault for half-formed thoughts.

Each is individually impressive. Nothing compounds.

You park an idea in a chat log on Monday, read a paper in a PDF reader on
Wednesday, draft a paragraph on Friday, run an analysis the following Tuesday,
and by the end of the month none of these pieces know the others exist. The
chat is gone. The paper notes are in some download folder. The draft has
drifted. The analysis output sits in `build/`, unconnected to the thinking
that produced it.

## The proposal

The template is one repo where the *thinking* (wiki + skills + state) and the
*running* (Snakemake + tests + report) sit next to each other and don't drift.

```
        ┌──────────────────────────────────────┐
        │            THE LOOP                  │
        │                                      │
        │   read → ingest → brainstorm →       │
        │   evaluate → analyse → write →       │
        │   reflect → read → ...               │
        │                                      │
        │   each arc powered by one skill      │
        │   each artefact in plain text        │
        │   the substrate binds them all       │
        └──────────────────────────────────────┘
```

Each arc is powered by a specific skill. The output of each arc is what the
next arc reads on startup. Because every skill reads and writes the same
substrate (`wiki/`, `research-state.yaml`, `events.jsonl`), reading on Monday
feeds brainstorming on Wednesday without a copy-paste. Reflection on Friday
can remind you on Monday what you decided the previous Friday. Nothing needs
to be carried in your head between sessions — if it was worth writing down,
it's already in a page the next skill will read.

## The three contracts

The pattern works because three contracts are honoured.

### Contract 1: Files as API

No servers, no databases beyond plain text. If `git` can version it, the
template can use it. Anything the machine knows is something the human can
open in an editor and read.

This is the thing that makes the substrate forkable. You can replace any one
tool with a better one as long as the replacement honours the file contract.
You can read the substrate without running the LLM. You can audit the
substrate by reading it. You can debug the substrate with `grep`.

### Contract 2: Bookkeeping is for machines

Humans abandon knowledge bases because maintaining cross-references is
boring. LLMs don't get bored.

The hook is non-negotiable. It is the thing the human cannot outsource to
discipline because the human is, in the end, the discipline that has been
failing all along. Every Write/Edit fires `research_hook.sh`. Every wiki page
that gets edited appends an event to `events.jsonl`. Every research evaluation
persisted to `wiki/research-evaluations/` shows up in next week's digest.

If the hook can't fire automatically (different platform, different runner),
the LLM calls it explicitly. The semantics are identical.

**Commits are the user's responsibility.** Agents never run `git commit`. The
user stays in control of when and how changes enter the repository.

### Contract 3: Narrative first, reference second

A research environment that only exposes reference documentation forces the
human to re-learn it every time they return. A narrative they can scan in
under two minutes on a Monday morning is what keeps the loop running.

This is why `research-session` exists: a single skill that reads the state,
the events tail, and the wiki staleness, then prints a briefing. The briefing
is the narrative. From the narrative the human chooses where to go, and the
session orchestrator routes them.

The reference documentation is here in `wiki/meta/docs/architecture.md` and in each
SKILL.md. The narrative is in `research-session`. Both exist; they don't
substitute for each other.

## The four layers

Reading top-to-bottom: each layer is more concrete, more modifiable, and more
forgiving than the one above it.

### Layer 0: The pipeline

Snakemake DAG. latexmk-rendered report. CI that re-runs
on every push. The pipeline is the artefact you ship to a journal: data in,
report out, with full provenance.

### Layer 1: The skills

Skills are the things the human types or signals. They guide the LLM through
phases that produce specific outputs in specific places. Each skill is
forkable: edit its SKILL.md and the next session uses the new version.

### Layer 2: The substrate

Plain text. Wiki pages with YAML frontmatter and `[[wikilinks]]`. State files
in YAML. Events in JSONL. The substrate is the contract — every skill reads
and writes it; everything else is layered on top.

### Layer 3: The bookkeeping daemon

Hooks. Auto-commit. Vault-sync. The things the human cannot remember to do
manually but cannot afford to skip.

## What this is not

- **Not a writing tool.** The template knows the wiki and the skills. It
  doesn't know whether a sentence is good. (For that, install
  `andrehuang/academic-writing-agents` or write your own writing-reviewer
  agent.)
- **Not an experiment manager.** The template tracks edits and ingestions and
  decisions, not training runs or hyperparameter sweeps. (For that, use
  Weights & Biases, MLflow, Snakemake's own benchmark mechanism, etc.)
- **Not a project manager.** It will not chase deadlines, send reminders, or
  enforce sprint discipline. (For that, the user's Obsidian Tasks plugin and
  Daily Notes work better than yet another LLM skill.)

## The portability claim

The pattern is what's portable. The implementation is one possible
expression of it.

If you swap OpenCode for Claude Code, the same SKILL.md files mostly work
(see `andrehuang/researcher-pack` for the Claude Code variant). If you swap
Snakemake for Make, the wiki keeps working. If you swap Obsidian for a plain
markdown editor, the wiki keeps working. If you replace the LLM entirely
with a sufficiently disciplined human, the wiki *still* keeps working — just
slower.

What is not portable is the bag of disconnected tools you started with. That
is the thing the pattern is meant to replace.
