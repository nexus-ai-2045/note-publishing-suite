---
name: note-postpublish-ledger
description: "Use inside note-publishing-suite after explicitly approved Note publication or scheduled publication to verify status and update local ledgers. トリガ語: note台帳更新 / note公開後チェック"
---

# note-postpublish-ledger (Claude Code pointer)

## 正本を先に読む

作業前に必ず Read tool で正本を読み、手順・台帳・禁止・停止条件をすべてそちらに従う:

```
{{PACKAGE_ROOT}}/skills/note-postpublish-ledger/SKILL.md
```

## Codex 前提の読み替え

正本中の Codex 前提の記述は Claude Code では次のように読み替える:
- file editor → Read tool
- Codex worker (spark) → Task tool subagent
- repo root → {{WORKSPACE_ROOT}}

## 作業場所 (SSOT 優先・台帳二重化禁止)

content/drafts・data 台帳・scripts は package 内の空雛形ではなく既存正本を使う:
- drafts: `{{WORKSPACE_ROOT}}/content/drafts`
- data 台帳: `{{WORKSPACE_ROOT}}/data`
- scripts: `{{WORKSPACE_ROOT}}/scripts`

## 公開 gate

公開・予約・外部送信ボタンは押さない。明示承認必須 (human_review_required)。
