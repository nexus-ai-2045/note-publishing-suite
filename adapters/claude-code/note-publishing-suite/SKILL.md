---
name: note-publishing-suite
description: "Use when the user wants repo-local, end-to-end Note publishing support: idea intake, local source review, skeleton and draft production, top-image and tag planning, local prepublish QA, Note editor handoff, publication gate, post-publish verification, and local ledger updates. Also use for Japanese requests such as \"note投稿を一気通貫\", \"Note投稿パッケージ\", \"note公開前チェック\", \"note台帳\", \"Note下書きから公開後まで\", \"noteスキル群\", \"note投稿\", \"note下書き\"."
---

# Note Publishing Suite — Claude Code Pointer

## 正本

正本を Read してからその内容に従うこと:
`{{PACKAGE_ROOT}}/SKILL.md`

## Codex 記述の読み替え

Codex 前提の記述は次のように読み替える: file editor→Read tool / Codex worker(spark)→Task tool subagent / repo root→`{{PACKAGE_ROOT}}`

## 作業場所 (採用settingsを優先)

`{{WORKSPACE_ROOT}}` は初回設定の起点です。正本の初回設定手順でsettingsを読み戻し、原稿は `storage.drafts`、台帳は採用済みの `storage.ledgers` を使います。台帳先が未指定なら既存台帳を本人に確認し、固定パスへ補完しません。本人が編集中の原稿正本は移動しません。

scriptsは `{{PACKAGE_ROOT}}/scripts` を使います。packageへ実原稿・台帳を保存せず、pointerでsettingsの保存先を上書きしません。

## 子スキル Routing 早見表

| phase | 子スキル | 停止条件 |
|---|---|---|
| idea | note-idea-intake | 読んでよい素材が未指定 |
| draft | note-draft-production | 根拠不足・権利/秘密情報リスク |
| qa | note-prepublish-qa | 警告・未確認・内部メモ残り |
| editor | note-editor-prepublish | browser/画像 upload 境界 |
| gate | note-publication-gate | 明示承認なし |
| ledger | note-postpublish-ledger | 公開 URL/status 未確認 |

## 公開 Gate

`publication_gate: human_review_required` — 公開・予約投稿・外部送信ボタンは押さない。現在の会話で対象記事と操作を特定した明示承認があるまで実行しない。
