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

## 作業場所 (SSOT 優先)

正本 SKILL.md の content/drafts・data 台帳・scripts は package 内の空雛形ではなく以下の既存正本を使う (台帳二重化禁止):

- drafts: `{{WORKSPACE_ROOT}}/content/drafts`
- data 台帳: `{{WORKSPACE_ROOT}}/data`
- scripts: `{{WORKSPACE_ROOT}}/scripts`

## 公開 gate

**human_review_required**: 公開/予約/外部送信ボタンは押さない。明示承認必須。
