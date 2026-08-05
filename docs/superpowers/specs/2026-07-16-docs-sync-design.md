---
title: Note Publishing Suite ドキュメント同期設計
type: design
status: approved-for-planning
created: 2026-07-16
approved: 2026-07-17
owner: nexus-ai-2045
publication_gate: human_review_required
external_action: none
---

# Note Publishing Suite ドキュメント同期設計

## 目的

`note-publishing-suite` の機能変更時に、関連ドキュメントの更新漏れと生成物の同期漏れをPR単位で検出する。GitHub ActionsがPR branchへ自動commitする方式は採用せず、CIの権限をread-onlyに保つ。

## 採用する方式

採用方式は「決定的な生成物は自動再生成して差分検知、意味判断が必要な文書は更新要否を機械検査」である。

- CIはrepositoryへ書き込まない。
- `README.rendered.html`は`README.md`から一時領域へ再生成し、commit済み生成物と一致するか確認する。
- 差分がある場合はCIを失敗させ、再生成後のpatchをworkflow artifactとして添付する。
- 手書き文書は変更種別と文書の対応表を使って、更新または「更新不要理由」の記録を要求する。
- fork PRやDependabotでもread-only検査として動く設計にする。
- PR branchへのbot commit、PAT、GitHub App、write権限は導入しない。

## 不採用方式

### PR branchへの自動commit

生成物を常に最新化できるが、write token、fork PR、bot commit後のCI再実行、commit attribution、無限loop防止が必要になる。`GITHUB_TOKEN`によるpushが通常のpush workflowを再発火しないため、最新SHAにCIが付かない状態も作り得る。現時点では複雑さと権限拡大が利益を上回る。

### 手動更新だけ

実装は不要だが、現状の更新漏れを防げないため採用しない。

## ドキュメント分類

### 自動生成物

| ファイル | 正本 | 同期方法 |
|---|---|---|
| `README.rendered.html` | `README.md` | `scripts/render_readme.py`で再生成し完全一致を検査 |

### 契約・入口文書

| ファイル | 更新トリガー |
|---|---|
| `README.md` | 利用者向け機能、導線、制約、検証コマンドの変更 |
| `SKILL.md` | routing、hard gate、完了条件、子skill契約の変更 |
| `package.yaml` | version、workflow、scripts、references、機械可読契約の変更 |
| `ROADMAP.md` | 現在地、優先順位、受入条件、将来計画の変更 |

### 運用・公開文書

| ファイル | 更新トリガー |
|---|---|
| `CHANGELOG.md` | version対象となる利用者可視・運用可視の変更 |
| `PUBLIC_READY.md` | 公開準備条件または検証面の変更 |
| `PUBLIC_RELEASE_CHECKLIST.md` | release前の実行手順・確認項目の変更 |
| `SECURITY.md` | security boundary、報告経路、対応範囲の変更 |
| `issue-drafts.md` | 実装済み項目、残課題、次の検証対象の変更 |

### 詳細リファレンスと子skill

`references/`と`skills/`は意味の正本である。機能変更はまず該当する詳細文書へ反映し、入口文書には利用者が必要な要約とpointerだけを同期する。

## 構成要素

### 1. ドキュメント同期manifest

機械可読なmanifestに次を定義する。

- 自動生成物と正本の組合せ
- 変更pathと更新候補文書の対応
- 常に存在すべき文書
- 更新不要理由を認める文書
- public packageへ含める文書

manifestは既存`package.yaml`へ追加し、別の設定正本を増やさない。

### 2. ローカル同期checker

新しいcheckerはread-onlyを既定にし、次を返す。

- `generated_drift`: 自動生成物の差分
- `missing_doc_review`: 変更に対応する文書更新も更新不要理由もない
- `missing_required_doc`: 必須文書がない
- `ok`: 同期済み

ローカル修復用の明示オプションだけが`README.rendered.html`を再生成する。通常検査はworking treeを書き換えない。ローカル実行では`--review-file <path>`で、CIではPR event payloadから抽出した本文fileで更新不要理由を検査できる。

### 3. PR用GitHub Actions job

既存`.github/workflows/test.yml`へread-onlyの`docs-sync` jobまたはstepを追加する。

- `permissions: contents: read`
- PR headをcheckout
- GitHub event payloadのPR本文を一時fileへ抽出
- checkerを実行
- 差分がある場合だけpatchと検査JSONをartifactとしてupload
- 差分があればjobを失敗させる
- commit、push、PR編集、comment投稿は行わない

### 4. PR本文の更新要否記録

PR templateに次を追加する。

```text
ドキュメント同期:
- [ ] 関連文書を更新した
- [ ] 更新不要。理由: <1行>
```

checkerはPR本文を直接書き換えない。GitHub Actionsが標準で持つevent payloadから本文をread-onlyで取得し、「関連文書を更新した」または具体的な更新不要理由を検査する。ローカルでは同じ書式のtext fileを`--review-file`で渡せる。

## データフロー

```text
PRの変更path
  -> package.yamlのdocs sync contract
  -> read-only checker
     -> 自動生成物を一時領域で再生成・比較
     -> 対応文書の差分を確認
  -> OK: CI成功
  -> NG: CI失敗 + patch/JSON artifact
  -> 人間またはCodexがbranchを修正
  -> 次のPR synchronizeで再検査
```

## エラー処理

- renderer失敗: `renderer_failed`として即失敗し、stdout/stderrをartifactへ含める。
- manifest不正: `contract_invalid`として即失敗する。
- 生成物差分: working treeを変更せずpatchを生成する。
- 文書更新要否が曖昧: 自動作文せず`missing_doc_review`として人間判断へ戻す。
- artifact upload失敗: checkerの失敗自体は保持し、ログから再現コマンドを提示する。
- fork PR: read-only tokenで完結し、write操作を要求しない。

## ドキュメント一式の初回更新

実装PRでは現在状態を一度棚卸しし、少なくとも次を同期する。

- `README.md` / `README.rendered.html`: 現行機能、Browser操作契約、docs-sync運用
- `SKILL.md`: docs-syncの保証ラチェットと停止線
- `package.yaml`: version、docs sync contract、checker、verification command
- `ROADMAP.md`: PRごとのdocs同期を「今」の受入条件へ移す
- `CHANGELOG.md`: 新versionの変更内容
- `PUBLIC_READY.md` / `PUBLIC_RELEASE_CHECKLIST.md`: docs-sync検査をrelease gateへ追加
- `issue-drafts.md`: docs-sync実装済み状態と残課題を反映
- `SECURITY.md`: 変更がなければ更新不要理由をレビュー記録に残す

## テスト

- README変更後に生成物未更新なら失敗する。
- READMEと生成物が一致すれば成功する。
- 対象path変更に対応する文書差分がなければ失敗する。
- 対象path変更に対応する文書差分がなくても、PR本文またはreview fileに具体的な更新不要理由があれば成功する。
- manifest欠損・不正schemaで失敗する。
- checker実行後にworking treeが変化しない。
- public package verifierと既存75件の回帰テストが成功する。
- workflowの`permissions`がread-onlyで、commit/push commandを含まない。

## 実装分離

PR #9はBrowser操作契約に限定し、2026-08-01に`main`へmerge済みである。本設計とdocs-sync実装は別branch・別PRで扱う。docs-sync実装branchは、PR #9を含む`0.2.11`以降の最新`main`を基点にする。

## 承認と停止線

2026-07-17に推奨順での進行が承認され、PR #9は2026-08-01にmergeされた。現段階では本設計のレビューと着地までとし、docs-sync実装は行わない。実装は本設計のレビュー完了後、最新`main`を基点に別PRで開始する。

## 完了条件

- ドキュメント一式が現行package状態と一致する。
- PRごとにread-only docs-sync検査が動く。
- 生成物差分がCI失敗とpatch artifactで分かる。
- CIがrepositoryへcommit、push、PR編集を行わない。
- ローカルとCIで同じcheckerを実行できる。
- PR #9の変更とdocs-sync基盤変更が別レビュー単位になっている。

## 参照

- GitHub `GITHUB_TOKEN`: https://docs.github.com/en/actions/concepts/security/github_token
- GitHub workflow permissions: https://docs.github.com/en/actions/reference/workflows-and-actions/workflow-syntax
- GitHub workflow artifacts: https://docs.github.com/en/actions/tutorials/store-and-share-data
