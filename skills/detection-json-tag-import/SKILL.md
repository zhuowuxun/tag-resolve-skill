---
name: detection-json-tag-import
description: Use when importing Digitation/SecVision-style detection JSON exports into the tag管理系统 online review queue, then running deterministic tag enrichment, software/vendor cleanup, official MITRE/ICS bridging, QA counts, and Excel export for inspection.
---

# Detection JSON Tag Import

Use this skill only for the `tag管理系统` project when the user provides a detection JSON export such as `export_YYYYMMDD_NN.json` and asks to “走 detection 导入和补 tag 流程”.

## Target

- Rule set: `DETECTION`.
- Destination: online review queue (`rules_main.status = PENDING`).
- Dictionary lane: `detection_base`.
- Official lane: `official_mitre_*` and `official_ics_mitre_*`.
- Keep `DETECTION` and `VALIDATION` separate.

## Workflow

1. Inspect the JSON locally.
   - Confirm it is a dict with `actions`.
   - Count `actions` and `sequences`.
   - For detection imports, use `actions`; `sequences` may be empty.

2. Backup the online database before writing.
   - Use the remote app’s `backend/.env` for DB settings when possible.
   - Store backups under `/home/dx/db_backups/`.
   - Name backups like `before_detection_<json_stem>_import_<timestamp>.dump`.

3. Upload the JSON to the remote app output directory.
   - Default remote app path: `/home/dx/apps/tag-management-system`.
   - Default upload path: `/home/dx/apps/tag-management-system/output/<filename>`.

4. Import through `app.services.rule_import_v2.import_single_file_auto`.
   - Call the async function with:
     - `filename=<json filename>`
     - `content=<json bytes>`
     - `rule_set="DETECTION"`
     - `user_id=<admin user id>`
   - Commit only after success.
   - Record `import_batch_id`, imported/skipped counts, and initial `tag_type_counts`.

5. Run enrichment scripts.
   - `backend/scripts/backfill_detection_pending_review_tags.py`
   - `backend/scripts/apply_vendor_from_software_to_pending_rules.py --rule-set DETECTION --status PENDING --dict-version detection_base`
   - `backend/scripts/apply_official_tags_to_pending_rules.py --rule-set DETECTION --status PENDING`

6. QA only the new batch.
   - Filter rules by `raw_json::text like '%<import_batch_id>%'`.
   - Count `tag_type`, row count, and distinct rule count.
   - Inspect `software`, `vendor`, and `other` per rule.
   - Expected checks:
     - `software` should cover all imported rules when source has `affected_software` or title product names.
     - `vendor` should be bridged from dictionary, `affected_software`, official homepages, GitHub orgs, or high-confidence vendor prefixes.
     - `other` should be zero unless a residual value is intentionally left for human review.
     - Do not treat generic values as malware/software/vendor, such as `Download`, `Malicious Link`, `web`, `http`, timestamps, versions, or vulnerability category words.

7. Batch-level manual cleanup if needed.
   - Fix overlong software values by stripping endpoint/action tails (`api`, `image_url`, `createuser`, path fragments).
   - Prefer source-derived vendors:
     - `affected_software` prefix when it clearly means vendor.
     - Homepage domain such as vendor official site.
     - GitHub org only when it is the real project/vendor, not a PoC author.
   - Delete residual `other` values after successful classification.

8. Export the new batch.
   - Use `app.services.excel_export.export_rules_to_excel`.
   - Parameters: `rule_set="DETECTION"`, `status="PENDING"`, `import_batch_id=<batch_id>`, `limit=0`.
   - Save remote output under `/home/dx/apps/tag-management-system/output/`.
   - Copy the Excel to `~/Downloads/`.

## Reporting

Final response should include:

- Imported/skipped count.
- `import_batch_id`.
- Final batch tag coverage counts for the important dimensions.
- Whether `other` is cleared.
- Local Excel path.
- Any unresolved ambiguous vendor/software decisions.

## Guardrails

- Never mix detection JSON imports into validation workflows.
- Do not claim an official tag was added unless it came from existing official dictionary/bridge logic.
- Do not force weak product-to-vendor guesses into green dictionary tags.
- For AI/raw recommendations, keep them unmapped/orange unless there is an existing dictionary match.
- If import errors occur, rollback and report the exception before retrying with corrected function signature or parameters.
