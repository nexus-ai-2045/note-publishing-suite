---
name: note-prepublish-qa
description: "Use inside note-publishing-suite to run local preview, pre-publish checks, fact checks, and optional Note/public diff checks before editor work or publication. (トリガ語: note公開前チェック / note下書き検査)"
---

# note-prepublish-qa — Claude Code pointer

正本を Read してから従うこと:

```
Read: {{PACKAGE_ROOT}}/skills/note-prepublish-qa/SKILL.md
```

## Codex → Claude Code 読み替え

| Codex 前提の記述 | Claude Code での読み替え |
|---|---|
| file editor | Read tool |
| Codex worker (spark) | Task tool subagent |
| repo root | {{WORKSPACE_ROOT}} |

## 作業場所の上書き (SSOT 維持・台帳二重化禁止)

package 内の空雛形ではなく既存正本を使う:

- content/drafts → `{{WORKSPACE_ROOT}}/content/drafts`
- data 台帳 → `{{WORKSPACE_ROOT}}/data`
- scripts → `{{WORKSPACE_ROOT}}/scripts`

## 公開 gate

公開・予約・外部送信ボタンは押さない。明示承認必須 (human_review_required)。
