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

## 作業場所 (SSOT 維持・台帳二重化禁止)

package 内の空雛形ではなく、既存正本ディレクトリを使う。

| 用途 | 実際に使うパス |
|---|---|
| content/drafts | {{WORKSPACE_ROOT}}/content/drafts |
| data 台帳 | {{WORKSPACE_ROOT}}/data |
| scripts | {{WORKSPACE_ROOT}}/scripts |

## 公開 gate

公開・予約投稿・SNS 共有・外部告知ボタンは押さない。明示承認必須 (`human_review_required`)。
