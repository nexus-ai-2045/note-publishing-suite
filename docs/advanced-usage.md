# 詳しい制作・開発手順

[READMEへ戻る](../README.md)。コマンドはリポジトリ直下で実行します。

## PRごとのドキュメント同期

`package.yaml`の`docs_sync_contract`を正本として、変更pathに対応する文書更新と
`README.rendered.html`の生成差分を検査します。通常検査はrepositoryを変更せず、
不足時は`generated_drift`、`missing_doc_review`、`missing_required_doc`を返します。

```bash
python scripts/docs_sync_check.py --base-ref origin/main
```

PRでは`.github/workflows/test.yml`が`contents: read`だけで実行します。失敗時は
検査JSONと生成物patchをartifactに残しますが、commit、push、PR編集は行いません。
ローカルで生成物だけ直す場合は、明示的に`--fix-generated`を付けます。

<details>
<summary>開発者向けの検証と保証</summary>

## 開発・検証

```bash
python scripts/render_readme.py
python scripts/docs_sync_check.py --base-ref origin/main
python scripts/review_draft.py build-context-card content/drafts/sample-note-prepublish-fixture.md --json
python scripts/review_draft.py review-draft content/drafts/sample-note-prepublish-fixture.md --json
python scripts/note_editor_prepublish_verify.py data/note_editor_prepublish_observation.fixture.json --json
python scripts/run_local_draft_qa_proof.py --json
python scripts/japanese_closeout_language_check.py --json
python scripts/note_image_upload_boundary_check.py --json
python scripts/note_editor_pdca_failure_check.py --json
python scripts/note_editor_pdca_cycle_check.py <receipt.json> --require-final --json
python scripts/topic_status_check.py --json
python -m pytest scripts/test_skill_integration.py tests
```

包括検証は `sh scripts/verify_public_package.sh` です。`verify:local` は、
公開操作なしで構成、安全境界、README表示、公開前停止線を確認します。

日本語報告の `ready for review` は下書き解除済み、`open PR` は未マージPR、
`MERGED` はマージ済み、`mergeable` はマージ可能です。これらを英語のまま
報告した場合は文章ミスではなく、構造バグとして出力ゲートを修正します。
コマンド、ファイルパス、URL、SHA、識別子は原文のまま扱います。

## 保証ラチェット

失敗や手動境界は、原因・復旧方法・次回の禁止事項を残します。再発防止できる
ものは検査器、契約テスト、スキルへ反映し、UI依存は無理に自動化しません。

GitHubではこのREADMEをそのまま読めます。ローカル整形版は
`python scripts/render_readme.py` で `README.rendered.html` に生成できます。

</details>

末尾は固定枚数にせず、既存制作計画でリンク・理由・形式・順序・必須/任意を人間レビューします。[制作計画契約](../references/note-draft-authority-and-layout-contract.md)とCLIで照合し、成功も供給snapshotの整合性に限定します。

## 記事制作の入口と毎回の確認

音声書き起こしやnote本文から始める編集、既存素材の記事化、壁打ちを重ねる共同執筆の3経路を扱います。原文を先にローカル保存し、編集稿と区別します。本人発話、AI整理・追加案、外部事実、採否を既存の由来検査に結び付けます。

誤字も修正前後を確認し、公開前調査・公開設定・最終公開も毎回本人に確認します。[版ごとの承認契約](../references/note-workflow-review-contract.md)と `scripts/note_workflow_gate.py` で対象の版と承認記録を照合します。古い承認では進めません。checkerだけで人間発言の真正性や任意のBrowser経路を保証せず、runtimeが接続と証拠照合を担います。毎発言のフックは導入せず、最終投稿ボタンは人間が操作します。

## SEO・AIO・Note・PDCAの調査確認

workspace settingsで `research_quality_policy` を有効にした利用者は、既存research段階でSEO、AI検索で読み取れる根拠（AIO）、Noteの表示・設定、タグ、PDCA、関連作者・旬の6分野を確認します。実際に読んだ資料、観測日時、保存物のハッシュ、採否と未確認事項を結び、欠落・改変・鮮度切れは停止します。適用外や既存資料の再利用には理由が必要です。設定しない利用者の既存Markdown報告は継続利用できます。

PDCAは「記事内の改善→公開直後の確認→記事の成果→同テーマの比較→運用戦略」の5段階を既存feedbackへ結びます。将来の測定は計画として扱い、未取得を0や成功に変えません。順位・AI引用・収益・画像品質の実効果は、この構造検査だけで保証しません。画像は保持条件・変更条件を分け、加工前後、実解像度、文字や顔の変化を確認します。

フッターを省略する場合は、制作計画の明示的な `decision: omit` と理由を承認ハッシュへ含め、空のリンク計画と空の観測ノードを照合します。省略を指定しない旧計画では従来の必須リンク検査を維持します。

## 公開後の読戻しと承認一覧

内部ブラウザで取得した公開現物JSONを `--local-observation` で供給できる。指定時はネットワーク取得へ戻らない。公開／下書き台帳は `--published-ledger`／`--draft-ledger` でworkspace正本を指定し、既定dry-runの確認後、`--write-ledger` で更新する。原稿・公開snapshot・採否履歴はpackage外に保管する。

承認の確認は `note_workflow_gate.py --list-gates` で現在版・根拠・失効理由・依存する未承認項目を表示する。本文校正、目次／末尾カード、公開設定、最終公開の承認を区別し、本人が変更したタグを上書きしない。公開済みの観測と全ゲート通過は別の事実として残す。

詳しくは [人間レビュー契約](../references/note-workflow-review-contract.md) と [公開後手順](../skills/note-postpublish-ledger/SKILL.md) を参照する。


## 原稿保全・検索QA・編集検査の統合

検索QA、POSIX pointer、原稿保全・目次・編集session・論点対応・packet検査を既存の入口へ統合しました。明示した検索語だけを検索し、候補の取得を出典確認と区別します。原稿版・公式資料の保存先はworkspaceを明示し、既定のローカル書込みを避けます。editorの途中失敗では後続操作を止め、供給した観測JSONの成功を公開準備完了へ変換しません。詳細と検査の接続範囲は `SKILL.md` を参照してください。最終公開の本人操作境界は維持します。

## 読書プレビューの表示範囲

ローカルの読書プレビューは白背景のlight表示を基本に、本文の読書と構成確認に使います。簡易表示はNote実物のテーマやエディタUIを完全再現するものではありません。メタデータや診断表示を本文と分け、実画面の読戻しを別に行います。

## URLを1件ずつ入力するガード

[`scripts/note_editor_guarded_input.mjs`](../scripts/note_editor_guarded_input.mjs) は、対象記事・タブ・空段落のカーソルを入力直前に確認し、URL1件のpaste後に前後の本文・画像・リンク・目次を照合します。未反映なら入力を繰り返さず読み取りで再確認し、想定外の変更があれば後続入力を停止します。

[操作入口](../skills/note-editor-ops/SKILL.md)で現行のworkflow承認とBrowser surfaceを照合してから使います。Node.js 22以降と対応Tab APIが必要な任意経路で、Python/Orca CLIは自動置換しません。fixtureテストの成功は実Noteの互換性・保存・公開を証明せず、最終公開の本人操作境界を維持します。


採用済みの本人語彙は外部settingsの `history_learning_policy.vocabulary_rules` へ指定し、既存G2で提示前に検査できます。記事別policyと全体policyを結合し、履歴必須がfalseでも語彙検査を省略しません。引用・資料名・保存原文の例外は、既存sidecarの許可参照と現稿hashへ範囲を束縛します。引用記号だけでの免除や自動置換は行いません。[語彙検査と例外の契約](../references/note-workflow-review-contract.md#採用済みの本人語彙を提示前に検査する)を参照してください。

## 毎回の開発検査

PRとmain/master更新の既存test workflowから、固定版のrepo-preflightとai-ratchet-gateを自動実行します。`package-smoke`はその成功が前提です。課金制限で開始されない場合はローカル相当の結果と区別し、設定や保護ルールを迂回しません。詳しくは [PREFLIGHT.md](../PREFLIGHT.md)。

入力ガードは、対象・保護本文の変化と一時的な読取り失敗を診断コードで分離します。URL入力は1回に限定し、読取り照合は最大6回で停止します。深いカード構造は欠落のないJSONで照合します。

既存の公開記事の依頼済み修正だけは、利用者が外部settingsで明示採用した任意policyと現稿・設定の一致を検査した場合に限り公開更新へ進めます。既定、新規公開、予約変更、SNS共有の確認は維持します。公開後は保存版・台帳・本文点検・計測登録を個別に照合します。

骨組みHTML生成・表示照合・保存原文の由来検査は `scripts/note_skeleton_review.py`、`scripts/note_skeleton_review_check.py`、`scripts/note_skeleton_source_gate.py` を使います。`--workspace-root` で資料を所有する利用側workspaceを明示し、個人の原稿・採否はpackageへ移しません。追加依存は `requirements-review.txt` です。

