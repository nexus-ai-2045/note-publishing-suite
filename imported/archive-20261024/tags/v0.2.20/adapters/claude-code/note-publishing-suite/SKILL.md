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

## 作業場所の上書き (SSOT 維持・台帳二重化禁止)

正本の content/drafts・data・scripts は package 内の空雛形ではなく既存正本を使う。

- content/drafts: `{{WORKSPACE_ROOT}}/content/drafts`
- data 台帳: `{{WORKSPACE_ROOT}}/data`
- scripts: `{{WORKSPACE_ROOT}}/scripts`

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
