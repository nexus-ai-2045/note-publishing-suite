---
name: note-prepublish-qa
description: "Use inside note-publishing-suite to run local preview, pre-publish checks, fact checks, and optional Note/public diff checks before editor work or publication."
---

# note-prepublish-qa

## 役割

既存 script だけを使って、ローカル draft の公開前検査を行う。

## 入力

- local draft path。
- preview HTML の出力先。未指定なら draft と同名の HTML。
- Note URL。未作成または未反映なら Unknown。
- diff check で確認する phrase。未指定なら共通チェックのみ。

## Commands

```powershell
python scripts\note_virtual_preview.py <draft.md> -o <preview.html>
python scripts\note_preview.py <draft.md> --review-provenance -o <review.html>
python scripts\pre_publish_check.py <draft.md>
python scripts\note_fact_check.py local <draft.md>
python scripts\note_diff_check.py <note_url> <draft.md> <phrase...>
```

## 手順

1. 読書用は `note_virtual_preview.py`、由来の本人レビュー用は `note_preview.py --review-provenance` で作る。
   編集診断の枠・字数・警告が必要な時だけ `note_virtual_preview.py --diagnostics` を使う。
   読書用は `frontmatter` と `HTML` コメントを除くが、原稿と公開前検査・本人確認の停止条件は変えない。
2. pre-publish check を実行する。
3. local fact check を実行する。
4. Note URL がある場合だけ diff check を実行する。
5. 重大警告があれば draft-production へ戻す。

## 判定

- `pre_publish_check.py` が警告を返したら、公開 gate へ進まず修正または人間確認に戻す。
- `note_fact_check.py` のメモ残り、未確認、伝聞、数字、URL は公開前の確認対象。
- `note_fact_check.py` の本人発言/体験ベース候補は、原文、会話ログ、
  体験メモ、または現在会話のユーザー確認と突き合わせる。
- `note_diff_check.py` は Note URL と確認 phrase がある場合だけ使う。
- `pre_publish_check.py --fix` はファイルを書き換えるため、ユーザーが明示した場合だけ使う。

## 停止条件

- `pre_publish_check.py` が警告または error を返す。
- `note_fact_check.py` が未確認、推測、数字、URL、内部メモ、
  本人発言/体験ベース候補を検出し、出典確認が残る。
- preview HTML を作れない。
- Note URL と local draft の差分が未確認。

## Closeout Evidence

- preview HTML path。
- 実行した command。
- exit code または主要出力。
- 公開 gate へ進めるか、draft 修正へ戻すか。

## PDCA 台帳確認

- 公開前に PDCA 記録 (workspace の learning/pdca.md または data/ 配下の台帳) の有無を確認する。
- 存在する場合: 過去記事の Check/Act (反応・改善点) を 1 度読み、今回の draft に反映漏れがないか見る。
- 存在しない場合: 雛形作成を提案する (公開は止めない)。
- 同梱 scripts/content_pdca_check.py が使える workspace ではそれを実行する。

## 公開前調査の毎回確認

`../../references/note-workflow-review-contract.md` に従い、現稿に対する調査報告を作成する。根拠・調査結果・未確認点を毎回本人に提示し、承認発言を当該会話のreceiptに記録する。`note_workflow_gate.py --settings USER_SETTINGS_PATH --packet USER_REVIEW_PACKET --conversation-id CURRENT_CONVERSATION --stage research` が通らなければ公開手前へ進まない。本人の意見を外部事実と混ぜず、検査CLIの成功だけで本人確認済みとしない。
