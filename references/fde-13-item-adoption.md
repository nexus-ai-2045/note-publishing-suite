# FDE 13 item adoption for Note Publishing Suite

このファイルは、FDE の 13 項目カードを Note Publishing Suite で明示採用する
ローカル正本。Note 投稿支援の 13 工程を置き換えず、開発・運用・完了確認の
メタカードとして使う。

## 採用方針

- FDE 13 項目は、作業単位を始める前と closeout 前に読む開発カード。
- `references/initial-note-workflow-ruleset.md` は、素材入口から handoff までの
  Note 投稿支援 13 工程。
- つまり FDE は「どう作業を切るか」、Note workflow は「何を順に進めるか」を担う。
- 公開、予約投稿、SNS 共有、外部告知、repository visibility 変更は、どちらの
  正本でも human gate まで停止する。

## FDE 13 項目の採用表

| # | FDE 項目 | Note Publishing Suite での採用内容 |
|---:|---|---|
| 1 | 目的 | ローカル素材から Note 下書き、QA、エディタ引き継ぎ、公開直前停止、台帳更新案までを安全に進める |
| 2 | 主ユーザー行動 | ユーザーが素材、記事意図、公開方式、レビュー可否を選び、公開判断を行う |
| 3 | 主経路 | `references/initial-note-workflow-ruleset.md` の 13 工程 |
| 4 | 保存単位 | 下書き、preview、QA evidence、台帳、review artifact。Cookie、token、非公開 URL、個人パスは保存しない |
| 5 | 最小E2E | sample draft を preview、pre-publish check、fact check、diff skipped、publication stop まで通す |
| 6 | やらないこと | Note 公開、予約確定、SNS 共有、外部告知、repository visibility 変更、未承認素材読取 |
| 7 | fallback | 素材不足なら intake へ、根拠不足なら source pack へ、エディタ不安定なら手動境界へ戻す |
| 8 | 公開/個人情報境界 | public package には fixture、空台帳、safe metadata、検査器だけを含める |
| 9 | 完了条件 | tests、public package verifier、diff check、公開/外部 action 0、残 gate 明示が揃う |
| 10 | ズレ検知条件 | スクリプト数だけを運用項目扱いする、実記事と fixture が混ざる、公開 gate が曖昧になる |
| 11 | owner | 親実行環境が判断、採否、Type1 境界、公開 gate、最終報告を持つ |
| 12 | 検証証跡 | pytest、`verify_public_package.ps1`、QA evidence、ledger dry-run、git diff check |
| 13 | 次の一手 | 現在の turn で閉じる 1 件を選び、未確認があれば hold として返す |

## Note 13 工程との対応

| FDE 項目 | 主に対応する Note 13 工程 |
|---|---|
| 目的 / 主ユーザー行動 | 1. 素材入口指定、3. 記事スコープと公開方式の仮決め |
| 主経路 | 1-13 全体 |
| 保存単位 | 8. Markdown レビュー artifact / local preview、12. 公開後確認 / 台帳更新案、13. 終了・handoff |
| 最小E2E | 6. 下書きプローブ、7. 下書きリスクレビュー、8. local preview、11. 公開直前 human gate |
| やらないこと / 公開境界 | 10. Note editor 引き継ぎ、11. 公開直前 human gate |
| fallback / ズレ検知 | 4. 根拠パック構成、5. 骨子確認 gate、10. Note editor 引き継ぎ |
| owner / 検証証跡 / 次の一手 | 13. 終了・handoff |

## Closeout で見ること

完了報告の前に、次を分けて確認する。

- 実装: FDE 13 項目と Note 13 工程の参照が更新されているか。
- ローカル検証: pytest、public package verifier、diff check が通っているか。
- 作業ツリー: 対象変更だけが staged で、無関係差分を混ぜていないか。
- 運用保証: 公開/外部 action が 0 で、残る human gate が明示されているか。
