---
name: validation-excel-tag-import
description: Use when importing Validation single-sheet tag Excel files such as tags_YYYYMMDDHHMMSS.xlsx into the tag管理系统 online review queue, then running deterministic Validation tag cleanup, threat-group alias expansion, software/vendor bridging, official MITRE/CAPEC/CWE/NIST/OWASP enrichment, batch QA, and Excel export.
---

# Validation Excel Tag Import

Use this skill only for the `tag管理系统` project when the user provides a Validation tag workbook and asks to “按 validation 规则导入 / 打 tag / 走导入流程”.

## Target

- Rule set: `VALIDATION`.
- Destination: online review queue: `rules_main.status = PENDING`.
- Dictionary lane: `validation_base`.
- Official lane: `mitre_official_base`.
- Keep `VALIDATION` and `DETECTION` imports separate.

## Input Pattern

Expected workbook examples:

- A single sheet named `Tags`.
- Common columns: `type`, `uuid`, `vid`, `tag_type`, `tag`, `tag_en`, `name`, `desc`.
- `tag_type` may be empty. In that case infer from `tag` prefixes and text:
  - `Actor:*` -> `threat_group`
  - `Malware:*` -> `malware`
  - `CAMP.*` -> `campaign_nocn`
  - `ATT&CK:Txxxx` -> `mitre_techniques`
  - `ATT&CK:TAxxxx` or tactic names -> `mitre_tactics`
  - `ATT&CK:T0800-T0895` -> `ics_mitre_techniques`, not Enterprise `mitre_techniques`
  - `ATT&CK:TA0100-TA0111` -> `ics_mitre_tactics`, not Enterprise `mitre_tactics`
  - `Control:*` -> `control`
  - `OS:*` -> `os`
  - `RunAs:*` -> `run_as`
  - `Src:*+Dst:*` -> `src_destination`
  - `NIST:*` -> `nist_control`
  - `CWE-*` -> `cwe_nocn`
  - `CAPEC-*` -> `capec_nocn`

## Workflow

1. Inspect locally before writing.
   - Count rows and distinct `uuid`.
   - Print sheet names and first rows.
   - Confirm it is Validation content, not Detection.
   - If Excel/WPS visibly shows tag rows but `openpyxl` reports only `A1` or one row, do not conclude the tag file is empty. Some exported XLSX files have a stale worksheet `<dimension ref="A1">` even though the sheet XML contains thousands of rows.
     - Inspect `xl/workbook.xml` and `xl/_rels/workbook.xml.rels` to map visible sheet names to the actual `xl/worksheets/sheetN.xml`; internal filenames such as `sheet2.xml` are not user-visible “Sheet2”.
     - Count `<row>` elements and parse header cells directly from the target worksheet XML when the dimension is suspicious.
     - Normalize the workbook with a real writer such as `openpyxl` before upload/import, preserving the visible sheet name and rows. Never switch to a language-only generated workbook unless the source tag sheet truly has no tag rows after XML inspection.

2. Backup the online database.
   - Default host: `192.168.10.89`.
   - Default app root: `/home/dx/apps/tag-management-system`.
   - Store backup under `/home/dx/db_backups/`.
   - Name it like `before_validation_<file_stem>_import_<timestamp>.dump`.

3. Upload the workbook to the remote host.
   - Default upload path: `/tmp/<filename>`.

4. Import through `app.services.rule_import_v2.import_single_file_auto`.
   - Call the async function with:
     - `filename=<xlsx filename>`
     - `content=<xlsx bytes>`
     - `rule_set="VALIDATION"`
     - `user_id=<admin user id>`
   - Record `import_batch_id`, imported/skipped counts, and initial `tag_type_counts`.

5. Reuse Detection master `software`/`vendor`/`attack_name`/`attack_type` before any weak extraction. This is mandatory for every Validation tagging run.
   - For the new Validation batch, collect target UUIDs from `rules_main.raw_json.import_batch_id`.
   - Query the latest committed Detection master table (`master_table_version` newest version containing `DETECTION` entries).
   - For UUIDs that exist in Detection master, copy every `software`, `vendor`, `attack_name`, and `attack_type` tag from Detection master to the Validation pending rules before any title/source extraction. Do not copy only the first value when Detection has multiple values in one dimension.
   - These copied tags are authoritative reuse, not AI recommendations, and must happen before cleanup/enrichment scripts:
     - Preserve/reuse `tag_dict_id` when available.
     - If Detection master only has raw values, resolve them against same-lane approved `validation_base` dictionary rows by exact CN/EN/display match.
     - Do not mark copied Detection `software`/`vendor`/`attack_name`/`attack_type` tags yellow when they have a dictionary match.
   - Delete the target batch's previous `software`/`vendor`/`attack_name`/`attack_type` rows only for UUIDs that have Detection master replacements for that dimension, then insert the Detection-derived rows.
   - For UUIDs without a Detection master match, later title/source extraction may still propose these dimensions, but keep weak guesses unmapped/yellow unless same-lane dictionary matched.
   - If this step is skipped, the run is incomplete. Stop and report why Detection master reuse could not be performed.

6. Run Validation enrichment scripts in this order.
   - `python backend/scripts/backfill_validation_pending_cleanup.py`
   - `python backend/scripts/backfill_validation_pending_attack_tags.py`
   - `python backend/scripts/backfill_validation_pending_malware_from_title.py`
   - `python backend/scripts/backfill_validation_pending_software_vendor_from_other.py`
     - This script must not overwrite UUIDs whose `software`/`vendor` were already copied from Detection master.
   - `python backend/scripts/expand_validation_pending_threat_group_families.py`
     - Do not infer `threat_group` for generic Web/application vulnerability rules from product, vendor, path, software, or vulnerability words.
     - Accept `threat_group` only when the source tag is explicitly actor-like (`Actor:*`) or the rule title/text clearly contains actor context such as `威胁组织`, `Threat Group`, `APT`, `APT-`, `APT-U`, `UNC`, `TA`, `UAT`, `Storm`, etc.
     - Enforce this in code with `_should_infer_threat_group_from_text(...)` before any fallback from rule title, description, or `other` values. Do not rely on post-export manual QA alone.
     - After expansion, audit Web/application vulnerability rules (`Web应用程序漏洞`, `Web安全验证`, `AI应用程序漏洞`, `应用程序漏洞`) and remove `threat_group` plus derived `industries` when no explicit actor context exists.
   - After threat-group expansion, bridge `industries`/`industry` from the final `threat_group` tags using the approved threat-group-to-industry relationship table and same-lane `validation_base` industry dictionary. Do not stop after writing `threat_group`; if no industry sheet/tag rows are produced, explicitly report why.
   - `python backend/scripts/apply_vendor_from_software_to_pending_rules.py --rule-set VALIDATION --status PENDING --dict-version validation_base`
     - Skip UUIDs whose vendor was copied from Detection master unless the Detection master has no vendor and the software-to-vendor bridge is an exact dictionary relationship.
  - `python backend/scripts/apply_official_tags_to_pending_rules.py --rule-set VALIDATION --status PENDING`
    - This official bridge must cover all deterministic official dimensions, not only Enterprise ATT&CK:
      - `mitre_techniques` -> `official_mitre_techniques` and parent `official_mitre_tactics`.
      - `mitre_tactics` -> `official_mitre_tactics`.
      - `mitre_techniques` -> `ics_mitre_techniques` / `official_ics_mitre_techniques` when the IT technique appears in the approved `IT-to-ICS` bridge sheet, then add parent `ics_mitre_tactics` / `official_ics_mitre_tactics`.
      - `ics_mitre_techniques` -> `official_ics_mitre_techniques` and parent `official_ics_mitre_tactics`.
      - `ics_mitre_tactics` -> `official_ics_mitre_tactics`.
      - `capec_nocn` -> `official_capec_patterns`; also add `official_capec_categories` via official CAPEC category membership.
      - `cwe_nocn` -> `official_cwe`; when official CAPEC metadata contains `cwe_external_ids`, also bridge to related `official_capec_patterns` and their `official_capec_categories`.
    - OWASP hard scope: only rules whose title/metadata clearly indicates Web/application vulnerability (`Web应用程序漏洞`, `Web安全验证`, `应用程序漏洞`, `AI应用程序漏洞`, `Web Application Vulnerability`, `Application Vulnerability`) may receive `owasp` or `official_owasp_attacks`. Do not bridge CAPEC/CWE/text to OWASP for malicious file transfer, phishing email, host command line, protected sandbox, command-and-control, scanning, remote-service-vulnerability, or other non-Web/application-vulnerability rules. If the rule-name prefix is non-Web, it is a hard deny even when the description mentions application vulnerabilities.
    - The default local IT-to-ICS source is `tag字典_0603_split/IT-to-ICS.xlsx`, with `IT` and `ICS` columns. Only use complete `Txxxx` / `Txxxx.xxx` codes from that sheet; never infer ICS from prose.
    - If an IT-to-ICS mapped ICS code only exists in `mitre_official_base` but the same `validation_base` row is rejected/inactive, keep the official ICS tag green and leave the legacy `ics_mitre_*` row unmapped/yellow instead of forcing a rejected dictionary row.
    - If a batch has no source `CAPEC-*`, no source/direct-or-IT-mapped ICS, and no CWE-to-CAPEC relationship, report that no CAPEC/ICS values were bridgeable. Do not invent placeholder CAPEC or ICS tags.
  - After these scripts, run a same-lane unmapped audit. Link unmapped rows only when they deterministically match `validation_base` rows of the same `tag_type`.

7. QA only the new batch.
   - Filter by `rules_main.raw_json::text like '%<import_batch_id>%'`.
   - Count each `tag_type`: row count, distinct rules, distinct tags.
   - Confirm `industries`/`industry` exists when the batch has `threat_group` tags with known industry mappings. Missing industry after threat-group enrichment is a bug, not an optional omission.
   - Confirm Web/application vulnerability rows without explicit actor context have zero `threat_group` and zero derived `industries` rows. If the count is non-zero, clean it before export.
   - Confirm same-UUID Detection master reuse:
     - report how many UUIDs matched Detection master
     - report copied `software`/`vendor`/`attack_name`/`attack_type` row counts
     - copied rows with dictionary matches should not be yellow
     - fail the QA if Validation rows with Detection matches still use weaker title-extracted values for these four dimensions
   - Confirm OWASP scope:
     - `owasp` and `official_owasp_attacks` must be zero for non-Web/application-vulnerability rules.
     - If any non-Web/application-vulnerability row still has OWASP, run `python backend/scripts/cleanup_non_web_owasp_tags.py --rule-set VALIDATION --pending --dry-run`, inspect examples, then rerun without `--dry-run` for the target batch/status before export.
   - Inspect residual `other` values.
   - Do not leave structured or clearly classifiable values in `other`.
   - Audit highlighted/yellow cells before export:
     - `tag_dict_id IS NULL` should be yellow.
     - Same-lane dictionary misses should be fixed before delivery.
     - True no-dictionary values should remain yellow and be reported.
     - Common false-yellow: `mitre_mitigation` values like `ATT&CK:M1018` should match `validation_base.mitre_mitigation=M1018` after stripping `ATT&CK:`.
     - Do not force `ATT&CK:M1060` or any other value green when no same-lane dictionary row exists.
   - Run source/language/output reconciliation before export delivery. This is mandatory, not optional:
     - Prefer the bundled helper:
       `python ~/.codex/skills/tag-resolve/scripts/reconcile_validation_output.py --source-tags <source_tags.xlsx> --language <language.xlsx> --output <export.xlsx> --detection-master <detection_master.xlsx> --report <reconcile_report.xlsx>`
     - Compare output UUID set against the source tag workbook UUID set. Missing UUIDs, extra UUIDs, or UUID-only rule-name fallbacks are blocking unless explicitly accepted.
     - Compare `rule_name`/`rule_name_en` in output against the provided language workbook for overlapping UUIDs. Language workbook values should win over raw source names; mismatches must be explained.
     - Compare source structured values against output by UUID and dimension:
       - `CVE-*`, `CWE-*`, `CAPEC-*`, `ATT&CK:T*`, `ATT&CK:TA*`, `ATT&CK:M*`, `NIST:*`, `Control:*`, `OS:*`, `RunAs:*`, and `Src:*+Dst:*`.
      - Treat ICS ATT&CK codes separately: `T0800-T0895` must appear under `ics_mitre_techniques`/`official_ics_mitre_techniques`, and `TA0100-TA0111` must appear under `ics_mitre_tactics`/`official_ics_mitre_tactics`.
      - Treat IT-to-ICS bridge output as expected enrichment, not source mismatch: if a source Enterprise `mitre_techniques` code exists in `IT-to-ICS.xlsx`, verify the mapped ICS technique and parent ICS tactic are present.
      - When source has `CWE-*`, verify any generated CAPEC comes only from official CAPEC `cwe_external_ids` relationships; when source has `CAPEC-*`, verify `official_capec_patterns` and applicable `official_capec_categories` were generated.
       - Code-like identifiers must remain exact normalized codes; do not allow dictionary fuzzy rewrites or cross-row leakage.
     - Compare title/language CVE values against output `cve`. Every `CVE-YYYY-NNNN` in the final rule title should appear as the same CVE in output; unrelated CVE values are blocking.
     - Compare Detection master same-UUID reuse for `software`, `vendor`, `attack_name`, and `attack_type`. If Detection has rows for the UUID, output must contain those values unless there is an explicit audited reason not to.
     - The reconciliation report must list checked counts and blocking issue counts. If blocking issues are non-zero, fix and rerun before handing off the workbook.

8. Handle residual `other`.
   - If an `other` value appears in the rule name as a malware/tool family, promote it to `malware` as an unmapped/orange AI tag and delete the `other` mapping.
   - When promoting an `other` value to `malware`, also create or refresh the matching `malware_type` sheet/value if the type is known from source, title, dictionary, or the reviewed malware mapping. For webshell tools such as 中国菜刀 / CHINACHOP, 冰蝎 / BEHINDER, 哥斯拉 / GODZILLA, and 蚁剑 / ANTSWORD, use the existing dictionary spelling and `malware_type=黑客工具 / Hacking Tool` when approved.
   - Examples: `RegPhantom`, `VECT`, `Stealth Packer`, `PeerTime`.
   - Do not promote generic words such as `Download`, `Malicious Link`, `web`, `http`, timestamps, versions, or vulnerability category words.

9. Optional cleanup.
   - After manual residual classification, do not rerun `cleanup_validation_pending_unmapped_malware.py` unless the user explicitly wants unmapped malware removed.
   - If you run it earlier, re-check whether any useful malware names were deleted and restore batch-specific ones when needed.

10. Export the batch for inspection.
   - Use `app.services.excel_export.export_rules_to_excel`.
   - Parameters: `rule_set="VALIDATION"`, `status="PENDING"`, `import_batch_id=<batch_id>`, `limit=0`.
   - Save under remote `output/`, then copy to `~/Downloads/`.
   - The exported workbook must not freeze panes. If using `openpyxl`, explicitly ensure every worksheet has `freeze_panes = None`.
   - User-facing Excel deliverables must be written or modified with a real Excel writer such as `openpyxl`. Do not hand-generate XLSX XML/ZIP content when the user needs to open, inspect, or recognize formatting. The old pitfall was XML-generated files that looked structurally valid but lost visible yellow fills in WPS/Excel.
   - The exported workbook must include English fields:
     - summary sheet: `规则名称_en` plus `<tag_type>_en` next to every tag dimension
     - detail sheets: `规则名称_en` and `tag_en`
     - use dictionary `tag_en` first; for raw code-like unmapped values, repeat the code as EN; otherwise leave EN blank rather than inventing a translation
     - preserve imported source `tag_en` for unmapped/yellow tags. If the source tag workbook has `tag_en`, store it in `rules_main.raw_json.source_tag_en_map` or apply it during post-export repair; do not lose it just because `tag_dict_id` is NULL.
     - when source `tag_en` is empty but the standardized language workbook has an unambiguous English product name in `rule_name_en`, use that for `software` display English. Example: `Web Application Vulnerability - Lawyer eTong, ...` can fill `软件=律师 e 通` as `Lawyer eTong`.
     - do not invent vendor English names from pinyin or guesses. Vendor `tag_en` should come from dictionary/source data or remain blank if not reliable.
     - when deduplicating `software`, never keep a generic platform tag over a more specific product/plugin tag from the same rule title. Examples: keep `WordPress Perfmatters`, `WordPress s2Member`, or `WordPress Breeze Cache`; remove the generic `WordPress` for that UUID. Prefer the most specific product name that appears in the rule title, not the shortest label.
   - User-facing `source` columns must be readable. Do not expose internal implementation markers such as `source`, `other_to_malware_reclass_*`, `title_type_reclass_*`, or `malware_existing_inferred`; translate them to labels like `原始导入`, `从 other 重归类为 malware`, `根据规则名称补 malware_type`, `已有 malware 补充 malware_type`, or omit the column.
   - Verify the workbook after saving:
     - no frozen panes on any sheet
     - yellow count by sheet
     - sample yellow values for each sheet
     - `mitre_techniques` and `mitre_mitigation` have no false-yellow dictionary matches left
     - summary cells with mixed mapped and unmapped values are not filled yellow as a whole; exact yellow marking stays in the per-dimension detail sheet
     - MITRE/CVE/CWE/CAPEC/NIST code-like values are sorted by normalized code after stripping prefixes such as `ATT&CK:` and `NIST:`
     - If `threat_group` is present, include the bridged `industries`/`industry` dimension in the export as its own sheet and summary column.
   - Excel/WPS openability is mandatory, not optional:
     - Run `unzip -t <xlsx>` and fail fast on ZIP/package errors.
     - Scan with `openpyxl` for illegal control characters and cell text longer than Excel's 32,767 character limit.
     - If `libreoffice`/`soffice` is available, run a headless open-and-resave pass: `libreoffice --headless --convert-to xlsx --outdir <tmpdir> <xlsx>`, then deliver the resaved workbook. This catches files that `openpyxl` can read but Excel/WPS may refuse.
     - After LibreOffice resave, re-check sheet count, `freeze_panes`, and yellow fill counts. LibreOffice may normalize yellow from `00FFF59D` to `FFFFF59D`; treat both as valid yellow.
     - Do not hand off an Excel file to the user until this openability check passes.

## Optional Language Retag

When the user later provides a standardized language workbook such as
`YYYYMMDDHHMMSS-t_CN-EN_1_standardized.xlsx`, rerun the batch using the richer text.

1. Confirm UUID overlap.
   - Load `Actions`, `Email`, `Sequences`, and `Pipelines` sheets if present.
   - Count language UUIDs, batch UUIDs, and overlap.
   - Continue only when the target batch UUIDs are fully covered or the user accepts partial coverage.

2. Back up the database again.
   - Name it like `before_validation_<file_stem>_language_retag_<timestamp>.dump`.

3. Update only the target batch.
   - Locate the batch by `raw_json::text like '%<import_batch_id>%'`.
   - Replace `rule_name`, `rule_name_cn`, `description_cn`, `note_cn`, and corresponding English fields from the language workbook.
   - Do not touch other pending batches.

4. Rebuild weak dimensions from language text.
   - Delete old mappings for `attack_type`, `attack_name`, and bad/unmapped `malware` only for the target batch.
   - Do not blindly delete `software`/`vendor`/`attack_name`/`attack_type` copied from Detection master. Re-run the Detection master reuse step first and treat copied rows as authoritative. Only rebuild these dimensions from language text for UUIDs with no Detection master match.
   - Recreate `attack_type`/`attack_name` from Chinese rule titles:
     - `恶意文件传输` -> `attack_type=恶意文件下载`
     - `命令与控制` -> `attack_type=C&C回连`
     - `钓鱼邮件` -> `attack_type=钓鱼`; add `attack_name=恶意链接/恶意附件` only when explicitly present.
     - `主机命令行` with secret reading / theft / leakage -> `attack_type=数据泄露`; with collection/enumeration/recon -> `attack_type=信息收集`.
     - `应用程序漏洞` with privilege wording -> `attack_name=权限提升` and parent `attack_type=提权`.
   - For `software`, only use true affected application/vulnerability titles such as `应用程序漏洞 - Linux 内核...`; do not treat malware names, OS names, payload filenames, or sandbox scenario names as software.
   - Component vulnerability aliases must bridge to the approved software dictionary when present. `Log4j`, `Log4j2`, `Apache Log4j2`, and `Log4Shell` all map to `software=Apache Log4j`; do not report this as “Log4j dictionary missing”. If a rule also has a concrete affected product such as `GoAnywhere`, `Rundeck`, `Metabase`, `MobileIron`, or `Jamf Pro`, keep that product tag and additionally add `Apache Log4j`.
   - For `vendor`, bridge only when the software dictionary/metadata gives a confident vendor; do not invent vendor for Linux Kernel.
   - When the title clearly names an affected application or product but there is no `validation_base` dictionary row, keep it as an unmapped/yellow `software` tag instead of dropping it.
   - For vendor from title, only infer obvious product-owner names with strong textual evidence. Keep them unmapped/yellow unless a same-lane vendor dictionary row exists.

5. Restore and normalize malware.
   - Re-add source `Malware:*` values and obvious family names from language titles as unmapped/orange malware when dictionary rows do not exist.
   - Strip role/platform suffixes: `(Windows)`, `(Linux)`, `后门`, `释放器`, `加载器`, `勒索软件`, `木马`, `变种`.
   - Delete file-type noise such as `.EXE 文件`, `.DLL 文件`, `.SO 文件`, `.ELF 文件`, `.ZIP 文件`.
   - Do not keep generic words like `Download`, `Malicious Link`, `Backdoor`, `Loader`, `Trojan`, `RAT`, `Windows`, `Linux`, `Telegram`, `C2`, `C&C`.
   - Do not extract malware from behavior/action descriptions. Values like `Execute Shellcode`, `Dump SAM`, `Creates A Run Key`, `Registry Dump`, or command names are behaviors, not malware families.
   - After rebuilding malware, list remaining unmapped malware values and confirm they are real family names from source/title. If unsure, keep out rather than polluting the malware column.

6. Re-run deterministic yellow cleanup after language retag.
  - Normalize old MITRE mitigation display values:
    - `ATT&CK:M1018` -> dictionary `mitre_mitigation=M1018` when present in `validation_base`.
    - Keep unresolved values yellow when no same-lane row exists, for example `ATT&CK:M1060` if absent from all dictionaries.
    - Strip the `ATT&CK:` prefix generically before dictionary matching so that any `ATT&CK:M####` value resolves to `mitre_mitigation=M####`; same for `ATT&CK:T####` to `mitre_techniques` and `ATT&CK:TA####` to `mitre_tactics`. After normalization, unresolved values like `ATT&CK:M1060` stay yellow only when no same-lane row exists. Apply this normalization in the cleanup pass and/or as a one-shot DB patch when the import otherwise leaves `ATT&CK:`-prefixed rows on yellow.
   - Normalize old MITRE technique display values similarly:
     - `ATT&CK:T1027.008` or source text containing `T1027.008` -> dictionary row `T1027.008` when present.
   - Structured identifier tags must match complete normalized codes only:
     - `CVE-*` must stay as the exact extracted CVE and must not be rewritten through fuzzy dictionary fragments.
     - `CWE-*`, `CAPEC-*`, MITRE, ICS MITRE, NIST, and official-code dimensions must not use broad short-code keys such as `[A-Z]{2}-\d{2}` outside the dimension they belong to.
     - Specifically guard against corruptions such as `CVE-2026-23482` matching `VE-20` and becoming an unrelated row like `CVE-2002-1123`.

## Official Bridge Filter: Don't Require is_active=True (added 2026-09-17)

The official CWE / CAPEC / NIST / ICS bridges on the platform run via
`scripts/apply_official_tags_to_pending_rules.py` (and the related runtime
helpers `apply_official_cwe_to_review.py`, `apply_official_nist_to_review.py`,
`apply_capec_nocn_to_review.py`, `apply_official_owasp_attacks_from_capec_to_review.py`,
`expand_threat_group_alias_tags.py`, `expand_validation_pending_threat_group_families.py`,
`enrich_classified_with_official_tags.py`, `supplement_official_from_text_for_master_version.py`,
`backfill_validation_pending_software_vendor_from_other.py`).

**Filter the dictionary rows by `TagDictionary.review_status == "APPROVED"`, not by
`is_active == True`.** The `is_active` flag is unreliable in past dictionary
maintenance runs: rows are routinely flipped to `false` by sync/normalize scripts
that don't re-activate them, and that silently breaks every official bridge that
follows. The bridge only needs to know "this is an approved entry from a known
version" — both `is_active=True` and `is_active=null` rows are safe to consume. Use
`TagDictionary.is_active.isnot(False)` (or equivalent) so APPROVED entries are
picked up regardless of the active flag.

Dictionary-creation and dictionary-sync scripts (`create_official_*`,
`sync_official_*`, `normalize_official_cwe_display_names.py`,
`create_ai_recommend_attack_dictionaries.py`) legitimately want
`is_active == True` because they're trying to maintain currently-active entries
without clobbering deactivated ones. Leave those untouched.

**Recovery procedure when official rows are silently deactivated:** on the
platform, run

```sql
UPDATE tag_dictionary
SET is_active = true
WHERE tag_type IN (
  'official_cwe', 'official_capec_patterns', 'official_capec_categories',
  'official_ics_mitre_techniques', 'official_ics_mitre_tactics',
  'official_nist_controls'
)
AND is_active = false
AND review_status = 'APPROVED'
AND version_id IN (
  SELECT id FROM dictionary_version
  WHERE version_name IN ('mitre_official_base', 'validation_base')
);
```

then re-run `apply_official_tags_to_pending_rules.py --rule-set VALIDATION --status PENDING`.
   - Never use Detection dictionary rows to green a Validation tag. Cross-rule-set historical Detection rows may be copied only as raw suggestions unless there is a Validation dictionary match.


## Malware Extraction Discipline (added 2026-09-17)

When extracting malware names from rule titles during the validation tag import, the
platform scripts (`backfill_validation_pending_malware_from_title.py` and the inline
`_extract_malware_candidate_from_rule_name` in `app/services/rule_import_v2.py`) must
follow these rules to avoid polluting the malware dimension with action phrases and
non-malware tokens:

1. **Reject action phrases**: candidates whose first token matches an action verb
   (execute, load, detect, call, connect, download, upload, read, write, create, delete,
   modify, add, enumerate, extract, find, persist, establish, run, start, stop, kill,
   obtain, collect, monitor, bypass, escalate, deploy, send, receive, steal, exfiltrate,
   hide, perform — plus their -s/-ed/-ing variants) are techniques, not malware
   families. Reject before dictionary matching. Implemented via `_is_action_phrase_malware`
   helper which `_is_generic_malware_label` consults.

2. **Extract leading English prefix from mixed-language segments**: a rule like
   `恶意文件传输 - Aeternum 加载器 恶意软件，.DLL 文件，下载` should yield `Aeternum`
   as malware. Strip common Chinese role suffixes (加载器, 释放器, 后门, 木马, 恶意软件,
   勒索软件, 信标) and their English equivalents (beacon, loader, backdoor, trojan,
   malware, ransomware, dropper, sample), then try the leading alphanumeric prefix
   (>=3 chars). Without this, Chinese malware names get silently dropped.

3. **Skip unmatched candidates from the database**: `backfill_validation_pending_malware_from_title.py`
   inserts every extracted candidate regardless of dictionary match. This means
   vendor names (OPSWAT), file extensions (LNK), and driver file names
   (ProcessMonitorDriver.sys) end up yellow in the malware dimension. Either:
   - Filter insertion by `if matched is not None:` before insert, OR
   - Run a post-extraction cleanup that deletes malware tags whose
     `tag_dict_id IS NULL` AND whose value matches known non-malware patterns
     (vendor dictionary prefix, file extension like `.sys`/`.exe`/`.lnk`/`.dll`,
     threat group ID pattern).

4. **Dictionary hygiene**: the `validation_base.malware` dictionary should not
   contain threat group names (e.g., KIMSUKY is currently there but Kimsuky is a
   North Korean APT, not malware). Audit and clean during the next dictionary pass.

## Threat Group Family Expansion (added 2026-09-17)

`expand_validation_pending_threat_group_families.py` adds related actors via the
`family_lookup` dictionary. Watch for over-broad alias matching: a single UNC/APT
input can fan out to 10+ "related" actors because the family buckets key on
overlapping aliases. Before delivery, audit:
- For each rule with >5 threat_group tags, confirm each alias actually belongs to
  the same threat group cluster (e.g., Bohrium=APT37 vs ENSYNCROLL's APT-U1549).
- If a family bucket mixes unrelated groups (e.g., North Korean APT37 with Iranian
  APT-U1549), the dictionary's metadata_info.aliases is too loose and needs pruning.

## 和原文核对是底线（added 2026-09-18）

`产品版本 4.3.35.1` 是原文，**不能改成 `产品变种 #4.3.35.1`**；`Variant-1` 是原文，**不能改成 `变种-1` 然后又改成 `变种 #1` 自己造数据**。

**硬约束：任何加工前先和源 tag workbook 原文逐字段核对：**

- `description` (源 col 8) → `description_cn` (输出 col 4)：逐字符核对
- `name` (源 col 7) → `cn_name` (输出 col 2)：版本号/变种号/产品名/文件名/CVE 必须保留
- `name` 已有值 → 不许造新值、不许重命名

**禁用清单：**

- 不许把 `产品版本 X.Y.Z.W` 改写成 `产品变种 #X.Y.Z.W`（混淆术语：版本 ≠ 变种）
- 不许把 `(产品版本 4.3.35.1)` 重写成 `(产品变种 #4.3.35.1)`（加 `#`、换词）
- 不许把 `Variant-1` 改写后丢失 `Variant` 标识
- 不许把 `文件版本 11.11.4.0` 改写成 `文件变种 #11.11.4.0`
- 不许给 `变种 -1` / `Variant-1` 这种源数据中无 `#` 的格式补 `#`

**实施：标准化的 description 阶段必须读取源 tag workbook 的 description 原文，不要从其他行推断（推断可能导致版本号错位——比如 4.3.35.1 的描述被错误复用到 4.3.2.1 的行）。**

**校验步骤（输出前必跑）：**

```python
import openpyxl
src = openpyxl.load_workbook(SOURCE_TAG_XLSX, data_only=True)
std = openpyxl.load_workbook(STANDARDIZED_XLSX, data_only=True)
# 对每个 UUID：
# 1. src description == std description_cn 逐字符一致（或仅做 SKILL.md 列出的允许替换）
# 2. src name 里出现的所有版本号、变种号、产品名、文件版本号、cve、actor id 必须在 std cn_name + description_cn 里都出现
# 3. 任何 std 里有但 src 里没的「term」都标黄让人审
```

不通过校验的产物不出手。
## Reporting

Final response should include:

- Imported/skipped count and distinct rule count.
- `import_batch_id`.
- Backup path.
- Final important dimension counts.
- Whether `other` is zero.
- Local export path if created.
- Any unresolved ambiguous values.

## Guardrails

- Never mix this flow with Detection imports.
- Do not force weak vendor/software/malware guesses into green dictionary tags.
- Official tags must come from existing official dictionaries or deterministic bridge logic.
- Keep AI/raw recommendations unmapped/orange unless there is an approved dictionary match.
- If import fails, report the exception and retry only after fixing the function signature or bad input columns.
