# Research Dataset Products

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

Neither table stores source text, filenames, paths, names, contact details, or detected entities. `research_consent=no` means the files remain local and must not be submitted or uploaded.

The first beta schema is intentionally broad enough for 48-80 participant calibration. G fields include the peak activity hour and privacy-safe aggregate distributions, but their scoring weight remains zero until cohort analysis justifies promotion.

Time-based report fields use a stricter research trace:

- only files active in the latest 180 days;
- same-second bulk migrations/exports are excluded;
- one project contributes at most one activity session per hour;
- `activity_session_count`, `activity_active_day_count`, `peak_activity_share`, `peak_activity_gap`, and `peak_activity_confidence` are retained for audit;
- the poster shows a peak hour only at medium or high confidence, otherwise it says `样本不足`.

Additional zero-weight calibration fields include `recent_180_file_count`, the strict session-based late-night/weekend ratios, all 24-hour/7-day aggregate distributions, `marvis_image_category_distribution`, `marvis_image_recognized_count`, `marvis_app_inventory_count`, `marvis_app_category_distribution`, and `marvis_app_names`. Application inventory fields are for later model optimization only and do not determine the current letters.

Image category metrics are the one exception to the old "images are gray-only" rule: if Marvis provides category counts for work images inside the authorized file scope, low-weight W metrics may use them for S/N and T/F. Lifestyle categories such as selfie, travel, food, family, or private-photo-library content remain gray-only or excluded.
