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

## 作業場所 (採用settingsを優先)

`{{WORKSPACE_ROOT}}` は初回設定の起点です。正本の初回設定手順でsettingsを読み戻し、原稿は `storage.drafts`、台帳は採用済みの `storage.ledgers` を使います。台帳先が未指定なら既存台帳を本人に確認し、固定パスへ補完しません。本人が編集中の原稿正本は移動しません。

scriptsは `{{PACKAGE_ROOT}}/scripts` を使います。packageへ実原稿・台帳を保存せず、pointerでsettingsの保存先を上書きしません。

## 公開 gate (human_review_required)

公開・予約・外部送信ボタンは押さない。明示承認必須。
