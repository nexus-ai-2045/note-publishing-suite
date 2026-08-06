# NPS 使い方動画（demo assets）

このフォルダは **Note Publishing Suite（NPS）の使い方動画** を置く場所です。

## 置くファイル

| ファイル | 必須 | 内容 |
|---|---|---|
| `usage-walkthrough.mp4` | 推奨 | 1〜3 分の画面録画。clone → verify → install → 最初の依頼 |
| `usage-walkthrough-thumb.svg` または `.png` | 推奨 | README 用サムネ（1280×720 前後） |
| `storyboard.md` | 任意 | 撮影台本 |

## README への載せ方

`README.md` の「使い方動画」節に、次を有効化する（コメントアウトを外す）:

```markdown
[![NPS 使い方動画を再生](assets/demo/usage-walkthrough-thumb.svg)](assets/demo/usage-walkthrough.mp4)
```

### 注意

- GitHub README は **相対パスの `<video>` 埋め込みが安定しない** 環境があります。
  サムネ画像 → mp4 へのリンク方式がいちばん壊れにくいです。
- mp4 は **短く・軽く**（目安 30MB 未満）。長い解説は YouTube 等へ。
- 録画に Cookie、token、個人パス、非公開 URL を映さない。
- 公開・予約・SNS 操作はデモでも押さない（停止線を見せる）。

## 撮影の最短台本

1. 空フォルダで `git clone` → `verify_public_package`
2. Windows: `adapters/codex/install.ps1`
3. Codex に「note-publishing-suite で、素材はここだけ。公開しない」
4. idea → draft → QA のどこか 1 本を短く
5. 「ここで公開ボタンは押さない」を明示して終了

詳細台本: `storyboard.md`
