---
name: note-idea-intake
description: "Use inside note-publishing-suite when selecting local materials and producing Note article candidates before drafting. トリガ語: note投稿 / note下書き"
---

# note-idea-intake (Claude Code pointer)

## 正本

正本を必ず先に Read してから従うこと:

```
{{PACKAGE_ROOT}}/skills/note-idea-intake/SKILL.md
```

正本の手順・入力・出力・停止条件・Closeout Evidence をそのまま適用する。

## Codex 記述の読み替え (Claude Code 用)

| 正本の表現 | Claude Code での読み替え |
|---|---|
| file editor | Read tool |
| Codex worker / spark | Task tool subagent |
| repo root | {{WORKSPACE_ROOT}} |

## 作業場所の上書き (SSOT 維持・台帳二重化禁止)

正本に `content/drafts` / `data/` / `scripts/` とある場合、package 内の空雛形ではなく既存正本を使う:

- drafts: `{{WORKSPACE_ROOT}}/content/drafts`
- data 台帳: `{{WORKSPACE_ROOT}}/data`
- scripts: `{{WORKSPACE_ROOT}}/scripts`

## 公開 gate

公開 / 予約 / 外部送信ボタンは押さない。明示承認必須 (human_review_required)。
