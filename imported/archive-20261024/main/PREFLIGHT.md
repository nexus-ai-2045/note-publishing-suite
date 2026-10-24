<!-- repo-preflight:review-record -->

# 公開準備レビュー記録

repo-preflight の検査結果と、それに対する人間の判断を記録します。
**この記録は「検査を通した」証拠であり、「安全である」ことの保証ではありません。**

公開準備の判定票そのものは `PUBLIC_READY.md` を正本とします。本ファイルは開発保証ゲートの契約側です。

## 対象

- repository: `nexus-ai-2045/note-publishing-suite`
- 公開範囲: 2026-10-20の読戻しではPRIVATE。本人の明示依頼に基づき、全履歴検査後に専用publish_gateでPUBLICへ切り替える。切替結果はGitHubの現在値を正本とする。
- ライセンス: リポジトリ直下の `LICENSE` を正本とする

## 開発保証ゲート

検査ロジックは本リポジトリへコピーしない。上流を直接呼ぶ。`engineering-brain` は埋め込まない。

| 契約 | 上流 | 設定 | 扱い |
|---|---|---|---|
| 文書・実装の宣言整合 | `nexus-ai-2045/repo-preflight`（pin SHA） | `.repo-preflight-consistency.json`（`shadow`） | `consistency_gate` + `readiness_scan`。shadow 所見は止めない。`tool_error` は fail-closed |
| tracked ∧ ignored の新規悪化 | `nexus-ai-2045/ai-ratchet-gate` v0.1.1（wheel + SHA-256） | `.ai-ratchet-gate/baseline.txt` | 既存分は grandfather。baseline に無い新規だけ deny |

### 毎回の自動実行とローカル相当

- 開発保証workflow（`repository-guarantees.yml`）は `test.yml` の再利用jobとしてPR・main/masterへのpushごとに自動実行する。`package-smoke` はこのjobの成功を前提とし、抜けたまま進めない
- `workflow_dispatch` で BASE と HEAD が同一（空 diff）のときは差分検査を緑にしない（fail-closed）
- 検査ロジックは上流を呼び、コピーしない。通常のPR／branch pushはoriginから取得したイベント基点との差分を検査し、新規branch・タグ・Release公開・通常テストの手動実行は対象コミットの実在する親を取得し、mainが進んでいても現在のmainを基点にしない。対応外イベントは停止する。保証workflowを直接手動dispatchした場合は従来の全体release検査を行う。test workflowからの呼出しは明示inputで区別し、main上の通常テストの手動実行も差分なしを理由に停止しない。readinessのpass以外とratchetの新規悪化は停止する。整合性のshadow所見は所見として区別する
- マージは人が行う。required status checksやSettingsは変更せず、既存package-smokeの前提jobで接続する

### 手元同等の確認手順

feature 枝で `origin/main` との差分がある状態で実行する（`BASE==HEAD` は意図的に失敗させる）。

```bash
# 1) ai-ratchet-gate（tracked∧ignored の新規悪化だけ deny）
python -m pip install --require-hashes -r requirements-tools.txt
python -m ai_ratchet_gate --repo .

# 2) repo-preflight（上流 clone。検査ロジックはコピーしない）
REPO_PREFLIGHT_SHA=f825268978228a3cfb2f5ecba16a74d424134b1a
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

## 2026-10-20の公開対象確認

公開対象はGitHubから取得したmainと全tagの到達可能履歴。ローカル退避用refは含めない。
過去blob内の検出パターンと説明用・合成USER例による18件は、実ユーザーpathではないことを個別に確認する。
公開操作の全履歴検査は、repo-preflight既存のreviewed-secret-exceptionsでrepo・path・内容hash・一致hash・件数・期限を固定する。
名義は公開用nexus-ai-2045 / nexus-ai-2045 / GitHubと既知AIの公開用メールに限定し、個人の拒否ルールは維持する。共有の非公開設定は変更しない。
個別の設定・検査実行receiptは利用者workspaceで保持し、packageには複製しない。

公開後の継続検査は`.github/workflows/preflight.yml`から上流の共通ゲートを固定SHAで呼ぶ。
`.repo-preflight/ratchet-baseline.json`は全履歴の既存例示18件をCIで増やさないための基準値。
公開可否の検査にはこの基準値を使わず、個別にレビューした例示だけを厳密に束縛する。
GitHub-hosted CIが課金制限で起動しない状態を成功とは記録しない。ローカル実行と区別する。
