---
name: master-classified-merge
description: Use when merging a classified tag workbook into the online tag管理系统 master table as a new Detection or Validation master version. Handles fast PostgreSQL-side cloning, classified tag replacement for touched UUIDs, language metadata merge, no-tags5/no-comparison-file guardrails, and post-merge QA.
---

# Master Classified Merge

Use this skill when the user says “合到线上总表 / 更新总表 / merge classified 到 master table” and provides a classified workbook such as `tags_YYYYMMDDHHMMSS-classified.xlsx`.

## Purpose

Create a new online master-table version from an existing base version without ORM full-table cloning.

The bundled script:

- Reads a classified workbook.
- Reads an optional language workbook.
- Generates temp CSV and SQL.
- Clones base entries/tags inside PostgreSQL using `INSERT ... SELECT`.
- Replaces only the supplied dimensions for touched UUIDs.
- Links tags to active approved dictionary rows by exact same-dimension `tag_cn`/`tag_en`.
- Updates rule metadata from language sheets using non-empty-field overwrite only.
- Verifies version counts and missing rule names.

## Lessons From Production Incidents

These checks are mandatory because past merges were slow or confusing when they were skipped:

- Treat `modified_rules` UUIDs as either replacements or additions. Before execute, compare them against the selected base version and all online versions. If they are absent from the base, this is an append merge, not a replacement merge.
- Always use the matching language workbook when available. A classified tag workbook can carry tags but not enough names/descriptions; without language metadata, newly appended UUIDs can become UUID-only rows.
- Never assume the latest visible file is the latest online base. Query `master_table_version` and choose the latest same-lane version (`DETECTION` or `VALIDATION`) intentionally.
- Keep dictionary sync scoped to the lane and current input. Do not run broad historical dictionary generation unless the user explicitly asks; it can pull old noisy values into the dictionary.
- Dictionary governance has an approval boundary. A merge may link to existing `APPROVED` dictionary rows and may create high-confidence `PENDING` dictionary candidates for review, but it must never create new `APPROVED` dictionary rows silently. Abnormal candidates must be exported/reported for manual confirmation instead of entering the dictionary.
- If a merge is slow, check indexes before waiting. `master_table_entry(version_id)`, `master_table_entry(version_id, rule_uuid)`, and `master_table_tag(entry_id)` must exist on the online DB.
- Clone tags by first mapping old entry IDs to new entry IDs, then reading `master_table_tag` through `entry_id`. If PostgreSQL still chooses a bad plan, force the generated SQL to use `JOIN LATERAL (...) OFFSET 0` from `tmp_entry_map`; do not start the clone query from the whole `master_table_tag` table or disable nested loops globally, because that can scan tens of thousands of rows and stall.
- Always run MITRE shape QA before committing a merged version. Validate IT `mitre_tactics` codes against active `mitre_official_base/official_mitre_tactics`, not against a hard-coded old regex. ATT&CK v19.1 added official Enterprise tactic codes such as `TA0112 - Defense Impairment`, so `TA01xx` is not automatically bad. Still reject tactic codes that are absent from the active official dictionary, `TAxxxx` tactics inside `ics_mitre_techniques`, and `Txxxx` techniques inside `ics_mitre_tactics`.
- Always run IT-to-ICS bridge QA before accepting a merged version that contains Enterprise `mitre_techniques`. Check `tag字典_0603_split/IT-to-ICS.xlsx`; matching IT techniques should have corresponding `ics_mitre_techniques`, `official_ics_mitre_techniques`, and parent ICS tactics. Missing ICS after a mapped IT technique is a merge/enrichment bug, not "no ICS".
- Identifier/code-only dimensions must never lose English values. `master_table_tag` stores `raw_value` plus `tag_dict_id`, not standalone `tag_cn/tag_en`; if a code-like tag is inserted as `UNMAPPED`, later master exports can show blank `tag_en`. During merge, link existing approved same-value dictionary rows for identifier-like dimensions such as `cve`, `cnvd`, `cwe_nocn`, `capec_nocn`, `nist_control`, `nist_control_nocn`, and `campaign_nocn`. If a dictionary row is missing, create a `PENDING` candidate or export a candidate report; do not silently approve it.
- Normalize known typo/alias dimensions before writing CSV/SQL. In production `softeware` appeared inside a source cell and created a separate master dimension even though the sheet name was `software`; this must always be normalized to `software`. Also keep `安全控制设备` / `安全控制手背` / `control` merged as `control`.
- Every new master version must write `master_table_version.base_updated_at = now()` and APIs/UI must expose it as `Base 更新时间`. If the DB column is missing, add/backfill it before merge; do not leave the UI guessing from `created_at`.
- OWASP is a Web/application-vulnerability-only dimension. During merge, `owasp` and `official_owasp_attacks` must be kept only for rules whose title/metadata clearly indicates `Web应用程序漏洞`, `Web安全验证`, `应用程序漏洞`, `AI应用程序漏洞`, `Web Application Vulnerability`, or `Application Vulnerability`. Remove OWASP from malicious file transfer, phishing email, host command line, protected sandbox, command-and-control, scanning, remote-service-vulnerability, and other non-Web/application-vulnerability rules. Non-Web rule-name prefixes are hard denies even if description text says application vulnerability. CAPEC/CWE relationships are not sufficient to add OWASP outside this scope.

## Hard Rules

- Do not use old comparison files such as `action_tags(5).xlsx`, `tags5`, or audit workbooks unless the user explicitly asks to compare. Classified merge source must be the user-provided classified workbook.
- Keep `DETECTION` and `VALIDATION` separate.
- Always create a new `master_table_version`; do not mutate the old base version directly.
- Use a correct language file when available. If multiple sheets contain the same UUID, later sheets may only override fields that are non-empty. This prevents `Email` sheets without `cn_name` from blanking `Actions.cn_name`.
- If language metadata is missing, do not invent rule names. Report missing UUIDs.
- Prefer this skill's SQL script over `import_classified_tags_to_master()` for large online merges, because the ORM clone path can take too long.
- Do not store passwords in the skill. Pass them via arguments or environment variables.

## Recommended Workflow

1. Identify inputs:
   - `classified`: the classified tag workbook.
   - `language`: the matching language/standardized workbook, if available.
   - `rule_set`: `VALIDATION` or `DETECTION`.
   - `base_version_id`: current online base version to clone from.
   - `version_name`: new master version name.

2. Inspect the source workbook before running:
   - Count `modified_rules` UUIDs.
   - Count tag rows and dimensions.
   - Confirm the lane matches the user's request.
   - If a language workbook exists, pass it. Dry-run must report `language_matched_uuids` equal to touched UUIDs for newly appended rules.
   - Compare touched UUIDs against the chosen base version. If zero match the base but the user intends a new batch, proceed as an append merge; if unexpected, stop and re-check the base version.

3. Ensure online performance indexes exist before large merges:

```sql
CREATE INDEX IF NOT EXISTS idx_master_table_entry_version_id ON master_table_entry(version_id);
CREATE INDEX IF NOT EXISTS idx_master_table_entry_version_rule_uuid ON master_table_entry(version_id, rule_uuid);
CREATE INDEX IF NOT EXISTS idx_master_table_tag_entry_id ON master_table_tag(entry_id);
```

4. Run the script in dry-run mode first:

```bash
python3 ~/.codex/skills/tag-resolve/skills/master-classified-merge/scripts/fast_merge_classified_master.py \
  --classified "/path/to/tags_YYYYMMDDHHMMSS-classified.xlsx" \
  --language "/path/to/language.xlsx" \
  --rule-set VALIDATION \
  --base-version-id "<base-version-uuid>" \
  --version-name "Base - Action/Validation - Classified YYYYMMDDHHMMSS" \
  --dry-run
```

Dry-run must be checked for:

- `modified_uuids`
- `input_tag_rows`
- `tag_types`
- `language_matched_uuids`
- `missing_rule_name_count_before_merge`

For newly appended rules with a language file, `missing_rule_name_count_before_merge` must be `0`.

5. Execute online merge:

```bash
python3 ~/.codex/skills/tag-resolve/skills/master-classified-merge/scripts/fast_merge_classified_master.py \
  --classified "/path/to/tags_YYYYMMDDHHMMSS-classified.xlsx" \
  --language "/path/to/language.xlsx" \
  --rule-set VALIDATION \
  --base-version-id "<base-version-uuid>" \
  --version-name "Base - Action/Validation - Classified YYYYMMDDHHMMSS" \
  --host 192.168.10.89 \
  --ssh-user dx \
  --ssh-password "$TAGSYS_SSH_PASSWORD" \
  --db-name tag_system \
  --db-user tagapp \
  --db-password "$TAGSYS_DB_PASSWORD" \
  --execute
```

6. Verify output:
   - New version ID.
   - Total entries and distinct entries.
   - Total tags.
   - Touched UUID count.
   - Touched tag count.
   - Missing rule-name count.
   - No unexpected `tag_type` remains in the new version. Explicitly check and fix typo dimensions such as `softeware`; they must not appear in `master_table_tag`.
   - `base_updated_at` is non-empty on the inserted `master_table_version`.
   - Identifier/code-only dimensions must export with `tag_en` populated. For values such as `CVE-2026-12345`, `tag_cn` and `tag_en` should both be the code.
   - `mitre_shape_audit` must be `passed`. If it fails, the transaction should roll back and you must inspect:
     - `mitre_tactics` `TAxxxx` codes must exist in active `mitre_official_base/official_mitre_tactics` for the current ATT&CK version.
     - `ics_mitre_techniques` must not contain `TAxxxx` tactic values.
     - `ics_mitre_tactics` must not contain `Txxxx` technique values.
   - `IT-to-ICS` bridge check must be `passed` or explicitly reported with examples. Do not deliver a merged master where `mitre_techniques` contains codes present in `IT-to-ICS.xlsx` but the corresponding ICS sheets are absent.
   - OWASP scope check must pass: run `python backend/scripts/cleanup_non_web_owasp_tags.py --rule-set <VALIDATION|DETECTION> --version-id <new-version-id> --dry-run`. The `master_removed_non_web_owasp_tags` count must be `0`; if not, rerun without `--dry-run` and re-export/re-check.

7. If the user also asks to update dictionaries, sync only missing tag pairs from the current workbook into the same-lane base dictionary:
   - Detection -> `detection_base`
   - Validation -> `validation_base`
   - Use exact same-dimension `tag_cn`/`tag_en` matching.
   - Existing approved rows can be linked immediately.
   - New dictionary rows must be inserted as `PENDING`, `is_active=true`, and `source_type='MASTER_SYNC_CANDIDATE'`, or exported as a review workbook if the value is abnormal.
   - Do not link pending dictionary rows as green mapped tags until the user approves them.
   - Report inserted pending dictionary count by `tag_type`, abnormal candidate count, and remaining unmapped count for the current input.

## Dictionary Candidate QA

Before any dictionary candidate is inserted, classify it:

- `auto_pending`: tag type exists in `tag_type_registry`, `tag_cn` and `tag_en` are non-empty, and the value is code-like or came directly from a user-provided final workbook.
- `manual_review`: tag type exists, but `tag_en` is missing, the value is unusually long, contains descriptions/URLs/timestamps/hashes, mixes multiple unrelated values, or looks like a sentence.
- `invalid_type`: tag type is not registered for the lane (`rule_set` or `BOTH`); do not insert it. Report the original sheet/value.
- `blocked`: value is on the project block list for that dimension, such as malware/tool names that must not become `threat_group`.

Only `auto_pending` may enter `tag_dictionary` as `PENDING`. Everything else must be returned for human confirmation.

## Default Online Context

Known non-secret defaults:

- Host: `192.168.10.89`
- SSH user: `dx`
- App root: `/home/dx/apps/tag-management-system`
- DB name: `tag_system`
- DB user: `tagapp`

Use `sshpass` only when the user has supplied/approved the password in the current work context.

## Output Expectations

Final response should include:

- New version name and ID.
- Base version ID used.
- Entry/tag counts.
- Number of touched UUIDs.
- Whether missing rule names remain.
- Any cleaned ignored artifacts, for example old `tags5` comparison files.

## Troubleshooting

- If the merge is slow, check `pg_stat_activity`. If it is stuck on cloning `master_table_tag`, first verify the indexes above. If indexes exist and it is still slow, inspect the generated SQL and ensure it uses `tmp_entry_map` with `JOIN LATERAL (SELECT ... FROM master_table_tag WHERE entry_id = em.old_entry_id OFFSET 0)` so each old entry uses `idx_master_table_tag_entry_id`.
- If an execute run is terminated during a transaction, PostgreSQL rolls it back. Verify no target `version_name` exists before re-running.
- If `modified.csv` line count is larger than UUID count, inspect with CSV parser before panicking. Multiline descriptions/notes are valid CSV and make `wc -l` misleading.
- If rule names become UUIDs, re-run metadata repair using the correct language workbook and the non-empty override rule.
- If the target version already exists, stop and ask whether to delete the failed duplicate or create a differently named version. Do not overwrite silently.
