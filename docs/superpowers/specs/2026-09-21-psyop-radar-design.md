# Psyop Radar — Design Spec

Date: 2026-09-21 · Status: approved-by-mandate (user pre-authorized design → premortem → build → deploy) · Path: architectural (new project)

## 0. One-line

A local-first "spam filter for your brain": ingest news and social text, cluster it into narratives, and
rate each narrative's *engineered-ness* with evidence, using deterministic signals plus bounded Jev
decisions, while a local LLM (optional) writes the forensic brief. Code owns every threshold and consequence.

## 1. Source material distilled

| Source | What we take |
|---|---|
| Roemmele, "The Psyop AI Prompt Detector" (ReadMultiplex podcast, 2026-06-24) | Format: paste a news item, get a repeatable forensic read grounded in evidence and first principles "rather than emotion or authority". Members tier: a score per news event. Heuristic: identical talking points across outlets is a "humongous red flag". |
| Roemmele, Deep Truth Mode / Empirical Distrust Algorithm | Penalize high-authority, low-verifiability claims; up-weight primary, uneditable sources; steel-man fringe/dissenting explanations; audit suppression; demand falsifiability. |
| Chase Hughes, NCI Engineered Reality Scoring System (covered by Roemmele 2026-06-18) | Shape of the output: N categories each scored on a small ordinal scale, summed to 0–100 "engineered reality" likelihood. We use the shape, not his exact categories. |
| Jev audit prompt (attached screenshots) | Jev is a decision model, not a writing model. Choice / Score / Noul only. Generative model plans and writes; Jev decides where intelligence is spent; normal code owns permissions, thresholds, consequences. Never send secrets or personal data. |
| Detection literature (SemEval-2020 T11, SemEval-2023 T3, DISARM, ABCDE, Nimmo 4Ds, SIO/Graphika CIB indicators) | Label taxonomy and the deterministic/semantic split (§4). |

Caveat: the podcast transcript was not delivered with the task; the podcast, Substack, and X were egress-blocked from this sandbox. Distillation rests on indexed search snippets. Treat §1 as "close paraphrase", and re-verify against the actual transcript.

## 2. Product format

Three surfaces over one pipeline, all local:

1. **CLI** `poradar` — `scan` (one item: URL, file, or stdin text), `watch` (RSS/Atom feeds → SQLite → clusters), `report` (top narratives), `serve` (dashboard), `doctor` (which providers are live, no secrets printed), `dryrun` (one reversible Jev call with a canned fixture).
2. **Radar dashboard** — FastAPI serving a single-file HTML "radar screen". Each blip is a narrative cluster. Radius = Engineered Reality Score (ERS, center = 100), angle = topic sector, size = source count, glow = burst intensity. Click a blip → evidence panel: signals, Jev answers with probabilities, the forensic brief, and "what would falsify this".
3. **Prompt/MCP surface** — the same question bank shipped as JSON so Claude Code / Codex can run a scan through the community `evaluate` MCP tool interactively (docs/JEV_SETUP.md). This is where the attached audit framework plugs in.

## 3. Architecture

```
 feeds / URL / text
        │
        ▼
 ┌─────────────┐   ┌──────────────┐   ┌────────────────────┐   ┌────────────┐   ┌───────────────┐
 │ ingest      │──▶│ signals      │──▶│ decisions          │──▶│ fusion     │──▶│ brief (opt.)  │
 │ feedparser  │   │ deterministic│   │ Jev | Ollama | heur│   │ ERS 0–100  │   │ Ollama writer │
 │ readability │   │ MinHash/LSH  │   │ Choice/Score/Noul  │   │ code-owned │   │ or template   │
 └─────────────┘   └──────────────┘   └────────────────────┘   └────────────┘   └───────────────┘
        │                 │                     │                   │                  │
        └─────────────────┴─────────────────────┴───── SQLite (local) ─────────────────┘
                                                            │
                                              CLI · dashboard · JSON · MCP question bank
```

Packages (`src/poradar/`):

| Module | Responsibility | Depends on |
|---|---|---|
| `models.py` | `Item`, `Narrative`, `Signals`, `Decision`, `Verdict` (pydantic) | – |
| `ingest/` | `feeds.py` (RSS/Atom), `web.py` (URL → text, readability-lite), `text.py` (stdin/file) | httpx, feedparser |
| `signals/` | `dedup.py` (MinHash LSH clustering), `lexical.py` (VADER, absolutist/urgency lexicons, caps/exclaim), `attribution.py` (primary-source cues), `temporal.py` (burstiness) | datasketch, vaderSentiment |
| `decisions/` | `base.py` (typed primitives, done), `jev.py` (done), `ollama.py` (local structured-output emulation), `heuristic.py` (rules-only fallback), `router.py` (provider selection + confidence gate) | httpx |
| `questions.py` | The question bank: what we ask Jev, with criteria. Also exported as `questions.json` for MCP use. | decisions |
| `fusion.py` | Deterministic ERS 0–100, bands, evidence list, falsifiers | models |
| `brief.py` | Forensic brief: Ollama generative (if live) or template | httpx |
| `store.py` | SQLite persistence | sqlite3 |
| `cli.py` | Typer commands | all |
| `server.py` + `static/radar.html` | Dashboard | fastapi |

## 4. Signals: deterministic vs. semantic

Deterministic (code, always on, zero cost):

| Signal | Computation | Why it matters |
|---|---|---|
| `uniformity` | mean pairwise Jaccard of 3-shingles within a cluster (MinHash) | Roemmele's identical-talking-points red flag; CIB copypasta |
| `source_diversity` | unique registrable domains / items in cluster | narrative laundering shows low diversity or wire-only echo |
| `burst` | items in last 6h vs trailing 72h mean (z-like ratio) | synchronized pushes |
| `emotional_load` | VADER |compound| mean + intensity of top sentences | crude loaded-language proxy |
| `absolutism` | rate of "always/never/everyone/undeniable/no doubt/proven" per 100 words | thought-terminating certainty |
| `urgency` | rate of "breaking/urgent/act now/immediately/before it's too late" | manufactured urgency |
| `shout` | caps-word ratio + exclamation density | stylistic manipulation |
| `attribution_absence` | 1 − presence of {named org/person + said/according to/reported, direct quotes, document links, primary URL} | Empirical Distrust: high authority, low verifiability |
| `authority_words` | "experts say/officials/sources familiar/studies show" without a named entity nearby | anonymous authority |

Semantic (bounded; Jev primary; Ollama or heuristic fallback):

| id | Type | Question (instructions carry full meaning; ids are not sent) | Answers |
|---|---|---|---|
| `primary_source` | noul | Does the text cite a verifiable primary source (named document, dataset, on-record named witness, or official record) rather than only anonymous or secondary authority? | p(true) |
| `manufactured_urgency` | noul | Does the text press the reader to feel that immediate action or belief is required, beyond what the stated facts justify? | p(true) |
| `one_sided` | noul | Does the text present only one side of a contested matter while omitting or dismissing plausible counter-explanations? | p(true) |
| `tribal_signal` | noul | Does the text frame the matter as in-group versus out-group (us/them, patriots/traitors, etc.) rather than as a factual question? | p(true) |
| `genre` | choice | What kind of text is this? | reporting / opinion / satire / press_release / advertorial / social_post / other |
| `technique` | choice | Which persuasion technique is most prominent, if any? | loaded_language / name_calling / exaggeration / doubt / appeal_to_fear / flag_waving / causal_oversimplification / slogans / appeal_to_authority / black_and_white / thought_terminating_cliche / bandwagon / whataboutism_red_herring / none |
| `nimmo_d` | choice | Which narrative move dominates, if any? | dismiss / distort / distract / dismay / divide / none |
| `emotional_engineering` | score | How engineered is the emotional response? | 0 neutral report · 1 mild coloring · 2 clearly loaded · 3 designed to inflame · 4 pure outrage bait |
| `verifiability` | score | How verifiable are the central claims from the text alone? | 0 unverifiable assertions · 1 anonymous authority only · 2 named secondary sources · 3 named primary source · 4 primary source plus document/data link |
| `engineered_likelihood` | score | Overall, how much does this read like an engineered narrative rather than organic reporting? | 0 organic · 1 slightly shaped · 2 shaped · 3 likely engineered · 4 textbook engineered |

State sent to the decider: `{title, source_domain, published, excerpt (≤ 1500 chars), signals (numbers only)}`. No user identity, no URLs with tokens, no personal data. Never our own verdict.

## 5. Confidence gate (code-owned)

| Provider | Confidence measure | Accept | Uncertain | Reject |
|---|---|---|---|---|
| Jev noul | `abs(p − 0.5) × 2` | ≥ 0.6 | 0.3–0.6 | < 0.3 |
| Jev choice/score | `confidence` field | ≥ 0.6 | 0.35–0.6 | < 0.35 |
| Ollama (self-reported, poorly calibrated) | same fields, capped at 0.8 | ≥ 0.7 | 0.45–0.7 | < 0.45 |
| Heuristic | fixed 0.4 | never "accepts"; marks uncertain | – | – |

Accept → answer counts at full weight. Uncertain → counts at half weight and the item is flagged `needs_review`. Reject → answer ignored, counted as "unknown". Thresholds live in `config.py`, overridable by env `PORADAR_ACCEPT`, `PORADAR_UNCERTAIN`.

## 6. Fusion: Engineered Reality Score

ERS ∈ [0, 100] = 100 × Σ wᵢ · normalizedᵢ, where the terms (weights sum to 1):

| Term | Weight | Source |
|---|---|---|
| engineered_likelihood (score / 4) | 0.20 | semantic |
| emotional_engineering (score / 4) | 0.12 | semantic |
| 1 − verifiability/4 | 0.12 | semantic |
| manufactured_urgency, one_sided, tribal_signal (mean p) | 0.12 | semantic |
| 1 − primary_source p | 0.06 | semantic |
| uniformity | 0.14 | deterministic (cluster) |
| 1 − source_diversity | 0.06 | deterministic (cluster) |
| burst (capped) | 0.06 | deterministic (cluster) |
| lexical (emotional_load, absolutism, urgency, shout, attribution_absence, authority_words mean) | 0.12 | deterministic |

Semantic terms whose answer was rejected redistribute their weight to the remaining terms. Genre `satire` or `opinion` caps ERS at 60 and prefixes the band with "opinion:" (opinion is allowed to be one-sided; we flag, not condemn). Bands: 0–24 clear · 25–49 watch · 50–74 elevated · 75–100 high. Every verdict carries `evidence[]` (which signals fired, with values) and `falsifiers[]` (what observation would lower the score: "a named primary document", "independent outlets with different phrasing", etc.).

## 7. Generative layer (writer role)

`brief.py` writes the forensic read Roemmele's prompt produces: what the narrative claims, which signals fired, the strongest steel-man for the *organic* explanation, and what to check next. Backends: Ollama `/api/chat` with a fixed system prompt (default model `qwen3:8b`, overridable), or a deterministic template when Ollama is absent. The brief never changes the score.

## 8. Providers and routing

Order: `PORADAR_PROVIDER` env if set; else Jev if `TYPESAFE_API_KEY`/`OPENROUTER_API_KEY` present; else Ollama if `http://localhost:11434` answers; else heuristic. `doctor` prints which is live and why, never the key. Jev is called once per item with all 10 questions batched (one round-trip, ~100–500 ms, roughly a thousandth of a cent per item at listed pricing; estimate, not measured).

## 9. Guardrails

- Never attributes an actor. Output vocabulary is "engineered/organic", never "state X did this".
- Leads, not verdicts: every score ships with evidence and falsifiers; the UI labels scores as "signals to investigate".
- Keys env-only; `doctor` and logs redact; the Jev state is minimal and never includes user data.
- No telemetry, no cloud store; SQLite in `~/.poradar/` or `PORADAR_HOME`.
- Deterministic layer is always on and sufficient for a degraded-mode score; the app never blocks on a network provider.

## 10. Testing

- Unit: every signal on hand-written texts; fusion arithmetic; gate thresholds; Jev wire format and parsing (respx); Ollama emulation parsing; heuristic provider.
- Golden: `tests/fixtures/*.json` with contrasting items (wire report with named document vs. outrage-bait with anonymous "experts") and expected band.
- Integration: `poradar scan` on a fixture file with the heuristic provider, `poradar dryrun` against a mocked Jev.
- Live dry run (user's machine): `OPENROUTER_API_KEY=… poradar dryrun` → one call, prints answers, writes nothing.

## 11. Deployment

- Branch `claude/psyop-radar-design-deploy-lm1y4u`, pushed.
- `uv sync` / `pip install -e .` install; `poradar serve` local dashboard.
- A static demo of the radar screen (fixture data, no network) published as an artifact so the UI can be reviewed without installing anything.
- Rollback: delete the branch, or `pip uninstall poradar`; nothing touches global config unless the user runs the MCP setup themselves.

## 12. Out of scope (v0.1)

Account/network metadata signals (need platform APIs); image/video forensics; multilingual lexicons; fine-tuned local classifiers (SetFit/NLI) — the provider interface leaves room for them.
