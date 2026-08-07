---
name: tag-resolve
description: Meta workflow for tag deliverables in the tag管理系统 project. Use when the user asks to process, import, govern, classify, sync, merge, audit, export, or resolve Detection/Validation tags, including Validation tag Excel import, Detection JSON tag import, tag dictionary governance, official MITRE/CAPEC/CWE/OWASP/NIST mapping, scene tag aggregation from rule tags, and classified tag workbook synchronization into the online master table.
---

# Tag Resolve

Use this as the top-level router for tag-related work. Keep it separate from rule-name/description standardization and translation skills.

Bundled child skills live under `skills/` in this package. Prefer those bundled copies first so a downloaded `tag-resolve-skill` release is self-contained. Fall back to sibling standalone skills only when a bundled child skill is missing.

## Start Message

When this skill runs, tell the user:

`运行 <selected-child-skill> skill 处理 <task-summary>。如果有不清楚的地方，可以输入 help 或 帮助 获取 skill 使用说明。`

If the user asks `help` or `帮助`, reply with the Help section below and do not touch files or the online platform.

## Help

`tag-resolve` 是 tag 处理与 tag 同步总入口。它会先判断任务属于哪条 tag 流程，再按需检查线上 `tag管理系统` 平台是否可访问。

Common requests:

- Validation tag Excel 导入：使用 `validation-excel-tag-import`，处理 `tags_*.xlsx` 这类 Validation 单 Sheet tag 文件。
- Detection JSON tag 导入：使用 `detection-json-tag-import`，处理 Detection JSON 导出并导入线上待审核队列。
- tag 字典治理 / 官方映射：使用 `tag-governance-workflow`，处理字典、MITRE/CAPEC/CWE/OWASP/NIST 桥接、黄格/橙格审计。
- 场景 tag 聚合：使用 `scene-tag-from-rule-tags`，根据规则 tag 和 `seq_to_action` / `sequence_action` 映射给场景打 tag。
- tag 同步到总表：使用 `master-classified-merge`，把 classified tag workbook 合并成线上 Detection/Validation master table 新版本。

如果任务依赖线上平台但默认地址不可访问，我会停下来让用户确认平台地址，例如 `http://192.168.10.89:8080` 或后端 API 地址。

## Routing

Resolve the target child skill before doing work:

- `validation-excel-tag-import`: use for Validation single-sheet tag Excel files, pending review import, enrichment, QA, and export. Every Validation tagging route must first reuse Detection master same-UUID `software`, `vendor`, `attack_name`, and `attack_type` before weak extraction.
- `detection-json-tag-import`: use for Detection JSON exports, pending review import, enrichment, QA, and export.
- `tag-governance-workflow`: use for dictionary governance, official mapping, review-table enrichment, yellow/orange unmapped audits, alias dictionary sync, and classified workbook supplementation that does not mutate the online master table.
- `scene-tag-from-rule-tags`: use for scene/scenario tag generation from rule tags and sequence/action mapping workbooks.
- `master-classified-merge`: use for tag sync / classified merge into the online master table, including new master-table versions and dictionary sync scoped to the current workbook.

After choosing the child skill, resolve it in this order:

1. bundled child skill: `~/.codex/skills/tag-resolve/skills/<child-skill>/SKILL.md`
2. sibling standalone skill: `~/.codex/skills/<child-skill>-standalone/SKILL.md`
3. legacy sibling skill, if still present: `~/.codex/skills/<child-skill>/SKILL.md`
4. if none exists, stop and report the missing child skill

Read the resolved child skill's `SKILL.md` completely. When the bundled child skill contains scripts, resolve relative script paths from that bundled child skill directory, not from a sibling standalone skill.

## Platform Preflight

Before any task that reads from or writes to the online `tag管理系统`, run:

```bash
python3 ~/.codex/skills/tag-resolve/scripts/preflight.py --require-platform
```

Use `--base-url` when the user provides a platform address:

```bash
python3 ~/.codex/skills/tag-resolve/scripts/preflight.py --require-platform --base-url http://192.168.10.89:8080
```

Environment overrides are also allowed: `TAG_RESOLVE_BASE_URL`, `TAG_PLATFORM_BASE_URL`, `TAG_SYSTEM_BASE_URL`, `TAG_API_BASE_URL`, or `TAGSYS_BASE_URL`.

If preflight cannot reach the platform, stop and ask the user to confirm the platform address before continuing. Do not guess, import, sync, or mutate online data while the platform address is unconfirmed.

For local-only workbook inspection, local dictionary drafting, or help output, platform preflight is optional. If the task later becomes online import/sync/export, run preflight before that step.

## Language Workbook Check

Before tag import, batch tagging, classified merge, or master-table sync, check whether the user provided a matching language workbook/table, such as a standardized `*-t_CN-EN_*.xlsx` file or another workbook containing rule names/descriptions.

If no language workbook/table is provided, pause before online mutation and remind the user:

`这次没有导入 language 表。是否需要一起导入 language 表来补规则名称、英文名称和描述？如果不导入，新增或缺少元数据的 UUID 可能会出现规则名/描述不完整。`

Continue without the language workbook only after the user confirms, or when the child skill proves the current input already contains complete rule metadata. For master-table sync, missing language metadata is high risk because newly appended UUIDs can become UUID-only rows.

## Guardrails

- Keep `DETECTION` and `VALIDATION` lanes separate. Do not mix dictionaries, pending queues, master versions, or export assumptions.
- Local workbook tagging is local-only unless the user explicitly asks to import, sync, merge, or update the online platform. A request like `打tag` must not mutate online pending queues, dictionaries, or master tables as a side effect.
- For Validation tagging, same-UUID Detection master reuse is mandatory before enrichment: copy every same-dimension `software`, `vendor`, `attack_name`, and `attack_type` value from the latest committed Detection master when available. Do not collapse multi-valued Detection tags to the first value. If this cannot be done, stop and report why instead of silently falling back to weak title extraction.
- Never use rule standardization or translation logic here unless the child tag skill explicitly asks for standardized language workbooks as metadata input.
- Back up the online database before imports, merges, or dictionary mutations when the child skill requires it.
- Prefer deterministic dictionary/official bridges before AI inference. Do not turn weak guesses into green mapped tags.
- Software component aliases must be resolved through the approved dictionary before reporting misses. In particular, `Log4j`, `Log4j2`, `Apache Log4j2`, and `Log4Shell` bridge to `software=Apache Log4j`; keep any concrete affected product tag and add `Apache Log4j` as the component software.
- Structured identifier tags must be exact-code only. `cve`, `cwe_nocn`, `capec_nocn`, MITRE, ICS MITRE, NIST, and official-code dimensions must never use broad short-code fuzzy dictionary keys; for example, never let `CVE-2026-23482` match a generic fragment like `VE-20` and turn into another CVE.
- Official enrichment must include CAPEC and ICS, not only Enterprise ATT&CK: `CAPEC-*` and official CWE related-weakness mappings bridge to `official_capec_patterns/categories`; direct ICS codes `T0800-T0895` and `TA0100-TA0111` bridge to `official_ics_mitre_techniques/tactics`; Enterprise IT techniques must also be checked against the approved `IT-to-ICS` mapping sheet (for this repo: `tag字典_0603_split/IT-to-ICS.xlsx`) and bridge matching IT `mitre_techniques` to `ics_mitre_techniques`, `official_ics_mitre_techniques`, and their parent ICS tactics. Do not report zero ICS merely because the source has no direct ICS code. If no source or official/mapping relationship exists, report zero bridgeable values instead of inventing tags.
- Validation rules whose Chinese or English title is clearly `命令与控制` / `Command and Control` must carry `ics_mitre_tactics=TA0101 - 命令与控制 / TA0101 - Command and Control` when the same-lane dictionary row exists. T20/DNS/ICS audits must check all title-matching rules, not only the small subset already found by DNS heuristics.
- OWASP is strictly scoped to Web/application vulnerability rules. Only rules whose names/metadata clearly indicate `Web应用程序漏洞`, `Web安全验证`, `应用程序漏洞`, `AI应用程序漏洞`, `Web Application Vulnerability`, or `Application Vulnerability` may have `owasp` or `official_owasp_attacks`. Rule names with non-Web prefixes such as `恶意文件传输`, `钓鱼邮件`, `主机命令行`, `受保护的沙盘`, `命令与控制`, `扫描活动`, or `远程服务漏洞` must never keep or receive OWASP tags, even if their descriptions mention application vulnerabilities or CAPEC/CWE could bridge to OWASP. After every import/merge/enrichment, run or document an OWASP scope QA and remove non-Web OWASP tags.
- Web/application vulnerability rules must not be left with `control=WAF` only. For `Web应用程序漏洞`, `Web安全验证`, `应用程序漏洞`, `AI应用程序漏洞`, `Web Application Vulnerability`, or `Application Vulnerability`, use the current same-lane control dictionary and ensure the baseline controls include `WAF`, `NGFW`, and `IDS/IPS`; add `NTA/NDR` only when traffic/behavior analysis is appropriate, and add `RASP` only for runtime application protection scenarios. After every import/merge/enrichment, QA for Web rules whose only control is `WAF` and fix them or report them as blocking review items.
- Control enrichment must follow the project control matrix by rule prefix/context, with prefix priority before keyword fallback. `钓鱼邮件` / `Phishing Email` always maps only to `Email`, even when the title contains `恶意附件` or `Malicious attachment`; do not apply the malicious-file-transfer control set to phishing rows. Current matrix: Web/application vulnerability prefixes (`应用程序漏洞`, `Web安全验证`, `SQL注入`, `WAF绕过`, `Web应用程序漏洞`, `XXX攻防演练`, `Web Shell 活动`, `AI应用程序漏洞`, `远程服务漏洞`, `OWASP`) -> `WAF`, `IDS/IPS`, `NGFW`, `NTA/NDR`; `命令与控制` + DNS query -> `DNS`, `NGFW`, `Proxy`, `NTA/NDR`; `命令与控制` + C&C/通信/信标/签到/Beacon/变种 -> `IDS/IPS`, `NGFW`, `NTA/NDR`, `Proxy`; `恶意文件传输` or `美国NSA网络武器` -> `AV`, `EDR/XDR`, `IDS/IPS`, `NGFW`, `Proxy`; `拒绝服务` -> `IDS/IPS`, `NGFW`, `NTA/NDR`; `云验证` -> `CSPM`, `HIDS`; `数据泄漏` -> `DLP`, `IDS/IPS`, `NGFW`, `NTA/NDR`, `Proxy`; `横向移动` -> `IDS/IPS`, `NGFW`, `NTA/NDR`; `捕获的IOC`, `DNS隧道`, and `利用套件(EK)活动` -> `IDS/IPS`, `NGFW`, `NTA/NDR`, `Proxy`; `Active Directory` / `AD` pcap rules -> `IDS/IPS`, `NGFW`, `NTA/NDR`; `容器安全` -> `Container`.
- Host and sandbox control enrichment must use OS, single/double-host, and dependency-file context instead of a single broad default. `主机命令行` Linux single-host -> `HIDS`; Linux double-host -> `HIDS`, `IDS/IPS`, `NGFW`, `NTA/NDR`; Windows/macOS single-host with dependency file -> `AV`, `EDR/XDR`; Windows/macOS single-host without dependency file -> `EDR/XDR`; Windows/macOS double-host with dependency file -> `AV`, `EDR/XDR`, `IDS/IPS`, `NGFW`, `NTA/NDR`; Windows/macOS double-host without dependency file -> `EDR/XDR`, `IDS/IPS`, `NGFW`, `NTA/NDR`. `受保护的沙盘` Windows single-host with dependency file -> `AV`, `EDR/XDR`; without dependency file -> `EDR/XDR`. `IOT安全` / `OT安全` malicious-file-transfer cases use the malicious-file-transfer control set, while vulnerability/CVE cases use the Web/application vulnerability control set.
- OWASP Top 10 keeps the official 2021 and 2025 lists side by side. Normalize old bare labels to versioned 2021 labels, e.g. `A01 - Broken Access Control` -> `A01:2021 - Broken Access Control`; do not keep generic `OWASP Top 10` or legacy labels such as `OWASP A1 Injection`.
- For categories that exist in both 2021 and 2025, keep both tags on the rule when one side is present: `A01:2021` <-> `A01:2025`, `A02:2021` <-> `A04:2025`, `A03:2021` <-> `A05:2025`, `A04:2021` <-> `A06:2025`, `A05:2021` <-> `A02:2025`, `A07:2021` <-> `A07:2025`, `A08:2021` <-> `A08:2025`, `A09:2021` <-> `A09:2025`.
- Do not infer `A03:2025 - Software Supply Chain Failures` or `A10:2025 - Mishandling of Exceptional Conditions` from 2021 tags or heuristics. Only add those two 2025 tags when a user-provided rule-to-label correspondence table explicitly contains them. Never map `A10:2021 - Server-Side Request Forgery (SSRF)` directly to `A10:2025`.
- After every generated tag workbook, run source/language reconciliation before delivery: compare output UUIDs, rule names, source structured tags, CVE/CWE/CAPEC/MITRE/NIST exact codes, and Validation same-UUID Detection reuse against the original tag workbook and language workbook. Do not deliver if the reconciliation has blocking mismatches.
- Yellow/orange cells mean unmapped values. First try same-lane, same-dimension dictionary matches; if no match exists, keep them highlighted and report examples.
- `other` is not a dumping ground. Reclassify clearly classifiable values into the correct dimension before delivery. If a residual `other` value is confirmed as a malware/tool family from source tags, dictionary, or rule title, move it to `malware`, create/refresh the matching `malware_type` when the type is known, and remove it from `other`. Keep unrelated context/noise such as model names, timestamps, versions, generic protocol words, or ambiguous product text out of `malware`.
- User-facing workbooks must not expose internal script markers. Do not leave `source` values such as `other_to_malware_reclass_*`, `title_type_reclass_*`, or similar implementation labels in exported sheets; translate them to readable labels such as `从 other 重归类为 malware`, `根据规则名称补 malware_type`, or omit the column.
- For master-table sync, always create a new version; do not mutate an existing committed version directly.
- Do not run broad historical dictionary sync while merging a current workbook unless the user explicitly asks. Scope dictionary additions to the current lane and input.
- Validate generated Excel deliverables with a real Excel writer/openability check before handing them over.

## Finish

Report:

- selected child skill and why
- platform preflight result, including the confirmed base URL if used
- files produced or online version/batch IDs created
- important counts and unresolved tag decisions
- whether any online mutation was skipped because the platform address was not confirmed
