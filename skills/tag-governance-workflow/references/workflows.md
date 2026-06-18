# Workflow Notes

## Main database objects

- Dictionary versions live in `dictionary_version`
- Dictionary terms live in `tag_dictionary`
- Master-table versions live in `master_table_version`
- Master-table rows live in `master_table_entry`
- Master-table tags live in `master_table_tag`

## Current version conventions

- Official dictionary version: `mitre_official_base`
- Validation active dictionary: `validation_base`
- Detection active dictionary: `detection_base`
- Validation AI taxonomy: `validation_ai_recommend_attack_v1`
- Detection AI taxonomy: `detection_ai_recommend_attack_v1`

## Review convention

- Formal master-table versions are baseline/reference.
- `[REVIEW]` versions are the correct place for AI补标、官方桥接、旧标签校对.
- Do not mutate the formal source version when the user says “校对版” or “review”.

## Classified workbook supplementation

Current project pattern:
- read workbook from `参考文档/`
- keep source sheets unchanged
- create a sibling workbook with `_official补充.xlsx`
- append `official_*` sheets and a summary sheet

## Useful reporting dimensions

Frequent high-value dimensions:
- `control`
- `os`
- `mitre_tactics`
- `mitre_techniques`
- `ics_mitre_tactics`
- `ics_mitre_techniques`
- `official_cwe`
- `official_capec_patterns`
- `official_capec_categories`
- `official_owasp_attacks`
- `official_nist_controls`
- `official_nist_family`
