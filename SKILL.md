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

- `validation-excel-tag-import`: use for Validation single-sheet tag Excel files, pending review import, enrichment, QA, and export.
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
- Never use rule standardization or translation logic here unless the child tag skill explicitly asks for standardized language workbooks as metadata input.
- Back up the online database before imports, merges, or dictionary mutations when the child skill requires it.
- Prefer deterministic dictionary/official bridges before AI inference. Do not turn weak guesses into green mapped tags.
- Yellow/orange cells mean unmapped values. First try same-lane, same-dimension dictionary matches; if no match exists, keep them highlighted and report examples.
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
