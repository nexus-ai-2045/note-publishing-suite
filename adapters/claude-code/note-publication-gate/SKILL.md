---
name: note-publication-gate
description: "Use inside note-publishing-suite immediately before any Note publish or scheduled publish action. note投稿 / note公開前チェック"
---

# note-publication-gate (Claude Code pointer)

## 正本

以下を Read してから従う:

```
{{PACKAGE_ROOT}}/skills/note-publication-gate/SKILL.md
```

## 作業場所の上書き (SSOT 維持・台帳二重化禁止)

package 内の空雛形は使わない。既存正本を使う:

- content/drafts → `{{WORKSPACE_ROOT}}/content/drafts`
- data 台帳 → `{{WORKSPACE_ROOT}}/data`
- scripts → `{{WORKSPACE_ROOT}}/scripts`

## 公開 gate (human_review_required)

公開・予約・外部送信ボタンは押さない。明示承認必須。
