---
name: marvis-work-mbti-skill
description: 基于用户主动授权的本地工作目录与 Marvis 本地知识库的图片/应用聚合信息，提取不含原文、文件名和完整路径的工作行为统计，判定工作版 MBTI，并生成一张 1800×2400 的高清人格报告图片。内测模式还会在报告展示后征得用户同意，生成本地脱敏数据表和反馈文件，用于优化评分规则；不会自动上传或外发任何数据。当用户要求生成、测试或优化 Marvis 工作版 MBTI、工作人格或数字分身报告时使用。
license: MIT
metadata:
  author: meiruiyu
  version: 1.9.5
---

# Marvis 工作版 MBTI

Run one user-visible skill with four internal modules: evidence collection, scoring, report generation, and beta validation. Keep raw scanning evidence, research exports, and visual products separate.

Requires Marvis desktop, Python 3, and a local Chrome or Chromium browser. Run locally and analyze only directories explicitly authorized by the user.

## Required Consent

Before scanning, show `references/privacy-policy.md`. Scan authorization is always one directory-scope single-choice selector. Use radio buttons, chips, or a menu; never use checkboxes, multi-select lists, free-form questions, or an `其他` text box. If structured controls are unavailable, show the same A/B/C options as a numbered list and ask the user to reply with one letter only; never fall back to “你想扫描哪里？”.

First show exactly one directory-scope selector with three options:

- `A 常用工作区（推荐）` — scan Desktop + Documents. Use this as the default recommendation for most users. It has the best signal-to-noise ratio and covers file structure, naming habits, content/project themes, and work rhythm.
- `B 完整工作足迹` — scan Desktop + Documents + Downloads. Use when the user often leaves work attachments, received files, or web downloads in Downloads. It gives more data but also more noise.
- `C 自选工作文件夹` — open the native folder picker and allow the user to select 1–3 work folders. Use for privacy-sensitive users or users whose work files live in fixed project folders. A narrow or single-project scope may still produce a report, but confidence may be lower.

Scope mapping is fixed:

- A maps to `--scope-preset work-core` and scans `~/Desktop` + `~/Documents`.
- B maps to `--scope-preset work-triad` and scans `~/Desktop` + `~/Documents` + `~/Downloads`.
- C maps to `--scope-preset custom`; invoke the system folder picker and pass exactly the selected 1–3 folders with repeated `--root` arguments.

Do not ask the user to choose a time range. The Skill always analyzes files modified in the latest 365 days, matching the scoring window: 0–90 days weight 1.0, 91–180 days weight 0.6, and 181–365 days weight 0.3. Files older than 365 days are excluded. Report activity statistics such as peak hour and late-night share continue to use only the latest 180 days.

Do not ask the user to type a path or a folder name. Only after `C 自选工作文件夹` may the native folder picker appear. The user should choose folders visually in the system picker. Store the selected directory option and fixed 365-day window in evidence metadata for beta analysis.

Use Marvis local knowledge base aggregates without adding another user-burden step:

- File/project themes are not full-document reading. Use filenames, extensions, folder context, and at most 300 recent work documents' first 200 characters for transient local classification. Discard the sampled text immediately and retain only labels/counts/ratios.
- If Marvis has already recognized image categories inside the authorized file scope, export only category counts such as screenshot, chart, table, code screenshot, poster, design draft, whiteboard, moodboard, document scan, ticket, travel, selfie, etc. Do not export raw images, OCR text, faces, identities, locations, or private photo-library contents. Work-image categories may participate as low-weight S/N and T/F evidence; selfie/travel/life categories stay gray-list only.
- If Marvis has already recognized installed applications, export app names, broad categories, and installed counts for the research table only. Application installation data never affects the current letters. Do not ask the user to enable Full Disk Access for this default flow.
- If app usage strength or recent-90-day active days are blocked by macOS privacy/TCC, skip them silently and keep E4/T4 missing. Do not ask users to open System Settings or grant Full Disk Access unless the campaign owner explicitly starts a separate opt-in enhanced test.

Then show a separate research selector:

- `A 同意生成脱敏研究数据表，供算法优化；文件只保存在本机，由我决定是否提交`
- `B 仅生成报告，不参与研究`

Before running the pipeline, read the current signed-in Marvis account nickname/display name directly from the account session or profile context. Pass that exact current-account value to `--display-name`; the poster title is always `<current account nickname>的工作版MBTI`.

Do not ask the user to confirm the nickname, choose where to place it, or enter it again. Never hard-code `Angeline` or reuse a previous participant's name. If the account API unexpectedly returns an empty value, use `小马同学` for that run rather than asking another question. The nickname is used only in `report.json`, `report.html`, and `report.png`; never add it to the anonymized research CSV files.

- `research-consent=yes`: generate the report and privacy-safe research tables. Do not upload or transmit them automatically. Let the user download and voluntarily submit them to the campaign owner.
- `research-consent=no`: still generate the report and local tables marked `research_consent=no`; do not ask the user to submit them.

Never infer permission to scan a home directory, chats, mail, browser history, calendars, private photos, cloud drives, credentials, identity documents, contracts, or medical records.

## Mandatory Pipeline

Use the single pipeline command. Do not manually substitute its stages:

```bash
python scripts/run_pipeline.py \
  --scope-preset work-core \
  --lookback-days 365 \
  --output-dir /workspace/output \
  --research-consent yes \
  --display-name "<current signed-in Marvis account nickname>"
```

When Marvis local aggregates are available, write them under the run output directory and pass them into the same pipeline:

```bash
python scripts/run_pipeline.py \
  --scope-preset work-core \
  --lookback-days 365 \
  --output-dir /workspace/output \
  --research-consent yes \
  --display-name "<current signed-in Marvis account nickname>" \
  --image-summary-json /workspace/output/internal/marvis_image_summary.json \
  --app-inventory-json /workspace/output/internal/marvis_app_inventory.json
```

The pipeline must produce all of these before the run is complete:

- `output/report.png`: **primary user-facing product**, the complete 1800x2400 high-resolution report image.
- `output/report.html`: fixed-size intermediate poster used only as the screenshot source.
- `output/data_collection.csv`: one privacy-safe row per participant/run for later sample merging and model analysis.
- `output/evidence_table.csv`: readable W/G evidence-detail table.
- `output/data_manifest.json`: consent and privacy manifest.
- `output/work_mbti_return_bundle.zip`: participant return bundle containing the poster and privacy-safe research/feedback files.
- `output/report.json`: structured report content.
- `output/internal/evidence.json` and `output/internal/score.json`: internal reproducibility files; do not present them as the data-collection table.

For `beta_blind`, the first pipeline stage is only `awaiting_feedback`, not complete. A beta user's run is complete only after `feedback.json` exists, `data_collection.csv` has been refreshed with the feedback labels, and `scripts/validate_products.py --require-feedback` passes.

The pipeline first fills the fixed 900×1200 CSS canvas in `assets/report-template/`, then takes a deterministic 2× Chromium screenshot at exactly 1800×2400. `report.html` is an intermediate preview; `report.png` is the high-resolution final report. Never ask an image model to redraw text, charts, or layout. The 16 transparent source personality illustrations stay inside the Skill and must not be registered as user products.

Visual golden reference: `work-mbti-output/16-personality-posters/` is the approved 16-type poster reference set. It contains QA examples generated from the shared runtime template, not 16 separate runtime templates and not 16 static user reports. Use those posters as the target visual effect when validating layout, spacing, hierarchy, palette, and image scale. Runtime output must regenerate a fresh `output/report.png` from the current user's evidence and account name; never copy `16-personality-posters/<TYPE>/report.png`, `report.html`, or `report.json` as the user's report.

The visual palette follows the bundled scarf image, not the MBTI camp:

- red/pink: ENFJ, ENTJ, ESFJ, ESTJ;
- green/mint: ENFP, INFP, INFJ, ISFJ, ISTJ;
- yellow: ESFP, ESTP, ISFP, ISTP;
- purple: ENTP, INTJ, INTP.

Only fill display name, type, name, tagline, three plain-language habits, compact axes, stats, and the matching personality image. Do not redesign the template, choose new colors, move sections, add icons, add animations, or change the information hierarchy during a run.

The bundled template defines one shared hierarchy for all 16 types and all four palettes. Render the account title as a compact bold byline, capped at 36px with automatic shrinking for long names, using the same dark text color as the personality headline. Make the MBTI code, type name, and tagline the bold primary visual group; keep the enlarged transparent personality image beside them. The four computer-stat cards and four axis cards must retain their visible borders and enlarged numbers; the bottom-left privacy mark must remain readable at poster scale. Do not apply type-specific layout overrides.

The 16 golden posters lock the desired structure:

- top byline: `<current account nickname>的工作版MBTI`, centered, bold, same dark theme color as the main type line;
- primary visual group: `<TYPE> <人格名称>` plus the tagline, large, bold, left-aligned, with the personality illustration on the right and away from the byline;
- middle evidence group: `三大习惯 · 你的电脑说的`, three plain-language habits with exact data evidence, no internal metric terms;
- data cards: four large bordered cards using `份工作足迹 / 个项目线索 / 你的高产时段 / 深夜产出占比`;
- compact axes: four bordered axis cards under `四维小结`, visible but secondary to the type headline and data cards;
- footer: bottom-left Marvis local-knowledge privacy mark only.

For all 16 types, generated posters should differ only by current user data, type/name/tagline, three habits, scores, the matching transparent personality image, and the selected red/green/yellow/purple palette. Keep the golden-reference rhythm and proportions.

Poster copy rules:

- Title: `<current signed-in Marvis account nickname>的工作版MBTI`; populate it automatically and never ask the user to confirm it.
- Section title: `三大习惯 · 你的电脑说的`.
- Exactly three habits are generated by `scripts/build_report.py`; do not improvise or rewrite them during a run.
- Every habit must retain at least one exact count, ratio, time range, or detected fact. Never invent a number, turn file count into task count, or imply that a proxy is a verified work record.
- Write each habit in conversational, shareable Chinese: a short punchy title plus one or two plain sentences. Use a light joke where it helps, but never mock, shame, diagnose, or insult the user.
- The three habits must collectively show visible work effort: recent output, projects still moving, recurring delivery, careful revision, late-night work, weekend work, or preparation for incoming requests. The intended takeaway is “这个人工作很认真、很勤奋”, supported by the computer evidence rather than empty praise.
- Never expose internal metric IDs or professional terms such as “聚类”, “语义”, “加权”, “置信度”, “指标”, “样本”, “活跃会话”, “时间戳”, “双边占比”, “收敛链”, “KL 距离”, or “加权贡献” on the poster.
- The four stats are `份工作足迹 / 个项目线索 / 你的高产时段 / 深夜产出占比`. Time stats use only recent 180-day project-hour sessions after bulk timestamp removal. If coverage or peak separation is insufficient, display `样本不足` rather than inventing a result.
- Footer appears only at bottom left: `Marvis本地知识库 · 你的文件管家` and `只读不改 · 敏感内容自动跳过 · 端侧模型生成不上传`.
- Do not place a campaign hashtag or any AI watermark on the poster.

The final poster must contain no AI-provider watermark, “AI generated” label, model logo, campaign hashtag, or external image resource. Run `scripts/validate_products.py` before registering products.

## Marvis Product Registration

After the pipeline succeeds:

1. Register `report.png` and `work_mbti_return_bundle.zip` with `declare_products`.
2. Display `report.png` directly with `yyb-image-gallery` or the available image viewer.
3. Tell beta users exactly: `请回传“work_mbti_return_bundle.zip”这个文件夹给Angeline。`
4. Do not register `report.html` as the final report; it is the deterministic screenshot source.
5. Do not register `assets/personalities/<TYPE>.png`; it is the source illustration, not the report.
6. Do not register anything from `work-mbti-output/16-personality-posters/`; that folder is a QA/reference sample set, not the current user's product.
7. Do not ask users to individually download or understand `data_collection.csv`, `evidence_table.csv`, `data_manifest.json`, `feedback.json`, `report.html`, `report.json`, or `internal/`.
8. Do not claim completion if `report.png`, `work_mbti_return_bundle.zip`, either CSV, `data_manifest.json`, or required beta `feedback.json` is missing.

## Beta Feedback

In beta mode, score without psychological MBTI. Display `report.png` first, then collect validation feedback with structured controls only. Do not ask the user to type a long list of 1-7 scores, paste command parameters, or answer all fields in one free-form text block.

Feedback UX must be simple:

1. Ask for the user's psychological/life MBTI with one selector only. Use 17 options: `ISTJ / ISFJ / INFJ / INTJ / ISTP / ISFP / INFP / INTP / ESTP / ESFP / ENFP / ENTP / ESTJ / ESFJ / ENFJ / ENTJ / 没测过/不确定`. Show this helper line near the selector: `可参考测试：https://www.16personalities.com/ch`. Do not ask a separate source question; write `psychological_type_source=self_selected` for any selected MBTI and `psychological_type_source=unknown` for `没测过/不确定`.
2. Show four axis cards and ask each one with three choices only: `准 / 有点像 / 不准`. Map to `accurate / mixed / wrong`.
3. Show one short overall feedback form with three-choice controls:
   - `整体像不像你的工作方式？` → `像 / 一半一半 / 不像`
   - `电脑证据准不准？` → `准 / 一半一半 / 不准`
   - `三大习惯有趣吗？` → `有趣 / 一般 / 不有趣`
   - `隐私体验舒服吗？` → `舒服 / 还行 / 不舒服`
   - `愿意分享这张图吗？` → `愿意 / 看情况 / 不愿意`
4. Add one optional short text box after the choices. Label it `你有什么具体改进建议？` Placeholder: `比如：人格名称可以更有梗，像急急国王、DDL战士、能工智人；或者哪句话不像你。` Keep it optional, cap at 300 characters, and store as `improvement_suggestion`.

Choice mapping is fixed:

- Axis choices: `准=accurate=7`, `有点像=mixed=4`, `不准=wrong=1`.
- Overall choices: positive=`yes=6`, middle=`mixed=4`, negative=`no=2`.

After the user answers, run one finalization command. It writes `feedback.json` and refreshes all research exports atomically:

```bash
python scripts/finalize_feedback.py \
  --evidence output/internal/evidence.json \
  --score output/internal/score.json \
  --config references/scoring-v1.json \
  --output-dir output \
  --research-consent yes \
  --psychological-type ENFJ \
  --ei-choice accurate --sn-choice mixed --tf-choice accurate --jp-choice wrong \
  --overall-choice yes --evidence-choice yes --quirk-choice mixed \
  --privacy-choice yes --share-choice mixed \
  --improvement-suggestion "人格名称可以更有梗一点"
```

If the user chooses `没测过/不确定`, pass `--psychological-type UNKNOWN`.

After finalization, re-register only the updated `work_mbti_return_bundle.zip` and keep `report.png` visible. Tell the user again: `请回传“work_mbti_return_bundle.zip”这个文件夹给Angeline。` Psychological MBTI must be collected only after raw scoring and must never alter the current beta result. A beta run may be called complete only after the finalizer prints `status: complete`.

For the public comparison campaign, use `run_pipeline.py --mode campaign_compare --psychological-type ENFJ`. Never use comparison mode to evaluate beta accuracy.

## Output Meaning

- `data_collection.csv` includes M metadata, all 18 W metrics, G zero-weight candidates and aggregate distributions, four axis results, scoring/config versions, privacy audit, consent, and beta feedback when collected.
- `evidence_table.csv` lists each W/G field with evidence values, coverage, reliability, source lineage, and scoring weight.
- `data_manifest.json` records scan scope, consent, privacy guarantees, generated file list, and participant-return instructions.
- `feedback.json` stores the user's psychological MBTI, the four axis feedback choices, overall fit, evidence accuracy, fun, privacy comfort, share intent, and optional improvement suggestion. It is generated only after the report is shown.
- `work_mbti_return_bundle.zip` is the only normal beta return file. Before feedback it contains `report.png`, `data_collection.csv`, `evidence_table.csv`, and `data_manifest.json`; after feedback it also contains `feedback.json`. Beta participants should download and return this one zip package.
- `report.html`, `report.json`, and `internal/` are debugging artifacts and are not included in the return bundle unless the campaign owner asks for troubleshooting.
- The tables contain no raw text, filenames, full paths, names, contacts, or recovered entities.
- One user's files stay local unless they explicitly submit them. Automatic multi-user aggregation requires a product-approved upload endpoint; do not invent one.

## Boundaries

- Raw first-200-character samples are transient and must be discarded after local classification.
- Missing metrics remain missing and leave the denominator; they never become reverse evidence.
- G fields have scoring weight zero and are used only for report quirks and later aggregate analysis.
- Application installation counts, uptime, late-night activity, and absolute clutter never determine letters. They may appear only as truthful, clearly labeled report habits or research candidates.
- Image category counts from Marvis local knowledge base may determine letters only through low-weight work-image metrics. Lifestyle image categories such as selfie, travel, food, pets, family, documents with sensitive content, and private-photo-library items never determine letters.
- Generated output directories must be outside the skill package and excluded from the next scan.
- Rendering requires a local Chrome/Chromium executable. If unavailable, stop and report that `report.png` could not be rendered. Do not silently deliver HTML or invoke an image model.
