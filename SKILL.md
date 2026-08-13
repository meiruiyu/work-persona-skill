---
name: marvis-work-mbti
description: Safely scan explicitly authorized local work files, export privacy-safe research tables, score Marvis work MBTI, generate a 900x1200 PNG digital-clone report, and collect post-result validation feedback. Use when a user asks to generate, test, validate, or improve a Marvis 工作版 MBTI / 数字分身报告 from local computer data.
---

# Marvis Work MBTI

Run one user-visible skill with four internal modules: evidence collection, scoring, report generation, and beta validation. Keep raw scanning evidence, research exports, and visual products separate.

## Required Consent

Before scanning, show `references/privacy-policy.md` and obtain explicit scan scope. Ask a separate question: “是否同意生成脱敏研究数据表，供工作人格算法优化使用？”

- `research-consent=yes`: generate the report and privacy-safe research tables. Do not upload or transmit them automatically. Let the user download and voluntarily submit them to the campaign owner.
- `research-consent=no`: still generate the report and local tables marked `research_consent=no`; do not ask the user to submit them.

Never infer permission to scan a home directory, chats, mail, browser history, calendars, private photos, cloud drives, credentials, identity documents, contracts, or medical records.

## Mandatory Pipeline

Use the single pipeline command. Do not manually substitute its stages:

```bash
python scripts/run_pipeline.py \
  --root /authorized/Desktop \
  --root /authorized/Documents \
  --root /authorized/Downloads \
  --output-dir /workspace/output \
  --research-consent yes
```

The pipeline must produce all of these before the run is complete:

- `output/report.png`: **primary user-facing product**, the complete 900x1200 report image.
- `output/report.html`: fixed-size intermediate poster used only as the screenshot source.
- `output/data_collection.csv`: one privacy-safe row per participant/run for later sample merging and model analysis.
- `output/evidence_table.csv`: readable W/G evidence-detail table.
- `output/data_manifest.json`: consent and privacy manifest.
- `output/report.json`: structured report content.
- `output/internal/evidence.json` and `output/internal/score.json`: internal reproducibility files; do not present them as the data-collection table.

For `beta_blind`, the first pipeline stage is only `awaiting_feedback`, not complete. A beta user's run is complete only after `feedback.json` exists, `data_collection.csv` has been refreshed with the feedback labels, and `scripts/validate_products.py --require-feedback` passes.

The pipeline first fills the fixed `assets/report-template/` HTML/CSS with report data, then takes a deterministic Chromium screenshot at exactly 900×1200. `report.html` is an intermediate preview; `report.png` is the final report. Never ask an image model to redraw text, charts, or layout. The 16 source personality illustrations stay inside the Skill and must not be registered as user products.

The visual palette follows the bundled scarf image, not the MBTI camp:

- red/pink: ENFJ, ENTJ, ESFJ, ESTJ;
- green/mint: ENFP, INFP, INFJ, ISFJ, ISTJ;
- yellow: ESFP, ESTP, ISFP, ISTP;
- purple: ENTP, INTJ, INTP.

Only fill type, name, tagline, evidence, axes, stats, and the matching personality image. Do not redesign the template or choose new colors during a run.

The final poster must contain no AI-provider watermark, “AI generated” label, model logo, or external image resource. The bottom-right campaign tag is Marvis campaign copy, not an AI watermark. Run `scripts/validate_products.py` before registering products.

## Marvis Product Registration

After the pipeline succeeds:

1. Register `report.png`, `data_collection.csv`, `evidence_table.csv`, and `data_manifest.json` with `declare_products`.
2. Display `report.png` directly with `yyb-image-gallery` or the available image viewer.
3. Make both CSV files downloadable. Briefly explain that `data_collection.csv` is the one-row sample for later merging.
4. Do not register `report.html` as the final report; it is the deterministic screenshot source.
5. Do not register `assets/personalities/<TYPE>.png`; it is the source illustration, not the report.
6. Do not claim completion if `report.png`, either CSV, `data_manifest.json`, or required beta `feedback.json` is missing.

## Beta Feedback

In beta mode, score without psychological MBTI. Display `report.png` first, then ask for the validation fields required by `references/feedback-schema.json`. After the user answers, run one finalization command. It writes `feedback.json` and refreshes all research exports atomically:

```bash
python scripts/finalize_feedback.py \
  --evidence output/internal/evidence.json \
  --score output/internal/score.json \
  --config references/scoring-v1.json \
  --output-dir output \
  --research-consent yes \
  --psychological-type ENFJ \
  --psychological-type-source formal_test \
  --ei-fit 6 --sn-fit 5 --tf-fit 7 --jp-fit 4 \
  --overall-fit 6 --evidence-accuracy 6 --quirk-fun 5 \
  --privacy-comfort 7 --share-intent 6
```

Re-register the updated `data_collection.csv`, `evidence_table.csv`, `data_manifest.json`, and `feedback.json`. Psychological MBTI must be collected only after raw scoring and must never alter the current beta result. A beta run may be called complete only after the finalizer prints `status: complete`.

For the public comparison campaign, use `run_pipeline.py --mode campaign_compare --psychological-type ENFJ`. Never use comparison mode to evaluate beta accuracy.

## Output Meaning

- `data_collection.csv` includes M metadata, all 18 W metrics, G zero-weight candidates and aggregate distributions, four axis results, scoring/config versions, privacy audit, consent, and beta feedback when collected.
- `evidence_table.csv` lists each W/G field with evidence values, coverage, reliability, source lineage, and scoring weight.
- The tables contain no raw text, filenames, full paths, names, contacts, or recovered entities.
- One user's files stay local unless they explicitly submit them. Automatic multi-user aggregation requires a product-approved upload endpoint; do not invent one.

## Boundaries

- Raw first-200-character samples are transient and must be discarded after local classification.
- Missing metrics remain missing and leave the denominator; they never become reverse evidence.
- G fields have scoring weight zero and are used only for report quirks and later aggregate analysis.
- Application installation counts, uptime, late-night activity, and absolute clutter never determine letters.
- Generated output directories must be outside the skill package and excluded from the next scan.
- Rendering requires a local Chrome/Chromium executable. If unavailable, stop and report that `report.png` could not be rendered. Do not silently deliver HTML or invoke an image model.
