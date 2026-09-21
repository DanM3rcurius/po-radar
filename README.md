# Psyop Radar (`poradar`)

A local-first "spam filter for your brain". Paste a news item, a URL, or a feed list; get a repeatable
forensic read grounded in evidence rather than emotion or authority, with a signal-density score, the
evidence behind it, and what would lower it.

**Division of labor (the rule this repo is built on):** a generative model writes the brief, Jev
(TypeSafe's System One decision model) or a local model answers bounded Choice / Score / Noul questions,
and ordinary code owns every threshold, permission, and consequence.

> Signals to investigate, not an attribution of intent or actor.

## 60-second start (zero keys, no network)

```sh
uv venv && uv pip install -e ".[dev]"      # or: pip install -e ".[dev]"
poradar scan tests/fixtures/outrage_bait.txt
poradar scan tests/fixtures/wire_report.txt
poradar scan -  < some_article.txt         # stdin never leaves the machine
poradar doctor                             # what is live, what would leave the machine
```

Without a local model or a Jev key, results run in **lexical-only mode**: deterministic signals only,
score capped at "watch", labeled as such. That is honest degraded mode, not a verdict.

## Add a semantic layer

- **Local:** run [Ollama](https://ollama.com) with a small instruct model (`ollama pull qwen3:8b`).
  `poradar` detects it and answers all ten questions in one structured-output call. Confidence is
  self-reported and capped at 0.8.
- **Jev (cloud, opt-in):** set `OPENROUTER_API_KEY` or `TYPESAFE_API_KEY` in your shell, then pass
  `--cloud` (or `PORADAR_ALLOW_CLOUD=1`). Every run prints an `egress:` line before anything is sent.
  Jev receives only `{title, source_domain, published, excerpt}`, never signal numbers or personal data.
  Verify with one reversible call: `poradar dryrun --cloud`.

See `docs/JEV_SETUP.md` for wiring Jev into Codex and Claude Code as an MCP tool.

## Surfaces

| Command | What it does |
|---|---|
| `poradar scan <file\|url\|->` | The hero loop. One item, full read, under 2 s in lexical-only mode. |
| `poradar watch [feeds...]` | Poll RSS/Atom into `~/.poradar/radar.sqlite`, cluster into narratives, score. Feed health tracked. |
| `poradar report` | Top narratives and feed health from the store. |
| `poradar serve` | Local radar dashboard at http://127.0.0.1:8642 (localhost only). |
| `poradar doctor` | Providers, routes, bank, store. Never prints secrets. |
| `poradar dryrun [--cloud]` | One decision call on a bundled fixture. Writes nothing. |
| `poradar log add\|show\|export` | The habitual log the NCI method insists on: dated entries with claim, score, and verdict, so patterns show up over months. |
| `poradar questions show\|import\|reset` | The question bank is data; replace it after reconciling with the source transcript (`docs/RECONCILE.md`). |

## How the score works

Engineered Reality Score (ERS, 0 to 100) fuses two independent evidence blocks in `fusion.py`:

- **Deterministic (always on):** cross-source phrasing uniformity (attributed wire copy excluded), source
  diversity, burstiness, and a lexical composite (emotional load, absolutism, urgency, shouting, missing
  attribution, anonymous authority).
- **Semantic (when a decider is live):** ten bounded questions from `src/poradar/questions.json`
  (primary source, manufactured urgency, one-sidedness, tribal framing, genre, dominant technique,
  narrative move, emotional engineering, verifiability, engineered likelihood), each gated by confidence.

Every result also carries an NCI-style 20-row worksheet (1 to 5 per row, receipts on each row, human-only
rows labeled) and a Deep Truth "define first" list of loaded terms the text never defines.

Rejected semantic answers never push weight onto lexical terms. Opinion and satire cap at 60. Every
result fails closed without evidence and falsifiers. Bands: quiet, watch, dense, saturated.

## Layout

```
src/poradar/
  models.py       shared contract (Item, signals, RadarResult)
  questions.json  the provisional question bank (data)
  signals/        deterministic layer: boilerplate, syndication, lexical, dedup, temporal, cluster
  decisions/      Choice/Score/Noul primitives; providers: jev, ollama, stub; gate; router
  semantic.py     ask, gate, cache
  fusion.py       ERS, bands, evidence, falsifiers
  brief.py        the writer role (local model or template)
  ingest/         text, url, feeds with ingestion-health rejection
  pipeline.py     orchestration
  cli.py          typer commands
  server.py + static/radar.html   dashboard
docs/superpowers/specs/   design spec (+ premortem revisions)
docs/premortem/           premortem report and transcript
docs/demo/                static radar demo with sample data
```

## Tests

```sh
.venv/bin/python -m pytest -q
.venv/bin/ruff check src tests
```

## License

Apache-2.0 (see LICENSE).
