<!-- repo-preflight:review-record -->

# 公開準備レビュー記録

repo-preflight の検査結果と、それに対する人間の判断を記録します。
**この記録は「検査を通した」証拠であり、「安全である」ことの保証ではありません。**

公開準備の判定票そのものは `PUBLIC_READY.md` を正本とします。本ファイルは開発保証ゲートの契約側です。

## 対象

- repository: `nexus-ai-2045/note-publishing-suite`
- 公開範囲: 既に public（visibility 変更は行わない）
- ライセンス: リポジトリ直下の `LICENSE` を正本とする

## 開発保証ゲート

検査ロジックは本リポジトリへコピーしない。上流を直接呼ぶ。`engineering-brain` は埋め込まない。

| 契約 | 上流 | 設定 | 扱い |
|---|---|---|---|
| 文書・実装の宣言整合 | `nexus-ai-2045/repo-preflight`（pin SHA） | `.repo-preflight-consistency.json`（`shadow`） | `consistency_gate` + `readiness_scan`。shadow 所見は止めない。`tool_error` は fail-closed |
| tracked ∧ ignored の新規悪化 | `nexus-ai-2045/ai-ratchet-gate` v0.1.1（wheel + SHA-256） | `.ai-ratchet-gate/baseline.txt` | 既存分は grandfather。baseline に無い新規だけ deny |

### トリガ方針（Actions 課金）

- 開発保証 workflow（`repository-guarantees.yml`）は **`workflow_dispatch` のみ**。`pull_request` / `push` では起動しない
- `workflow_dispatch` で BASE と HEAD が同一（空 diff）のときは差分検査を緑にしない（fail-closed）
- 既存の `test.yml`（pytest / package verifier / docs-sync）は別契約。本節の開発保証とは混ぜない
- マージは人が行う。required status checks の追加や Settings 変更は行わない

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

**visibility の変更は行いません。** Settings / rulesets / Actions 権限 / 課金の変更も行いません。
マージ承認は人間レビューの結果であり、本ゲートの緑はマージ承認の代替ではありません。
