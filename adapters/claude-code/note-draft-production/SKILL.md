---
name: note-draft-production
description: "Use inside note-publishing-suite when creating skeletons, Note drafts, top-image ideas, and tag candidates from approved local materials. トリガー語: note下書き / note投稿準備"
---

# note-draft-production (pointer)

> 正本を Read してから従うこと。本 file は pointer。手順・境界は正本が SSOT。

## 正本

```
{{PACKAGE_ROOT}}/skills/note-draft-production/SKILL.md
```

セッション開始時に上記 path を Read tool で読み込み、記載の手順・境界・出力仕様に従う。

## Codex 記述の Claude Code 読み替え

| Codex 前提 | Claude Code での読み替え |
|---|---|
| file editor | Read tool |
| Codex worker (spark) | Task tool subagent |
| repo root | {{WORKSPACE_ROOT}} |

## 作業場所 (採用settingsを優先)

`{{WORKSPACE_ROOT}}` は初回設定の起点です。正本の初回設定手順でsettingsを読み戻し、原稿は `storage.drafts`、台帳は採用済みの `storage.ledgers` を使います。台帳先が未指定なら既存台帳を本人に確認し、固定パスへ補完しません。本人が編集中の原稿正本は移動しません。

scriptsは `{{PACKAGE_ROOT}}/scripts` を使います。packageへ実原稿・台帳を保存せず、pointerでsettingsの保存先を上書きしません。

## 公開 gate

公開・予約投稿・SNS 共有・外部告知ボタンは押さない。明示承認必須 (`human_review_required`)。
