# Premortem transcript: Psyop Radar (2026-09-21)

Frame: it is March 2027. Psyop Radar has failed and been abandoned. Nine investigators, one per failure reason, ran in parallel against the design spec (docs/superpowers/specs/2026-09-21-psyop-radar-design.md).

Context: what = local-first influence-operation radar (deterministic signals + Jev bounded decisions + optional local LLM brief; CLI, dashboard, MCP question bank). Who = the repo owner (a security tester running local models) and anyone who sees a screenshot. Success = a trustworthy radar that runs with zero keys, has a verified Jev path, and ships on the feature branch with a demo.

## Raw failure reasons

1. False positives on legitimate outrage and wire reporting; lexical signals dominate when semantic answers are rejected.
2. Jev leakage and calibration: deterministic signals in state bias Jev; nuanced nouls sit near 0.5 and flood `needs_review`.
3. Wire syndication defeats uniformity/diversity; boilerplate clusters; unpinned MinHash threshold.
4. No real local semantic path: Jev gated, Ollama emulation slow and uncalibrated, heuristic mode looks like a regex toy.
5. Ingestion rot: dead feeds, blocked fetches, nav/cookie text scored as articles, no ingestion health.
6. Source fidelity gap: design built from search snippets, not the transcript; question bank never reconciled.
7. Scope and abandonment: three surfaces, no hero loop, first run needs keys.
8. Privacy surprise: env-var presence silently promotes to cloud; stdin text leaves the machine; MCP setup bakes keys into client config.
9. Accusation machine: "HIGH (84)" next to an outlet name is an attribution; screenshots strip the evidence.

## Deep dives (condensed from the investigators)

### 1. False positives
Story: uniformity (0.14), source_diversity (0.06), burst (0.06) all fire on normal breaking wire news; when the confidence gate rejects the semantic answers, their weight redistributes onto lexical and cluster terms, so a grim, widely syndicated AP report on an atrocity scores 80.
Assumption: lexical intensity and cross-outlet duplication are manipulation tells, when serious organic news produces both.
Warning signs: golden false-positive rate on organic wire/war/opinion fixtures above 10%; semantic rejection rate above 40%.
Fix: rejected semantic weight redistributes only among accepted semantic terms; with no accepted semantic term, cap the band at "watch" and set needs_review; exclude attributed wire copies from uniformity and diversity.

### 2. Jev leakage and calibration
Story: sending signal numbers in state is a partial verdict; Jev's `engineered_likelihood` echoes the lexical block, then fusion double-counts it. Nuanced nouls cluster at 0.4 to 0.6 and everything becomes `needs_review`.
Assumption: numbers as context are neutral; noul confidence near 0.5 reflects question difficulty rather than state contents.
Warning signs: correlation between lexical composite and engineered_likelihood above 0.7 on goldens; needs_review above 15 to 20% on a real feed run; more than half of one_sided/tribal_signal values in [0.4, 0.6].
Fix: send only {title, source_domain, published, excerpt}; deterministic and semantic evidence meet only in fusion. Add a calibration check in dryrun/goldens: a noul stuck in [0.45, 0.55] on most fixtures is a mis-specified question to be reworded, not gated.

### 3. Wire syndication
Story: AP/Reuters copy is verbatim across dozens of domains, so wire stories hit uniformity 1.0 and look like laundering; a single MinHash knob does two jobs and boilerplate creates spurious matches.
Assumption: textual near-duplication across outlets is evidence of coordination.
Warning signs: more than 20% of elevated/high verdicts carry a wire byline; Jaccard distribution bimodal at the extremes only.
Fix: strip boilerplate before shingling; detect wire attribution (dateline patterns, bylines, copyright footers) and tag `attributed_syndication`; exclude those from uniformity/diversity; pin the threshold with golden duplicate and unrelated pairs.

### 4. No local semantic path
Story: with no key, every scan falls to Ollama; self-reported confidence capped at 0.8 against an accept threshold of 0.7 lands nearly everything uncertain; ten sequential calls make scan take 30 to 60 s; heuristic mode emits full-looking verdicts.
Assumption: self-reported confidence from a small local model is usable, and ten sequential questions are fine without measuring latency.
Warning signs: uncertain/unknown share on Ollama far above Jev; p95 scan wall-clock; confidence spike at the cap value.
Fix: one batched Ollama call with one JSON schema; content-hash cache; honest "lexical-only mode" label when no semantic provider answered.

### 5. Ingestion rot
Story: feeds die or paywall, fetches get 403 or JS shells, readability-lite extracts nav and cookie text, uniformity spikes on shared footers, the dashboard renders confident blips from junk.
Assumption: fetch plus extraction is a solved low-variance step that can run unattended.
Warning signs: fleet-wide short excerpts; uniformity spikes across unrelated topics; feed success trending down.
Fix: per-feed health (last success, consecutive failures, dead flag) in doctor and report; minimum text length and boilerplate-density rejection tagged `ingest_rejected`; prefer feed-provided content over scraping; dim low-confidence-ingestion blips.

### 6. Source fidelity
Story: the caveat "re-verify against the transcript" was a comment, not a gate; the snippet-derived bank hardened into weights and the user found it off-target.
Assumption: a documented caveat is a safeguard.
Warning signs: bank hard-coded; no CLI path to compare or replace it.
Fix: questions.json is the single source of truth the code loads; `poradar questions` commands to show and import; docs/RECONCILE.md checklist; "provisional" banner until reconciled.

### 7. Scope and abandonment
Story: three surfaces built at once, dashboard breaks on first real data, user never gets past key setup, no wow moment in 60 seconds.
Assumption: breadth equals value; fixture-validated parts compose safely.
Warning signs: no zero-config scan in the deployment story; doctor and dryrun documented before scan.
Fix: hero loop is `poradar scan <file|url|->` with zero keys, under 2 s, deterministic ERS plus evidence plus template brief; everything else is secondary and must run against real data before it counts.

### 8. Privacy surprise
Story: a key present for unrelated work silently promotes scans to cloud; stdin-pasted private text goes to Jev; MCP setup writes the key into client config.
Assumption: an env var being set equals the user choosing cloud mode.
Warning signs: no --cloud flag; doctor is opt-in; stdin has no distinct trust tier.
Fix: default provider is local/heuristic; cloud requires `--cloud` or PORADAR_ALLOW_CLOUD=1; an egress line prints before any network call; stdin never leaves the machine without `--allow-stdin-egress`.

### 9. Accusation machine
Story: a blip's score next to an outlet name is the artifact that circulates; guardrail text lives one click away; Hamilton 68 pattern.
Assumption: guardrail vocabulary present somewhere in the system is enough.
Warning signs: screenshots of scores without evidence; "how do I get my outlet's score down" requests.
Fix: score is inseparable from evidence and falsifiers in every surface (fail closed in JSON); blip label carries the top falsifier; blips keyed by narrative, not outlet; every export burns in "not an attribution of intent or actor".

## Synthesis

Most likely failure: 1 plus 3 together. The deterministic cluster terms reward exactly what routine wire journalism produces, and the gate's redistribution rule turns every semantic rejection into more lexical weight. The tool's top blips would be AP stories within the first day of a real feed run.

Most dangerous failure: 9, then 8. A screenshot of a score beside an outlet name is an attribution regardless of the disclaimer, and a "local-first" tool that quietly sends pasted text to a cloud burns the one user it has. Both are cheap to prevent now and impossible to walk back later.

Hidden assumption: that the semantic layer will usually be present. The design treated Jev/Ollama as the normal path and heuristics as an edge case, so every fusion rule leaned on semantic answers being there. In practice the zero-key path is the common path, so the deterministic layer has to be honest and useful on its own, and the score must say which layers actually answered.

Revised plan (each item maps to a failure number):
- Hero loop first: `poradar scan` with zero keys, under 2 s, prints ERS band, evidence, falsifiers, and a template brief. (7)
- Provider default is local; cloud is opt-in via `--cloud`/PORADAR_ALLOW_CLOUD=1; egress line before any call; stdin never sent to cloud without a second flag. (8)
- Jev state is {title, source_domain, published, excerpt} only. (2)
- Fusion: rejected semantic weight redistributes only among accepted semantic terms; no accepted semantic answer caps the band at "watch" and labels the output "lexical-only". (1, 4)
- Wire attribution detector; attributed syndication excluded from uniformity and diversity; boilerplate stripped before shingling; MinHash threshold pinned by golden pairs. (3)
- Ollama path: one batched call, one JSON schema, content-hash cache. (4)
- Ingestion health in doctor and report; minimum-text and boilerplate rejection; feed content preferred over scraping. (5)
- questions.json is the loaded source of truth, with show/import commands and docs/RECONCILE.md. (6)
- Bands renamed to signal-density language; output fails closed without evidence and falsifiers; blips keyed by narrative; attribution disclaimer burned into every export. (9)

Pre-launch checklist:
1. Golden set includes an attributed wire report on a grave event, an opinion column, satire, and an outrage-bait post; the wire report must land in "clear" or "watch" in lexical-only mode.
2. `poradar scan tests/fixtures/*.txt` runs with no env vars and no network in under 2 s each.
3. A unit test asserts the Jev request body contains no `signals` key.
4. A unit test asserts that with all semantic answers rejected the band is at most "watch" and the output carries `mode: lexical-only`.
5. A unit test asserts every serialized result has non-empty evidence and falsifiers, and that the disclaimer string is present.
