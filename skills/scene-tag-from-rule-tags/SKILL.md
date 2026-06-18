---
name: scene-tag-from-rule-tags
description: Use when the user asks to tag scenes/scenarios from rule tags using a seq_to_action/sequence-action mapping Excel and master-table rule tags. Generates scene tag ratio analysis and final per-dimension scene tag workbooks.
metadata:
  short-description: 给场景按规则 tag 自动打 tag
---

# Scene Tag From Rule Tags

Use this skill when the user provides a scene-to-rule mapping file such as `seq_to_action_*.xlsx` / `sequence_action*.xlsx` and asks to 给场景打 tag, 场景关联 tag, 场景 tag 占比, or 筛选 80% 场景 tag.

## Core Rule

Scene tag = aggregate tags from all rules linked to the scene.

Default dimensions:

`attack_name`, `attack_type`, `malware`, `threat_group`, `vendor`, `control`, `mitre_tactics`, `industries`

Default ratio:

`tag support rule count / scene total rule count`

Do **not** divide by total tags in that dimension. Example: if a scene has 10 rules and 2 rules have `AV`, `AV` ratio is `20%`.

Default final threshold: keep scene tags with ratio `>= 80%`.

## Expected Inputs

Scene mapping Excel should contain:

- `UUID`: scene UUID
- `name`: scene name
- `sim_actions`: linked rule UUID

Rule tags should come from the relevant latest master table unless the user explicitly requests pending review data. For validation/action scenes, default to the latest Action/Validation master table. For detection scenes, default to the latest Detection master table.

Required rule-tag fields:

- `rule_uuid`
- `rule_name`
- `rule_set`
- `tag_type`
- `tag_cn`
- `tag_en`
- optional: `raw_value`, `mapping_status`

## Workflow

1. Inspect the scene mapping workbook first: sheet names, columns, row count, unique scene count, unique rule UUID count.
2. Identify the correct master table version from `master_table_version`.
3. Export only needed dimensions from `master_table_entry` + `master_table_tag` + `tag_dictionary`.
4. Run `scripts/scene_tag_from_rule_tags.py` with the scene mapping and exported rule-tag CSV.
5. QA:
   - every scene-rule UUID should match master tags, or report missing UUIDs;
   - output final workbook must have one sheet per dimension;
   - each tag must be a separate row, never multiple tags jammed into one cell;
   - ratio must be formatted as percent and calculated against scene total rules.
6. Return two paths:
   - full analysis workbook;
   - final `>=80%` scene tag workbook.

## Export Query Template

Adjust `version_id` and dimensions as needed. Do not hardcode credentials in the skill; use the project’s normal DB access method or environment variables.

```sql
select
  e.rule_uuid,
  e.rule_name,
  e.rule_set,
  t.tag_type,
  coalesce(td.tag_cn, t.raw_value) as tag_cn,
  coalesce(td.tag_en, '') as tag_en,
  t.raw_value,
  t.mapping_status
from master_table_entry e
join master_table_tag t on t.entry_id = e.id
left join tag_dictionary td on td.id = t.tag_dict_id
where e.version_id = '<MASTER_VERSION_ID>'
  and t.tag_type in (
    'attack_name','attack_type','malware','threat_group',
    'vendor','control','mitre_tactics','industries'
  );
```

## Script

Use the bundled script when possible:

```bash
python scripts/scene_tag_from_rule_tags.py \
  --scene-xlsx /path/to/seq_to_action.xlsx \
  --rule-tags-csv /path/to/rule_tags.csv \
  --out-dir /path/to/output \
  --prefix scene_tags_0527 \
  --threshold 0.8
```

The script writes:

- `<prefix>_ratio.xlsx`: `scene_summary`, `scene_tag_ratio`, `scene_rule_map`, `missing_rules`, `stats`
- `<prefix>_ge80.xlsx`: final true tags, one sheet per dimension plus `overview`

## Pitfalls

- Do not use XML/ZIP hand-written XLSX generators. Use `openpyxl`.
- Do not use pending review rows unless the user explicitly asks; default to master-table tags.
- De-duplicate scene-rule pairs before counting total rules.
- De-duplicate repeated same tag on the same rule before counting support.
- Empty final sheets are acceptable; keep the sheet with headers.
- If the scene mapping file uses different column names, map them deliberately and state the assumption.
