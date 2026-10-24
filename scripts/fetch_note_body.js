/**
 * Playwrightでnote.comの公開記事本文を取得するスクリプト
 *
 * 使い方: node fetch_note_body.js <URL>
 * 出力: 記事本文のプレーンテキスト（stdout）
 *
 * note.comはSPAのためfetch/curlでは本文取得不可。
 * Playwright (chromium) でレンダリング後にセレクタで抽出する。
 */
const path = require("path");
const { createRequire } = require("module");

function loadPlaywright() {
  try {
    return require("playwright");
  } catch (localError) {
    const platformRoot = path.resolve(__dirname, "..", "platform");
    try {
      return createRequire(path.join(platformRoot, "package.json"))("playwright");
    } catch (platformError) {
      const error = new Error(
        "Playwright が見つかりません。package root か platform/ で npm install を実行してください。"
      );
      error.cause = { localError, platformError };
      throw error;
    }
  }
}

const { chromium } = loadPlaywright();

const SELECTORS = [
  "div.note-common-styles__textnote-body",
  "article div[class*='note-common-styles']",
  "article",
  "main",
];
const TIMEOUT_MS = 30000;

async function extractArticleBody(page) {
  for (const selector of SELECTORS) {
    try {
      await page.waitForSelector(selector, { timeout: 5000 });
      const text = await page.$eval(selector, (el) => (el.innerText || "").trim());
      if (text) {
        return text;
      }
    } catch (_) {
      // 次の候補へ進む
    }
  }

  const jsonLd = await page.$$eval('script[type="application/ld+json"]', (scripts) => {
    for (const script of scripts) {
      const raw = (script.textContent || "").trim();
      if (!raw) {
        continue;
      }
      try {
        const parsed = JSON.parse(raw);
        const items = Array.isArray(parsed) ? parsed : [parsed];
        for (const item of items) {
          if (item && typeof item.articleBody === "string" && item.articleBody.trim()) {
            return item.articleBody.trim();
          }
        }
      } catch (_) {
        // ignore invalid JSON-LD blocks
      }
    }
    return "";
  });

  if (jsonLd) {
    return jsonLd;
  }

  throw new Error("公開本文を抽出できませんでした");
}

async function main() {
  const url = process.argv[2];
  if (!url) {
    console.error("Usage: node fetch_note_body.js <URL>");
    process.exit(1);
  }

  const browser = await chromium.launch({ headless: true });
  try {
    const page = await browser.newPage();
    await page.goto(url, { waitUntil: "domcontentloaded", timeout: TIMEOUT_MS });
    const text = await extractArticleBody(page);
    // stdoutにテキストを出力（改行で正規化）
    process.stdout.write(text.trim());
  } finally {
    await browser.close();
  }
}

main().catch((err) => {
  console.error(`[error] ${err.message}`);
  process.exit(1);
});
