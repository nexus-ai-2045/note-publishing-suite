<!-- repo-preflight:review-record -->

# 公開準備レビュー記録

repo-preflight の検査結果と、それに対する人間の判断を記録します。
**この記録は「検査を通した」証拠であり、「安全である」ことの保証ではありません。**

公開準備の判定票そのものは `PUBLIC_READY.md` を正本とします。本ファイルは開発保証ゲートの契約側です。

## 対象

- repository: `nexus-ai-2045/note-publishing-suite`
- 公開範囲: 旧リポジトリを非公開で保全し、新しい履歴の公開リポジトリを作る。新規作成はnew-repo-bootstrap、既存リポジトリの公開範囲変更はpublish_gateの責務。実際の状態はGitHubから読み戻す。
- ライセンス: リポジトリ直下の `LICENSE` を正本とする

## 開発保証ゲート

編集できる検査ロジックは本リポジトリへコピーしない。`engineering-brain` は埋め込まない。repo-preflight は pin SHA を clone する。ai-ratchet-gate は公開 Release が無いので、保全済み wheel を `vendor/` に置き、hash が一致するときだけ入れる。

| 契約 | 上流 | 設定 | 扱い |
|---|---|---|---|
| 文書・実装の宣言整合 | `nexus-ai-2045/repo-preflight`（pin SHA） | `.repo-preflight-consistency.json`（`shadow`） | `consistency_gate` + `readiness_scan`。shadow 所見は止めない。`tool_error` は fail-closed |
| tracked ∧ ignored の新規悪化 | `nexus-ai-2045/ai-ratchet-gate` v0.1.1 の保全 wheel（`vendor/`、SHA-256） | `.ai-ratchet-gate/baseline.txt` | 既存分は grandfather。baseline に無い新規だけ deny。Release URL は使わない |

### 毎回の自動実行とローカル相当

- 開発保証workflow（`repository-guarantees.yml`）は `test.yml` の再利用jobとしてPR・main/masterへのpushごとに自動実行する。`package-smoke` はこのjobの成功を前提とし、抜けたまま進めない
- `workflow_dispatch` で BASE と HEAD が同一（空 diff）のときは差分検査を緑にしない（fail-closed）
- 検査ロジックは上流を呼び、コピーしない。通常のPR／branch pushはoriginから取得したイベント基点との差分を検査し、新規branch・タグ・Release公開・通常テストの手動実行は対象コミットの実在する親を取得し、mainが進んでいても現在のmainを基点にしない。対応外イベントは停止する。保証workflowを直接手動dispatchした場合は従来の全体release検査を行う。test workflowからの呼出しは明示inputで区別し、main上の通常テストの手動実行も差分なしを理由に停止しない。readinessのpass以外とratchetの新規悪化は停止する。整合性のshadow所見は所見として区別する
- マージは人が行う。required status checksやSettingsは変更せず、既存package-smokeの前提jobで接続する

### CIのprivate identity設定と実行境界

`repository-guarantees`は、private設定を読む`private-readiness`と、候補のwheel・ratchet・整合性検査を行う別jobへ分ける。private jobは候補内のPython、pip、package、Nodeコードを実行しない。上流repo-preflightを固定SHAで取得し、実HEADを照合してから隔離Pythonで起動する。対象もイベントのSHAでcheckoutし、base/headを検査間で固定する。

PRの名義検査は投稿者の実headを対象とし、GitHubが生成した一時merge commitを投稿者のコミットへ混ぜない。候補実行jobはイベントの合成merge SHAを検査し、検査済みの実headとbaseがその祖先であることを照合する。名義policyへGitHub名義を追加して通過させない。

PRでは`scan_base`を`merge-base(event_base, authored_head)`とし、分岐後の著者コミットを検査する。`event_base`はイベントが示す実baseのまま別出力に保持する。統合jobはこの実base・著者headをイベント値へ照合し、両方が合成mergeの祖先であることを検証する。forkpointを統合baseの代わりへ流用せず、不正base・共通履歴のないPRは停止する。

保証workflowを直接手動実行する全体検査は、分岐featureや過去tagと既定branchの比較も扱うため、比較baseとの共通履歴を確認する。PRやtest workflow経由の通常検査ではbaseの祖先条件を維持する。

管理者は既存の採用済み資料から、repository Secretsの`NPS_PRIVATE_IDENTITY_DENYLIST`（UTF-8 denylist本文）と`NPS_PRIVATE_IDENTITY_PATTERNS`（型付きprivate policy JSON）を登録する。値・private資料・個人識別子はリポジトリ、PR、ログ、artifactへ置かない。`test.yml`はこの2つだけを再利用workflowへ明示転送する。fork等でSecretを取得できない場合も空policyやfixtureへ置換せず停止する。

Secretsは固定scannerを呼ぶstepのみに渡し、対象checkout外の一時ディレクトリへ権限600で保存する。子processへraw入力は渡さず、上流の既存validatorで内容を検査する。終了時は一時ファイルを削除し、公開ログにはpass/failと固定された検査名の許可済みstatusだけを出す。scannerの全文stdout/stderrは公開しない。秘密入力を持つjobへ候補のinstall/testを追加しない。

workflow自体の改変を許可するとSecretを読み得るため、workflow・固定SHA・権限・Secretの変更は人間レビューを要する。job隔離はそのレビューやGitHubのfork承認・管理権限境界の代替ではない。

リポジトリ直下の`/.worktrees/`は管理下Git checkoutを置く作業用出力としてGit対象外にする。provenance全体検査も、この配下でGitへ実登録されたcheckoutだけを親packageの再帰対象から外す。未登録フォルダー、別階層の同名フォルダー、明示指定したファイルやディレクトリは検査を維持する。元の原稿、資料、検査コードは引き続き検査・追跡し、この除外へ移して隠さない。配下checkoutの成果は各所有ブランチでレビュー・配送する。

GitHubでPRをマージする運用では、採用済みの公開名義一覧にあるプラットフォームcommitterをCI専用設定へ完全一致で反映する。共有のprivate policyは書き換えず、既存のdeny条件と共同作者拒否を保った派生入力を使い、既知mergeの受入と未知名義の拒否を確認する。PR著者headの照合をこの設定で代用しない。

### 手元同等の確認コマンド

feature 枝で `origin/main` との差分がある状態で実行する（`BASE==HEAD` は意図的に失敗させる）。

```bash
# 1) ai-ratchet-gate（tracked∧ignored の新規悪化だけ deny）
python -m pip install --no-index --require-hashes -r requirements-tools.txt
python -m ai_ratchet_gate --repo .

# 2) repo-preflight（上流 clone。検査ロジックはコピーしない）
REPO_PREFLIGHT_SHA="$(sed -n 's/^  REPO_PREFLIGHT_SHA: //p' .github/workflows/repository-guarantees.yml)"
git clone --no-checkout https://github.com/nexus-ai-2045/repo-preflight.git /tmp/repo-preflight
git -C /tmp/repo-preflight checkout --detach "$REPO_PREFLIGHT_SHA"
test "$(git -C /tmp/repo-preflight rev-parse HEAD)" = "$REPO_PREFLIGHT_SHA"

git fetch origin main
BASE="$(git rev-parse origin/main)"
HEAD="$(git rev-parse HEAD)"
test "$BASE" != "$HEAD"  # 空diff fail-closed

python /tmp/repo-preflight/scripts/consistency_gate.py \
  --repo . --base-ref "$BASE" --require-config --require-mode shadow --json

python /tmp/repo-preflight/scripts/readiness_scan.py \
  --repo . --release --consistency-base-ref origin/main
```

Actions で同等確認する場合は、feature 枝を選んで `repository-guarantees` を `workflow_dispatch` する（default branch 直上だと空 diff で fail-closed）。

## 判断の記録

今回の本人依頼はNPSのPRIVATEからPUBLICへの変更。対象・全履歴の検査と採用済み公開ゲートを通す。Settings / rulesets / Actions権限 / 課金の変更は含めない。
マージ承認は人間レビューの結果であり、本ゲートの緑はマージ承認の代替ではありません。

直接の全体手動検査は、既定branchと分岐したfeatureや過去tagも比較対象にします。共通履歴と実tree差分を要求し、イベント基点を使う通常CIの祖先性検査とは分けます。

公開snapshotの中断復旧journalは、その実行ホストのworkspace絶対pathを固定して再実行時に照合します。これは共有settingsの入力ではなく、途中書込みを復旧するローカル状態です。旧v1 journalはdata直下の旧基点だけを許容し、別の祖先へ読み替えません。

## 新しい履歴の公開対象確認

公開対象は今回選定したソースと、新しい履歴だけ。旧commit・branch・tag・PR・退避refを移植しない。
公開前のrepo-preflightは新しい全履歴を検査し、旧履歴向けの例外や基準値で個人情報を免除しない。
author・committerの名前は既存の公開identity正本に従う`nexus_ai`、登録公開emailは維持し、pusher・新規作成のactorは`nexus-ai-2045`を照合する。owner/loginとGit author名を混同しない。共同著者を自動追加しない。今後のmergerも外部操作前に照合し、GitHub生成commitの扱いは既存名義guardの契約に従う。
個別の設定・検査実行receiptは利用者workspaceで保持し、packageには複製しない。

公開後の継続検査は`.github/workflows/preflight.yml`から上流の共通ゲートを固定SHAで呼ぶ。
`.repo-preflight/ratchet-baseline.json`は新しいソースの実測に合わせて締める。旧履歴の18件枠は引き継がない。
公開可否の検査は基準値による免除を使わず、全公開対象を検査する。
GitHub-hosted CIが課金制限で起動しない状態を成功とは記録しない。ローカル実行と区別する。
