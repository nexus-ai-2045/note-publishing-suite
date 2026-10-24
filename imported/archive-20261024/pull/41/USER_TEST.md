---
title: Note Publishing Suite ユーザー受け入れテスト
type: user-acceptance-test
status: 実施待ち
version: 0.2.9
publication_gate: local_only
---

# ユーザー受け入れテスト

開発者向け自動テストとは別に、初めて使う人が主要導線と安全な停止位置を
確認するためのチェックリストです。すべてローカルで行い、Note 投稿、下書き保存、
SNS 共有、GitHub Release などの公開操作を行わないことを前提にします。

## 実施前の準備

- repository root で実施する。
- POSIX sh、Python、git を利用できる状態にする。
- 開始前の `git status --short` を記録する。
- 実記事、Cookie、認証情報、非公開 URL は入力しない。

## テストケース

| No | 確認項目 | 操作手順 | 期待結果 | 実際結果 | コメント / 証跡 | 確認日時 |
| --- | --- | --- | --- | --- | --- | --- |
| UAT-01 | 初見の入口 | `README.md` の「最初に開くリンク」と「最短確認」を読む | version、最短コマンド、人間承認が必要な公開境界を迷わず特定できる |  |  |  |
| UAT-02 | clean verifier | `sh scripts/verify_public_package.sh --json` を実行し、前後で `git status --short` を比較する | `ok: true`、errors 0、外部操作 0、公開操作 0。開始前後のGit差分が同じ |  |  |  |
| UAT-03 | 下書きレビュー停止線 | `python3 scripts/review_draft.py review-draft content/drafts/sample-note-prepublish-fixture.md --json` を実行する | fixtureは `verdict: blocked` となり、理由と確認質問がJSONで読める。公開操作は起きない |  |  |  |
| UAT-04 | 公開直前停止 | 下記の一時fileコマンドでローカルQA証跡を生成する | `overall: stopped_before_publish`、`human_review_required` を確認できる。repository内の追跡fileは変わらない |  |  |  |

UAT-04 のコマンド:

```bash
tmp_dir=$(mktemp -d)
python3 scripts/run_local_draft_qa_proof.py \
  --preview "$tmp_dir/preview.html" \
  --output "$tmp_dir/evidence.json" \
  --json
rm -f "$tmp_dir/preview.html" "$tmp_dir/evidence.json"
rmdir "$tmp_dir"
```

## 判定

- 4件すべて期待結果どおり: 受け入れ候補。
- 1件でも迷う、または期待結果と違う: 不合格としてケース番号と実際結果を記録する。
- UAT合格はNote公開の承認ではない。公開、保存、予約、外部共有は別の人間承認を必要とする。

## 実施サマリ

- 実施者:
- 実施環境:
- 実施日:
- PASS:
- FAIL:
- 保留:
- 総合判定:
