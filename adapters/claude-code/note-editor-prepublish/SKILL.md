---
name: note-editor-prepublish
description: "Repo-local wrapper for using the global note-editor-prepublish skill during Note editor reflection, formatting, save, and pre-publication verification. トリガー: note投稿 / note公開前チェック"
---

# note-editor-prepublish (pointer)

正本を Read してから従うこと:

`{{PACKAGE_ROOT}}/skills/note-editor-prepublish/SKILL.md`

## Codex → Claude Code 読み替え

| Codex 記述 | Claude Code での読み替え |
|---|---|
| file editor | Read tool |
| Codex worker (spark) | Task tool subagent |
| repo root | {{WORKSPACE_ROOT}} |

## 作業場所 (採用settingsを優先)

`{{WORKSPACE_ROOT}}` は初回設定の起点です。正本の初回設定手順でsettingsを読み戻し、原稿は `storage.drafts`、台帳は採用済みの `storage.ledgers` を使います。台帳先が未指定なら既存台帳を本人に確認し、固定パスへ補完しません。本人が編集中の原稿正本は移動しません。

scriptsは `{{PACKAGE_ROOT}}/scripts` を使います。packageへ実原稿・台帳を保存せず、pointerでsettingsの保存先を上書きしません。

## 公開 gate

**human_review_required**: 公開/予約/外部送信ボタンは押さない。明示承認必須。
