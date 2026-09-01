# Research Dataset Products

Every beta user gets a `report.png` poster and structured feedback. The return-data choice only controls whether anonymized computer-statistics tables are included in `work_mbti_return_bundle.zip`.

## Return bundle modes

### A 参与脱敏优化（推荐）

Full return bundle for users who are willing to help improve the Skill:

- `report.png`: the user's Work MBTI poster.
- `data_manifest.json`: run description, scan preset, consent, rule versions, and privacy guarantees.
- `data_collection.csv`: one-row anonymized statistics table for later merged analysis.
- `evidence_table.csv`: anonymized evidence table explaining which fields supported the result.
- `feedback.json`: the user's Work MBTI experience feedback.
- `README_请回传这个zip.txt`: simple return instructions.

It must not contain filenames, full paths, source text, raw images, real names, phone numbers, emails, or other sensitive content.

### B 只回传体验反馈

Small return bundle for users who only want to return their experience feedback:

- `report.png`: the user's Work MBTI poster.
- `data_manifest.json`: minimized run description and privacy guarantees.
- `feedback.json`: the user's Work MBTI experience feedback.
- `README_请回传这个zip.txt`: simple return instructions.

It must not include `data_collection.csv` or `evidence_table.csv`.

## data_collection.csv

One row equals one anonymized run. The row contains:

- consent and anonymous run identifiers;
- M scan metadata and data-quality coverage, including the selected directory preset and fixed 365-day lookback window;
- all W scoring metrics, including missing/degraded state;
- all G zero-weight research candidates, including active-hour, weekday, extension, Marvis image-category, and Marvis app-inventory distributions;
- four-axis scores, confidence, coverage, and metric contributions;
- raw/display work type and scorer version;
- beta labels and 1-7 ratings after feedback is collected.

This is the table to merge across 48-80 participants. The campaign owner should append rows by matching column names, then analyze axis-level accuracy and feature usefulness.

## evidence_table.csv

A long-format audit table. One row equals one W or G field. Use it to inspect why an individual result was produced and whether a field was missing, degraded, or overrepresented.

## Privacy

Neither table stores source text, filenames, paths, names, contact details, or detected entities. `research_consent=no` means the tables remain local calculation artifacts and are excluded from `work_mbti_return_bundle.zip`; only the poster, minimized manifest, and explicitly answered experience feedback are returned.

The first beta schema is intentionally broad enough for 48-80 participant calibration. G fields include the peak activity hour and privacy-safe aggregate distributions, but their scoring weight remains zero until cohort analysis justifies promotion.

Time-based report fields use a stricter research trace:

- prefer files active in the latest 180 days;
- same-second bulk migrations/exports are collapsed so one export cannot dominate the result;
- the primary trace allows one project to contribute at most one activity session per hour;
- if the primary trace is empty, collapse recent events to one event per day-hour; if the chosen folder has no recent-180-day events, use the same collapsed method over the latest 365 days;
- `activity_session_count`, `activity_active_day_count`, `peak_activity_share`, `peak_activity_gap`, and `peak_activity_confidence` are retained for audit;
- `activity_source_level` and `activity_window_days` record which time fallback was used;
- the poster recalculates the peak from each user's own recent-180-day distribution and shows it as a three-hour-friendly dynamic label such as `09:00前后` or `17:00前后`; example values are never hardcoded, and `activity_observation_level` records whether the observation is stable, limited, or unavailable for later calibration;
- the poster recalculates each user's late-night ratio and always shows the observed result, including a genuine `0%`, while session/day counts remain available for judging reliability during research.

Additional zero-weight calibration fields include `recent_180_file_count`, the strict session-based late-night/weekend ratios, all 24-hour/7-day aggregate distributions, `marvis_image_category_distribution`, `marvis_image_recognized_count`, `marvis_app_inventory_count`, `marvis_app_category_distribution`, and `marvis_app_names`. Application inventory fields are for later model optimization only and do not determine the current letters.

Image category metrics are the one exception to the old "images are gray-only" rule: if Marvis provides category counts for work images inside the authorized file scope, low-weight W metrics may use them for S/N and T/F. Lifestyle categories such as selfie, travel, food, family, or private-photo-library content remain gray-only or excluded.
