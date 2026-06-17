---
name: note-official-guidance-intake
description: "Use inside note-publishing-suite when collecting Note official guidance before changing article, tag, table-of-contents, editor, image, embed, publication-time, or browser-environment advice. Trigger on note公式, noteヘルプ, 公式ノウハウ, タグ, 目次, 公開時間, 推奨環境, or when Codex is about to claim Note behavior is official."
---

# note-official-guidance-intake

## 役割

Note 公式の一次情報を取り込み、実用できる editor / article / tag /
publication guidance だけを suite に反映する。公式未確認の推測を skill 本文に
混ぜないための入口。

## 入力

- 調べたい機能または運用論点。
- 反映先候補。通常は `../../references/note-editor-capability-inventory.md`。
- 既存 draft / editor 操作で困っている症状。なければ Unknown。

## 手順

1. 親 suite の公開 gate を再確認する。外部投稿、公開、共有はしない。
2. Note 公式ヘルプ、Note 公式マガジン、Note 運営の告知など一次情報だけを読む。
3. 公式ソースごとに、URL、確認日、対象機能、実用判断、未確認を分ける。
4. 公式に書かれていない推測は `local observation` または `needs measurement`
   として扱い、公式扱いしない。
5. 実用できるものだけ、`references/note-editor-capability-inventory.md` の
   `公式ソース`、`操作軸`、`足りていない棚卸し` のどれかへ反映する。
6. editor 操作に直結する場合は、`note-editor-constraint-debug` または
   `note-editor-ops` へ渡して実測手順に落とす。
7. 反映後は `scripts/test_skill_integration.py` を実行する。

## 取り込む対象

- 推奨ブラウザ、OS、既知の環境差。
- 見出し、目次、リンクカード、埋め込み、画像、alt、caption。
- タグ、マガジン、公開範囲、無料/有料、予約投稿、timezone。
- 自動保存、プレビュー、複数タブ競合、下書き復旧。
- 公式が示す制限、反映待ち、表示遅延、未対応機能。

## 公式扱いの最低条件

- `references/note-editor-capability-inventory.md` の `公式ソース` 表に、
  source URL と `confirmed_on` がある。
- 公式ソースの内容と local policy / local observation が同じ文に混ざっていない。
- 「おすすめ」「最適」「公式推奨」と書く場合、何を推奨しているのかを限定する。
  例: ブラウザ推奨、公開日の参考、タグ設定方法。
- 公式ソースが固定時刻を示していない場合、公開時刻の助言を公式扱いしない。
  創作カレンダーはテーマや公開日の参考であり、汎用的な最適時刻保証ではない。

## 書き方

- 「公式ソースでは X とされている」と書く時は、必ず source URL を残す。
- 「実測では X」と「公式では X」を分ける。
- 未確認を公式扱いしない。
- 作文禁止。公式にない便利そうな運用論を足す場合は、必ず `local policy`
  または `local observation` と書く。
- DOM selector、`figure[data-src]`、固定しない座標運用などの自動化判定は
  local checker として書き、公式ヘルプの主張にしない。

## 停止条件

- 一次情報が見つからない。
- 公式ソースの内容が現行 editor と食い違う。
- ログイン、Cookie、非公開URL、公開操作が必要になる。
- 反映先が公開済み資料で、現在会話で更新承認がない。

## Closeout Evidence

- 読んだ公式ソース URL。
- 反映した reference / skill / checker。
- 公式扱いしたこと、local observation に留めたこと。
- 未確認のまま残した論点。
- 実行した test。
