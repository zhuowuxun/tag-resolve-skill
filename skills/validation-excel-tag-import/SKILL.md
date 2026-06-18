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
  - `Control:*` -> `control`
  - `OS:*` -> `os`
  - `RunAs:*` -> `run_as`
  - `Src:*+Dst:*` -> `src_destination`
  - `NIST:*` -> `nist_control`
  - `CWE-*` -> `cwe_nocn`

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

5. Reuse Detection master `software`/`vendor` before any weak extraction.
   - For the new Validation batch, collect target UUIDs from `rules_main.raw_json.import_batch_id`.
   - Query the latest committed Detection master table (`master_table_version` newest version containing `DETECTION` entries).
   - For UUIDs that exist in Detection master, copy only `software` and `vendor` tags from Detection master to the Validation pending rules.
   - These copied tags are authoritative reuse, not AI recommendations:
     - Preserve/reuse `tag_dict_id` when available.
     - If Detection master only has raw values, resolve them against same-lane approved `validation_base` dictionary rows by exact CN/EN/display match.
     - Do not mark copied Detection `software`/`vendor` tags yellow when they have a dictionary match.
   - Delete the target batch's previous `software`/`vendor` rows only for UUIDs that have Detection master replacements, then insert the Detection-derived rows.
   - For UUIDs without a Detection master match, later title/source extraction may still propose `software`/`vendor`, but keep weak guesses unmapped/yellow unless same-lane dictionary matched.

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
   - After these scripts, run a same-lane unmapped audit. Link unmapped rows only when they deterministically match `validation_base` rows of the same `tag_type`.

7. QA only the new batch.
   - Filter by `rules_main.raw_json::text like '%<import_batch_id>%'`.
   - Count each `tag_type`: row count, distinct rules, distinct tags.
   - Confirm `industries`/`industry` exists when the batch has `threat_group` tags with known industry mappings. Missing industry after threat-group enrichment is a bug, not an optional omission.
   - Confirm Web/application vulnerability rows without explicit actor context have zero `threat_group` and zero derived `industries` rows. If the count is non-zero, clean it before export.
   - Confirm same-UUID Detection master reuse:
     - report how many UUIDs matched Detection master
     - report copied `software`/`vendor` row counts
     - copied rows with dictionary matches should not be yellow
   - Inspect residual `other` values.
   - Do not leave structured or clearly classifiable values in `other`.
   - Audit highlighted/yellow cells before export:
     - `tag_dict_id IS NULL` should be yellow.
     - Same-lane dictionary misses should be fixed before delivery.
     - True no-dictionary values should remain yellow and be reported.
     - Common false-yellow: `mitre_mitigation` values like `ATT&CK:M1018` should match `validation_base.mitre_mitigation=M1018` after stripping `ATT&CK:`.
     - Do not force `ATT&CK:M1060` or any other value green when no same-lane dictionary row exists.

8. Handle residual `other`.
   - If an `other` value appears in the rule name as a malware/tool family, promote it to `malware` as an unmapped/orange AI tag and delete the `other` mapping.
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
   - Do not blindly delete `software`/`vendor` copied from Detection master. Re-run the Detection master reuse step first and treat copied rows as authoritative. Only rebuild `software`/`vendor` from language text for UUIDs with no Detection master match.
   - Recreate `attack_type`/`attack_name` from Chinese rule titles:
     - `恶意文件传输` -> `attack_type=恶意文件下载`
     - `命令与控制` -> `attack_type=C&C回连`
     - `钓鱼邮件` -> `attack_type=钓鱼`; add `attack_name=恶意链接/恶意附件` only when explicitly present.
     - `主机命令行` with secret reading / theft / leakage -> `attack_type=数据泄露`; with collection/enumeration/recon -> `attack_type=信息收集`.
     - `应用程序漏洞` with privilege wording -> `attack_name=权限提升` and parent `attack_type=提权`.
   - For `software`, only use true affected application/vulnerability titles such as `应用程序漏洞 - Linux 内核...`; do not treat malware names, OS names, payload filenames, or sandbox scenario names as software.
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
   - Normalize old MITRE technique display values similarly:
     - `ATT&CK:T1027.008` or source text containing `T1027.008` -> dictionary row `T1027.008` when present.
   - Never use Detection dictionary rows to green a Validation tag. Cross-rule-set historical Detection rows may be copied only as raw suggestions unless there is a Validation dictionary match.

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
