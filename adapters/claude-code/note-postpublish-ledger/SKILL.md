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

## 作業場所 (採用settingsを優先)

`{{WORKSPACE_ROOT}}` は初回設定の起点です。正本の初回設定手順でsettingsを読み戻し、原稿は `storage.drafts`、台帳は採用済みの `storage.ledgers` を使います。台帳先が未指定なら既存台帳を本人に確認し、固定パスへ補完しません。本人が編集中の原稿正本は移動しません。

scriptsは `{{PACKAGE_ROOT}}/scripts` を使います。packageへ実原稿・台帳を保存せず、pointerでsettingsの保存先を上書きしません。

## 公開 gate

公開・予約・外部送信ボタンは押さない。明示承認必須 (human_review_required)。
