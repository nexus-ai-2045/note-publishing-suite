---
name: note-idea-intake
description: "Use inside note-publishing-suite when selecting local materials and producing Note article candidates before drafting."
---

# note-idea-intake

## 役割

ユーザーが選んだローカル資料だけを読み、Note 記事候補を出す。

## 入力

- 読んでよい素材フォルダ。
- 想定読者、テーマ、公開目的。未指定なら Unknown。
- 既存 draft / published ledger を見る必要がある場合は `data/note_drafts.json` と `data/published_notes.json`。

## 手順

1. 選択フォルダ外を読まない。
2. ファイル名、更新日、見出し、未完成メモ、公開済み記事とのつながりを確認する。
3. 既存 draft と published ledger は必要な時だけ読む。
4. 候補ごとに `title`、`reader`、`promise`、`source_hint`、`why_now`、`angle`、`risk_or_check` を出す。
5. 秘密情報、個人情報、未承認の外部情報が混ざる候補は除外または要確認にする。
6. 推奨候補は最大 3 件に絞り、次に読む素材を明記する。

## 停止条件

- 読んでよい素材フォルダが未指定。
- public URL や Note editor を読む必要があるが承認がない。
- 候補の根拠がローカルに見つからない。

## 出力

```text
探し方:
- ...

記事候補:
1. title:
   reader:
   promise:
   source_hint:
   why_now:
   angle:
   risk_or_check:

おすすめ上位:
- ...

次に読む素材:
- ...
```

## Closeout Evidence

- 読んだフォルダ/ファイル。
- 除外した候補と理由。
- 推奨候補と未確認リスク。
