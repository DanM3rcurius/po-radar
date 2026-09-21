# Jev decision-point audit for Psyop Radar

Adapted from the attached "Find where Jev fits" framework: the environment audited here is this
pipeline rather than a Codex or Claude config. Rule: Jev decides; a generative model writes; code owns
thresholds and consequences.

## Classification of every candidate decision

| Decision | Class | Why |
|---|---|---|
| Is this text near-duplicate of that text | A deterministic | MinHash Jaccard is exact and free |
| Is this attributed wire copy | A deterministic | dateline and byline patterns |
| Is the feed dead | A deterministic | consecutive HTTP failures |
| Is this extraction boilerplate | A deterministic | line-level denylist and density |
| Does the text cite a verifiable primary source | B Jev | semantic, bounded, repeated per item |
| Is urgency manufactured beyond the facts | B Jev | pragmatic judgment, finite answer |
| Is the framing one-sided on a contested matter | B Jev | needs reading, not rules |
| Is the framing in-group vs out-group | B Jev | finite, semantic |
| Genre (reporting, opinion, satire, ...) | B Jev | 7 options, changes the cap |
| Dominant persuasion technique | B Jev | 14 options from SemEval |
| Dominant narrative move (Nimmo Ds) | B Jev | 6 options |
| Emotional engineering level | B Jev | ordered rubric |
| Verifiability level | B Jev | ordered rubric |
| Engineered likelihood | B Jev | ordered rubric, top-weight term |
| Write the forensic brief | C generative | prose |
| Steel-man the organic explanation | C generative | prose |
| Who is behind the narrative | D human | text alone cannot attribute; the tool refuses |
| Publish or share a score | D human | reputational consequence |

## Top 10 Jev integrations (ranked)

| # | Decision | Where today | Why not code | Why Jev | Type | Threshold | High conf | Low conf | Risk | Est. saving | Difficulty |
|---|---|---|---|---|---|---|---|---|---|---|---|
| 1 | engineered_likelihood | fusion top term | holistic reading | one bounded score | Score 0-4 | 0.6 | full weight | half / lexical-only cap | reversible, score only | 1 generative call per item avoided (est.) | done |
| 2 | verifiability | fusion | sourcing quality is semantic | ordered rubric | Score 0-4 | 0.6 | full | half | low | same | done |
| 3 | primary_source | fusion + falsifiers | regex misses paraphrased citations | noul | Noul | p≥0.8 or ≤0.2 | full | half | low | same | done |
| 4 | genre | opinion/satire cap | satire defeats rules | 7 options | Choice | 0.6 | cap applied | no cap | low | same | done |
| 5 | manufactured_urgency | pressure term | "breaking" is not always manufactured | noul | Noul | as 3 | full | half | low | same | done |
| 6 | one_sided | pressure term | needs counter-explanation awareness | noul | Noul | as 3 | full | half | medium (near 0.5 often) | same | done, watch calibration |
| 7 | tribal_signal | pressure term | idiom and sarcasm | noul | Noul | as 3 | full | half | low | same | done |
| 8 | technique | evidence only | 14-way semantic | choice | Choice | 0.6 | listed as evidence | omitted | low | same | done |
| 9 | nimmo_d | evidence only | narrative move | choice | Choice | 0.6 | listed | omitted | low | same | done |
| 10 | needs-review triage in `watch` | code counts uncertain answers | which uncertain item a human should read first | Score of "worth a human minute" | Score 0-2 | 0.65 | surface first | keep order | low | reviewer time (est.) | small, not built |

Usage numbers are not measured anywhere; every saving above is an estimate.

## Recommended first integration

Already wired: all ten questions in one batched call per item (`semantic.py`), gated in
`decisions/gate.py`, fused in `fusion.py`. Highest frequency (every scanned item), lowest risk (score
only, capped, reversible), clearest payoff (semantic mode versus lexical-only), easiest rollback (drop
`--cloud`), least exposure (evidence-only state). Verify with `poradar dryrun --cloud` on your machine;
this sandbox could not reach OpenRouter or TypeSafe.
