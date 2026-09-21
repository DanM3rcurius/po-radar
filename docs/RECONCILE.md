# Reconcile the question bank with the source transcript

Status (2026-09-21): **partially reconciled.** The Multiplex transcript was delivered in chat and
uploaded to trunk as `psyopradar-transcript-multiplex`, but both copies stop at exactly 20,000
characters, mid-sentence ("...they map directl"). Everything the excerpt specifies is now in the
app; the parts after the cut are not.

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

## Still to reconcile (after the cut)

1. The names of all 20 NCI categories and how they map to Cialdini's principles. Our worksheet
   composes 20 rows from the elements above; when the real list is available, rename or replace rows
   in `worksheet.py` to match, keeping the 1-5 scale.
2. Any interpretive guidance the source gives per category (what a 3 looks like versus a 5).
3. Whether the source scores per claim or per narrative. The app scores per item and rolls up per
   narrative.

## How to finish

1. Put the full transcript in a local file (it stays on your machine).
2. List the 20 categories. For each, mark: already a row, a row under another name, or missing.
3. Edit `worksheet.py` row names and the `questions.json` instructions; bump `"version"` to
   `"1.0-reconciled"`; `poradar questions import my_questions.json`.
4. Re-run `poradar scan tests/fixtures/*.txt`; the attributed wire report must stay in quiet or watch.
