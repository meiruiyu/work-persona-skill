# Privacy Policy

## Allowed

- Read metadata and transiently classify an explicitly authorized work file.
- Retain only anonymous counts, ratios, broad labels, confidence, and hashed project IDs.
- Read at most the first 200 text characters of up to 300 recent work documents for local classification, then discard the text.
- Read Marvis local knowledge base image category aggregates inside the authorized file scope. Retain only category counts/ratios; do not retain raw images, OCR text, faces, identities, or locations.
- Read Marvis local knowledge base application inventory aggregates for research calibration. Retain app names, broad categories, and counts only; do not retain usage content or account data.

## Never retain or expose

- Full paths, filenames, source excerpts, names, organizations, accounts, emails, phone numbers, addresses, or document authors.
- Document bodies, chats, mail bodies, browser history, passwords, credentials, identity documents, bank cards, contracts, medical records, or private photos.
- Raw images, private photo-library items, extracted image text, face recognition output, precise photo locations, or application foreground usage content.

## Exclude before sampling

Skip sensitive path or filename categories, system directories, application packages, caches, dependency folders, backups, hidden metadata, and recycle/trash directories. Record only exclusion counts by broad reason.

## Consent boundaries

Scan only the single preset scope selected by the user or 1–3 paths selected through the native folder picker after choosing `自选工作文件夹`. Analyze only files modified in the fixed latest-365-day scoring window; do not ask for a separate time-range authorization. Do not expand to parent directories, the user home directory, cloud drives, photo libraries, calendars, or application support directories without separate explicit authorization.

The default application inventory flow must not require Full Disk Access. If app usage strength or recent active days are blocked by macOS privacy controls, skip them instead of asking the participant to change system settings.

## Beta feedback

Collect psychological MBTI and ratings only after raw scoring. Store them separately from `evidence.json` and `score.json`. The return-data selector is explicit consent: A permits returning privacy-safe computer aggregates plus feedback; B permits returning the user's explicit experience feedback only and must exclude computer-statistics CSV and evidence tables from the return bundle.
