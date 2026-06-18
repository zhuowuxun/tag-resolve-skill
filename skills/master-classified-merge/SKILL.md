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
- If a merge is slow, check indexes before waiting. `master_table_entry(version_id)`, `master_table_entry(version_id, rule_uuid)`, and `master_table_tag(entry_id)` must exist on the online DB.
- Clone tags by first mapping old entry IDs to new entry IDs, then joining `master_table_tag` on `entry_id`. Do not start the clone query from the whole `master_table_tag` table; it can scan tens of thousands of rows and stall.

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

7. If the user also asks to update dictionaries, sync only missing tag pairs from the current workbook into the same-lane base dictionary:
   - Detection -> `detection_base`
   - Validation -> `validation_base`
   - Use exact same-dimension `tag_cn`/`tag_en` matching.
   - Mark new dictionary rows as `APPROVED`, `is_active=true`, and set `source_type='MASTER_SYNC'`.
   - Link newly inserted dictionary IDs back to the new master version's `master_table_tag` rows.
   - Report inserted dictionary count by `tag_type` and remaining unmapped count for the current input.

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

- If the merge is slow, check `pg_stat_activity`. If it is stuck on cloning `master_table_tag`, first verify the indexes above. If indexes exist and it is still slow, inspect the generated SQL and ensure it uses `entry_map` before joining `master_table_tag`.
- If an execute run is terminated during a transaction, PostgreSQL rolls it back. Verify no target `version_name` exists before re-running.
- If `modified.csv` line count is larger than UUID count, inspect with CSV parser before panicking. Multiline descriptions/notes are valid CSV and make `wc -l` misleading.
- If rule names become UUIDs, re-run metadata repair using the correct language workbook and the non-empty override rule.
- If the target version already exists, stop and ask whether to delete the failed duplicate or create a differently named version. Do not overwrite silently.
