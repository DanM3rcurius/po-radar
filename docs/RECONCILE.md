# Reconcile the question bank with the source transcript

Status (2026-09-21, second pass): **reconciled with everything the transcript specifies.** The full
transcript on trunk (`psyopradar-transcript-multiplex`, 30.5 kB) describes the tool's shape, bands,
discipline, and psychology, but it never enumerates the 20 category names. The worksheet therefore
composes 20 rows from the elements the transcript names; rename rows when the canonical list is in hand.

## What the transcript specifies and where it landed

| Transcript element | Where it lives |
|---|---|
| NCI PsyOps Identification Tool v8.3 (Chase Hughes): 20 categories, 1 = absent, 5 = overwhelming, 0-100 | `worksheet.py`, `Worksheet` in `models.py`, printed by `poradar scan` |
| Bands: 0-25 low/organic, 26-50 moderate/sensationalism, 51-75 strong engineered elements, 76-100 overwhelming coordination indicator | `band_for` and `NCI_READINGS` in `models.py`; `nci_reading` on every result |
| Receipts: point to the specific sentence, temporal datum, structural anomaly | `receipts.py`; `receipt` on every worksheet row; `quote` on evidence |
| Conflicting sources required (left, right, international) | source-diversity row; the standing falsifier on single-item scans; `docs/JEV_SETUP.md` prompt |
| Prove your own score wrong | `falsifiers[]` on every result; `organic_explanation_strength` question; `lower_it` on every row |
| Timing (Friday-evening dump; coincides with a competing event) | `timing_dump` (deterministic window) plus a human row for the competing-event check |
| Historical parallels (rhetorical structure, emotional pacing of documented campaigns) | `historical_parallel` choice question |
| White / gray / black propaganda | `source_transparency` choice question |
| Amygdala hijack, System 1 vs System 2 | `emotional_engineering`, `manufactured_urgency`, emotional-hijack row |
| Illusory truth / processing fluency (repetition) | within-text `repetition` row plus cross-outlet uniformity |
| Prospect theory / loss framing | `loss_framing` question plus the `loss_ratio` lexicon |
| Social identity theory | `tribal_signal` question plus the tribal lexicon receipt |
| Cialdini's principles | `cialdini_lever` choice question |
| Amplification by bot networks | human row (needs platform data) |
| Cialdini mapping: authority ("leading experts warn"), social proof, urgency | `cialdini_lever` options plus the anonymous-authority and urgency rows |
| Continued influence effect (debunks do not erase the payload) | brief line; the dated log keeps the retraction on record |
| Cognitive load (a tired brain defaults to System 1; use an external structured tool) | the worksheet itself; `needs_review` flag |
| Habitual logging: dated entries with claim, summary, score, verdict; calibrated intuition over months | `poradar log add|show|export`; `log` table in the store |
| Deep Truth Mode: define the ontology of loaded terms before arguing; refuse binary conclusions | `undefined_terms` question; `define_first` on every result; `black_and_white` technique |

## Still open

1. The canonical names of the 20 NCI categories (not in the transcript). When available, rename or
   replace rows in `worksheet.py`, keeping the 1-5 scale.
2. Per-category guidance on what a 3 looks like versus a 5 (not in the transcript).
3. The transcript ends mid-sentence ("...the tool and the neuroscience."); if there is a closing
   section, send it.

## How to finish

1. Put the full transcript in a local file (it stays on your machine).
2. List the 20 categories. For each, mark: already a row, a row under another name, or missing.
3. Edit `worksheet.py` row names and the `questions.json` instructions; bump `"version"` to
   `"1.0-reconciled"`; `poradar questions import my_questions.json`.
4. Re-run `poradar scan tests/fixtures/*.txt`; the attributed wire report must stay in quiet or watch.
