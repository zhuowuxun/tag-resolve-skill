---
name: tag-governance-workflow
description: Manage tag dictionary governance, official MITRE/CAPEC/CWE/OWASP/NIST mapping, detection-vs-validation tag workflows, review-table enrichment, and classified Excel supplementation for the tag管理系统 project. Use when working on tag dictionaries, official bridge logic, review versions, rule-tag normalization, classified workbook补标, or tag-count/reporting tasks in this repository.
---

# Tag Governance Workflow

Use this skill only for the `tag管理系统` project.

## Core Rules

- Keep `DETECTION` and `VALIDATION` separate. Do not mix dictionaries, mappings, or review outputs across rule sets.
- Treat official dictionaries as the normalization target. Prefer bridging old/raw tags into `mitre_official_base` rather than inventing parallel tags.
- Keep formal/base master-table versions immutable. Put AI补标、旧标签校对、官方桥接 into `[REVIEW]` versions unless the task is explicitly “supplement an Excel file only”.
- Prefer deterministic bridges before LLM inference.
- When the source file already contains a direct field (`cwe_nocn`, `mitre_techniques`, `nist_control_nocn`), bridge from that field first. Do not jump straight to heuristic CAPEC/OWASP inference.
- Yellow/orange cells mean `tag_dict_id IS NULL`. Before treating them as AI补标, run a same-lane dictionary match audit. If a value can be deterministically normalized to an existing dictionary row, link it instead of leaving it yellow.
- Do not create or imply dictionary entries just to remove yellow. If the same-lane dictionary has no matching row, keep the value yellow and report the missing dictionary term.

## Workflow

### 1. Identify the working surface

Choose one of these first:
- Dictionary work: update or inspect dictionary versions and dimension counts.
- Review work: supplement the current `[REVIEW]` master-table version.
- Classified Excel work: generate a new workbook with extra official sheets, without modifying database rows.
- Reporting work: count dimensions, coverage, or export comparison tables.

### 2. Resolve the lane

- `DETECTION` lane uses `detection_base` and the detection master table.
- `VALIDATION` lane uses `validation_base` and the validation master table.
- Official normalization always uses `mitre_official_base`.
- AI-recommend attack taxonomy uses:
  - `detection_ai_recommend_attack_v1`
  - `validation_ai_recommend_attack_v1`

### 3. Bridge in the right order

Use this order unless the task says otherwise:
1. Raw/source field -> official dictionary direct match
2. Raw/source field -> normalized external ID -> official dictionary
3. Official upstream dimension -> downstream official dimension through official metadata
4. Only then use heuristic or AI inference

Default bridge order by family:
- MITRE: old `mitre_*` / `ics_mitre_*` -> `official_mitre_*` / `official_ics_mitre_*`
- CWE: `cwe_nocn` -> `official_cwe`
- NIST: `nist_control_nocn` -> `official_nist_controls` -> `official_nist_family`
- CAPEC: `official_cwe` primary, `official_mitre_*` secondary -> `official_capec_patterns` -> `official_capec_categories`
- OWASP attacks: official CAPEC View 659 first; otherwise only add high-confidence bridges

## Project Paths

Read these scripts before changing behavior:
- `backend/scripts/create_official_mitre_dictionary.py`
- `backend/scripts/create_official_capec_dictionary.py`
- `backend/scripts/sync_official_cwe_from_capec.py`
- `backend/scripts/sync_official_capec_owasp_view_659.py`
- `backend/scripts/sync_official_nist_80053_release_520.py`
- `backend/scripts/apply_official_cwe_to_review.py`
- `backend/scripts/apply_official_nist_to_review.py`
- `backend/scripts/apply_official_owasp_attacks_from_capec_to_review.py`
- `backend/scripts/apply_capec_nocn_to_review.py`
- `backend/scripts/enrich_classified_with_official_tags.py`

Read these service files when changing online behavior:
- `backend/app/services/ai_tagging.py`
- `backend/app/services/master_table_service.py`
- `backend/app/services/master_review_service.py`

For detail, read:
- [workflow notes](references/workflows.md)
- [official mapping notes](references/official-mappings.md)

## Common Tasks

### Supplement a classified workbook with official sheets

Use `backend/scripts/enrich_classified_with_official_tags.py`.

Expected behavior:
- Keep the original workbook unchanged.
- Write a new workbook beside it.
- Preserve original sheets.
- Add `official_*` sheets plus `official_bridge_summary`.
- Prefer deterministic bridges.

### Normalize review-table tags

When writing into a `[REVIEW]` version:
- Add new official tags with `AI_MAPPED` only if the bridge is deterministic or already approved by the project workflow.
- Do not delete old/raw tags unless the task explicitly asks to clean them.
- Keep old and new tags side-by-side when comparison is useful.

### Count dimensions

Report both sides when useful:
- dictionary count: number of dictionary terms in a dimension
- master count: number of tag rows and distinct rules carrying that dimension
- For ransomware reporting, if the workbook/stat sheet is counting `勒索软件相关`, extract the family name from the rule title by taking the token immediately before `勒索软件`. Example: `LockBit 3.0 勒索软件` -> `LockBit 3.0`, `Veaxor 勒索软件` -> `Veaxor`.

### Threat Group Alias Dictionary Sync

Use this checklist whenever syncing or repairing `threat_group_altname` into `validation_base` or exporting threat-group statistics:

- The curated dictionary is the authority. If the user provides `threat_group_altname_字典.xlsx`, use its `dictionary` sheet and do not fall back to older audit/curated drafts unless asked.
- Alias rows must be approved dictionary rows with both `parent_tag_id` and `mapped_tag_id` pointing to the canonical threat-group row. A row that only has `mapped_tag_id` but no `parent_tag_id` will not behave correctly in platform bridge/stat logic.
- After syncing, verify `validation_base/threat_group` has no unexpected `PENDING` rows. Historical `REFERENCE_SYNC` imports may leave rows pending; approve final-dictionary rows after validation.
- Do not force ambiguous shared aliases into a parent. Skip and report conflict aliases such as values that appear under multiple canonical names.
- For counting or expanding master-table tags, canonicalize through parent relationship first. Count aliases as support for their canonical parent, but keep alias tags valid when the user explicitly wants aliases as real tags.
- Normalize `UNC1234` to `APT-U1234` before comparing or counting.
- Normalize `APT-U1234` and `UNC1234` as the same threat-group code. Normalize `APT-G1234`, `Team1234`, and `Team 1234` as the same threat-group code. Do not report these as dictionary conflicts merely because the title and tag use different code families/spaces.
- Threat-group/industry audit must skip entries whose rule name is blank or only a UUID. Without a real rule title or description context, do not infer whether the threat-group tag is wrong.
- For Lazarus-family cleanup, keep `SectorA01` and `ITG03` under the proper-case `Lazarus` parent. Treat APT38 as a Lazarus-family subgroup, but do not automatically expand APT38-titled rules with every broad Lazarus umbrella alias unless the user explicitly asks for umbrella expansion.
- Treat `Cobalt Strike` as a tool name, not a threat group. If a rule title/description only contains `Cobalt Strike`, do not match or expand the Cobalt actor family (`Cobalt`, `Cobalt Gang`, `Cobalt Group`, `Cobalt Spider`, `G0080`, `Gold Kingswood`, `Mule Libra`). Do not remove valid non-Cobalt-family aliases such as `Cobalt Kitty` when they are part of another confirmed group. This pitfall previously caused APT41 rules to inherit APT4-family aliases and APT29 rules to inherit APT2/Putter Panda aliases through incorrect family expansion.
- Treat `Scarab` as a ransomware/malware family, not a threat group. Keep/bridge `malware=SCARAB`, but block `threat_group=Scarab` from extraction, dictionary sync, and audit expansion.
- Treat `RansomHub` as a ransomware/malware family, not a threat group. Keep/bridge `malware=RANSOMHUB`, but block `threat_group=RansomHub` from extraction, dictionary sync, and audit expansion.
- Treat `Emdivi` as malware/backdoor context, not a threat-group label. In titles such as `Emdivi 后门` or `Emdivi backdoor`, do not map or expand it into `threat_group`; keep the actual named organization such as `Bronze Butler` if present.
- Do not auto-extract `WildPressure` or `InvisiMole` as `threat_group` in this platform workflow. They have caused false-positive threat-group tags from rule titles; keep them out unless the user explicitly approves a threat-group dictionary correction.
- `Hades` was initially suspected as a ransomware-only false positive, but project rules explicitly use `Hades 威胁组织`; keep it as a threat-group alias under the existing Indrik/Evil Corp/Mustard Tempest family, while still allowing malware-dimension Hades/SCARAB-style labels when they are explicitly malware.
- Do not auto-extract `Foudre`, `Tonnerre`, `HeartBeat`, or `PLA Navy` as `threat_group`: Foudre and Tonnerre are treated as malware/tool context unless the title explicitly names Prince of Persia/APT-C-07/Infy/Operation Mermaid; HeartBeat is usually heartbeat traffic wording; PLA Navy is an affiliation/sponsor cue rather than a threat-group alias in this taxonomy.
- Treat `Infy`, `Prince of Persia`, and `Operation Mermaid` as aliases under the `APT-C-07` threat-group family. Do not let `Infy` remain a separate canonical threat-group row in audit or expansion logic.
- Keep `WICKED SPIDER` as its own threat-group label when explicitly present, but do not bridge it as an alias of `Energy` or auto-expand it from `APT41/Cobalt Strike` context.
- Confirmed alias bridges in `validation_base/threat_group` include: `MenuPass -> APT10`, `ITG13 -> OilRig`, `APT-C-11/ITG14/Navigator/TAG-CR1 -> FIN7`, `TG-4410 -> Patchwork`, `Bronze Highland/Daggerfly/Evasive Panda -> EvasivePanda`, `APT-C-56 -> APT36`, `ITG07 -> APT39`, `ITG16/Kimsuky -> APT43`, `HackingTeam -> Hacking Team`, and `Prince of Persia -> APT-C-07`.
- Do not auto-expand related-but-not-identical umbrella/subgroup relationships unless the title explicitly names the exact tag. Current safe examples: `Moonstone Sleet` should not auto-expand to `Lazarus`; `Andariel` should not be injected into broad `Lazarus/Contagious Interview/FASTCash` rules unless explicitly present.
- Leave unresolved/manual-review pairs in audit instead of forcing a bridge when public confidence is not high enough. Current examples include `APT-C-23/TG-3`, `APT-U4210/UNC638`, and `TEMP.Lice/Foudre`.
- If a script creates alias tags from metadata, it must set `parent_tag_id=<canonical.id>` and `mapped_tag_id=<canonical.id>`. The old pitfall was creating aliases with `parent_tag_id=None`, which made `APT38/Bureau 121/G0032` and similar aliases look like separate organizations.
- After fixing or expanding `threat_group`, immediately bridge `industry`/`industries` from the final canonical/alias threat-group tags using the approved threat-group-to-industry relationship file and the current same-lane industry dictionary. Treat a missing industry sheet/tag output as a workflow failure when mapped threat groups exist.
- The online PostgreSQL table names are singular: `dictionary_version`, `tag_dictionary`, `master_table_version`, `master_table_entry`, and `master_table_tag`.

### Compare old vs official

Prefer comparing by `external_id`/code, not by translated display name.
Examples:
- `T1190`
- `CAPEC-66`
- `CWE-89`
- `AC-06`

### Audit Yellow/Orange Review Tags

Use this check before final export when the user is reviewing highlighted cells:

- Scope the audit to the target lane and batch/version. For Validation pending imports, filter `rules_main.rule_set = 'VALIDATION'` and `rules_main.status = 'PENDING'`; when an import batch is known, additionally filter to that batch.
- For every unmapped row (`tag_dict_id IS NULL`), try deterministic same-type, same-lane matches against the active base dictionary:
  - exact `tag_cn`
  - exact `tag_en`
  - normalized external ID form, such as stripping `ATT&CK:` from `ATT&CK:M1018` before matching `mitre_mitigation=M1018`
- If matched, update the mapping to the dictionary row and set the display value to the canonical dictionary label.
- If not matched, keep the row yellow. Report representative unresolved values instead of silently inventing tags.
- Never map a value across dimensions just because the text matches. For example, a `vendor=MLflow` text match to `software=MLflow` is not a valid vendor dictionary link.
- For `mitre_techniques` and `mitre_mitigation`, normalize by external code first (`T1027.008`, `T1059.011`, `M1018`). A value like `ATT&CK:M1060` remains yellow if no same-lane `mitre_mitigation` dictionary row exists.

### Validation Review Export QA

Before handing over a review workbook:

- Use `openpyxl` or another real Excel writer for user-facing Excel deliverables. Do not hand-generate XLSX XML/ZIP files when formatting, yellow highlights, sheet order, or preserved styles matter. The old pitfall was XML-generated workbooks that looked structurally valid but did not render visible yellow fills in WPS/Excel.
- Ensure no sheet has `freeze_panes` set. The review Excel should not freeze windows unless the user explicitly asks.
- Count yellow cells by sheet and inspect samples from each sheet.
- Do not fill a summary cell yellow when it contains both mapped and unmapped values. Excel cell fill applies to the whole cell, so mixed cells would make valid mapped values look wrong. Keep exact yellow marking in the detail sheet, and only fill a summary cell yellow when all values in that dimension cell are unmapped.
- Sort code-like values by normalized external ID, not by raw display text. For example, `ATT&CK:M1060` should sort as `M1060`, after `M1018/M1022/M1024/M1030`, not before them because of the `ATT&CK:` prefix.
- Re-check high-risk sheets that are often false-yellow:
  - `mitre_techniques`
  - `mitre_mitigation`
  - `software`
  - `vendor`
  - `malware`
  - `nist_control`
- Distinguish false-yellow dictionary misses from true unknown values. Fix false-yellow rows; leave true unknowns yellow and list them.

## Guardrails

- Do not claim a mapping is official unless it comes from an official source already loaded into this project.
- CAPEC categories are not one-to-one with patterns. Do not assume every pattern has one category.
- MITRE revoked techniques must not be silently treated as active official techniques.
- For official CWE display, keep short code as display (`CWE-799`) and store the full official title in metadata/aliases.
- For official NIST controls, keep short display (`AC-06`) and store full control title in metadata.
- Do not infer malware from action descriptions, behaviors, or command names. Malware tags require explicit `Malware:*` source values, clear family names in the title/text, or existing dictionary matches.
- Do not turn vulnerability product names into green `software` or `vendor` tags unless a same-lane dictionary row exists. Title-extracted product/vendor values should stay yellow when no dictionary row exists.

## Output Expectations

When finishing a task, report:
- target surface: dictionary / review version / workbook
- which official dimensions were added or updated
- created counts by dimension
- any unmatched or ambiguous IDs
- file path of generated workbook/report if one was created


## Installation

Distribute this skill as a folder or zip. Install by copying `tag-governance-workflow/` into `~/.codex/skills/`. Use it only while working inside the `tag管理系统` repository so the project-relative paths above resolve correctly.
