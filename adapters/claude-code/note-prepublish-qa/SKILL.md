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

## 作業場所 (採用settingsを優先)

`{{WORKSPACE_ROOT}}` は初回設定の起点です。正本の初回設定手順でsettingsを読み戻し、原稿は `storage.drafts`、台帳は採用済みの `storage.ledgers` を使います。台帳先が未指定なら既存台帳を本人に確認し、固定パスへ補完しません。本人が編集中の原稿正本は移動しません。

scriptsは `{{PACKAGE_ROOT}}/scripts` を使います。packageへ実原稿・台帳を保存せず、pointerでsettingsの保存先を上書きしません。

## 公開 gate

公開・予約・外部送信ボタンは押さない。明示承認必須 (human_review_required)。
