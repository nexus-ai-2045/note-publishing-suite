import {
  Editor,
  Extension,
  Node,
  generateJSON,
  type JSONContent,
} from "@tiptap/core";
import StarterKit from "@tiptap/starter-kit";
import Link from "@tiptap/extension-link";
import {
  initApi,
  getTheme,
  createTheme,
  action,
  generate,
  articlePayload,
  connectionInfo,
  connectionPreflight,
  configureConnection,
  listThemes,
  type Theme,
  type Article,
  type Proposal,
} from "./api";
import {
  parseBlocks,
  bindBaseline,
  serializeDocument,
  newId,
  selectionMetadata,
  blocksForSave,
  type MarkdownDocument,
} from "./metadata";
import { layout } from "./layout";
import "./style.css";
let theme: Theme | null = null,
  article: Article | null = null,
  editor: Editor | null = null,
  doc: MarkdownDocument | null = null;
let themes: { id: string; title: string; revision: number }[] = [],
  dirty = false,
  conflicted = false,
  composing = false,
  busy = false,
  generating = false,
  editVersion = 0,
  timer: ReturnType<typeof setTimeout> | undefined;
const esc = (s: unknown) =>
  String(s ?? "").replace(
    /[&<>"']/g,
    (c) =>
      ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" })[
        c
      ]!,
  );
const $ = (id: string) => document.getElementById(id)!;
const input = (id: string) => ($(id) as HTMLInputElement).value.trim();
const safe = (fn: () => Promise<unknown>) => () => void fn().catch(report);
function report(e: unknown) {
  editor?.setEditable(true);
  $("toast").textContent = e instanceof Error ? e.message : String(e);
  $("recovery").hidden = false;
}
function notice(s: string) {
  $("toast").textContent = s;
}
const Identity = Extension.create({
  name: "identity",
  addGlobalAttributes() {
    return [
      {
        types: [
          "paragraph",
          "heading",
          "blockquote",
          "bulletList",
          "orderedList",
        ],
        attributes: { blockId: { default: null }, lineage: { default: null } },
      },
    ];
  },
});
const Opaque = Node.create({
  name: "opaque",
  group: "block",
  atom: true,
  selectable: true,
  addAttributes() {
    return { blockId: { default: null }, raw: { default: "" } };
  },
  parseHTML() {
    return [{ tag: "pre[data-preserved]" }];
  },
  renderHTML({ node }) {
    return [
      "pre",
      {
        "data-preserved": "true",
        contenteditable: "false",
        title: "元のMarkdownを保持する読取専用ブロック",
      },
      node.attrs.raw,
    ];
  },
});
const extensions = [
  StarterKit.configure({
    codeBlock: false,
    code: false,
    horizontalRule: false,
    strike: false,
    link: false,
    underline: false,
    trailingNode: false,
  }),
  Link.configure({ openOnClick: false, autolink: false }),
  Identity,
  Opaque,
];
$("app").innerHTML = layout;
function mount() {
  clearTimeout(timer);
  editor?.destroy();
  editor = null;
  doc = null;
  dirty = false;
  conflicted = false;
  $("editor").innerHTML = "";
  $("saveState").textContent = "";
  if (!article) {
    $("editor").innerHTML =
      '<div class="empty-editor">対話から始められます。本文を書くときは左側から記事を追加してください。</div>';
    return;
  }
  doc = parseBlocks(article.draft, article.blocks);
  const nodes: JSONContent[] = doc.pieces.map((p) => {
    if (p.kind === "opaque")
      return { type: "opaque", attrs: { blockId: p.id, raw: p.raw } };
    const n = generateJSON(p.html, extensions).content![0];
    return { ...n, attrs: { ...n.attrs, blockId: p.id } };
  });
  editor = new Editor({
    element: $("editor"),
    extensions,
    content: {
      type: "doc",
      content: nodes.length
        ? nodes
        : [{ type: "paragraph", attrs: { blockId: newId() } }],
    },
    editorProps: {
      handleDOMEvents: {
        compositionstart() {
          composing = true;
          clearTimeout(timer);
          return false;
        },
        compositionend() {
          composing = false;
          schedule();
          return false;
        },
      },
    },
    onUpdate({ transaction }) {
      if (!transaction.docChanged) return;
      dirty = true;
      editVersion++;
      assignIds(transaction);
      $("saveState").textContent = "未保存";
      renderOutline();
      schedule();
    },
  });
  assignIds();
  bindBaseline(doc, editor.getJSON().content || []);
}
function assignIds(transaction?: { before: any; mapping: any }) {
  if (!editor) return;
  const seen = new Set<string>();
  const tr = editor.state.tr;
  editor.state.doc.forEach((n, pos) => {
    const id = n.attrs.blockId;
    const duplicate = !id || seen.has(id);
    const lineage: string[] = Array.isArray(n.attrs.lineage)
      ? [...n.attrs.lineage]
      : n.attrs.lineage
        ? [n.attrs.lineage]
        : [];
    if (transaction)
      transaction.before.forEach((old: any, oldPos: number) => {
        const mapped = transaction.mapping.map(oldPos, 1);
        if (
          mapped >= pos &&
          mapped < pos + n.nodeSize &&
          old.attrs.blockId &&
          old.attrs.blockId !== id &&
          !lineage.includes(old.attrs.blockId)
        )
          lineage.push(old.attrs.blockId);
      });
    if (duplicate && id && !lineage.includes(id)) lineage.push(id);
    if (
      duplicate ||
      JSON.stringify(lineage) !== JSON.stringify(n.attrs.lineage || [])
    )
      tr.setNodeMarkup(pos, undefined, {
        ...n.attrs,
        blockId: duplicate ? newId() : id,
        lineage: lineage.length ? lineage : null,
      });
    seen.add(id);
  });
  if (tr.docChanged) editor.view.dispatch(tr);
}
function currentMarkdown() {
  return editor && doc
    ? serializeDocument(doc, editor.getJSON().content || [])
    : article?.draft || "";
}
function schedule() {
  clearTimeout(timer);
  if (!composing && !generating)
    timer = setTimeout(() => void save().catch(report), 1600);
}
function editorBlocks(): Article["blocks"] {
  if (!editor || !article) return [];
  return blocksForSave(editor.getJSON().content || [], article.blocks);
}
async function save(): Promise<boolean> {
  if (!dirty) return true;
  if (conflicted || composing || busy) return false;
  if (!theme || !article || !editor || !doc) return true;
  busy = true;
  clearTimeout(timer);
  const version = editVersion,
    draft = currentMarkdown(),
    selected = article.id;
  try {
    const blocks = editorBlocks();
    theme = await action(
      theme.id,
      "save_draft",
      { article_id: selected, draft, blocks },
      theme.revision,
    );
    article = theme.articles.find((a) => a.id === selected) || article;
    if (version === editVersion) {
      dirty = false;
      $("saveState").textContent = "保存済み";
    } else schedule();
    render();
    return !dirty;
  } catch (e) {
    if (
      ["stale", "external_edit"].includes((e as { code?: string }).code || "")
    )
      conflicted = true;
    $("saveState").textContent = "保存失敗・本文保持";
    report(e);
    return false;
  } finally {
    busy = false;
  }
}
async function beforeSwitch() {
  if (generating) {
    notice("AIの応答後に切り替えてください。");
    return false;
  }
  if (!(await save())) {
    notice(
      "未保存の本文を保持しました。保存または退避・復旧してから切り替えてください。",
    );
    return false;
  }
  editor?.setEditable(false);
  return true;
}
async function mutate(
  name: string,
  payload: Record<string, unknown>,
  replace = false,
) {
  if (!theme) throw new Error("先にテーマを作成してください");
  if (busy) throw new Error("保存が終わるまでお待ちください");
  if (replace && !(await beforeSwitch())) return;
  const selected = article?.id;
  busy = true;
  try {
    theme = await action(
      theme.id,
      name,
      articlePayload(name, payload, article?.id),
      theme.revision,
    );
    article =
      theme.articles.find((a) => a.id === selected) ||
      theme.articles[0] ||
      null;
    if (replace) mount();
    render();
  } finally {
    busy = false;
    editor?.setEditable(true);
  }
}
function renderLists() {
  if (theme) {
    const pos = themes.findIndex((t) => t.id === theme!.id);
    const row = { id: theme.id, title: theme.title, revision: theme.revision };
    if (pos < 0) themes.push(row);
    else themes[pos] = row;
  }
  $("themes").innerHTML =
    themes
      .map(
        (t) =>
          `<button class="theme ${theme?.id === t.id ? "selected" : ""}" data-theme="${esc(t.id)}">${esc(t.title)}</button>`,
      )
      .join("") || '<p class="muted">テーマを作って対話を始めます。</p>';
  $("themes")
    .querySelectorAll<HTMLButtonElement>("[data-theme]")
    .forEach(
      (b) =>
        (b.onclick = safe(async () => {
          if (!(await beforeSwitch())) return;
          theme = await getTheme(b.dataset.theme!);
          article = theme.articles[0] || null;
          mount();
          render();
        })),
    );
  $("articles").innerHTML = (theme?.articles || [])
    .map(
      (a) =>
        `<button class="theme ${a.id === article?.id ? "selected" : ""}" data-article="${esc(a.id)}">${esc(a.title)}</button>`,
    )
    .join("");
  $("articles")
    .querySelectorAll<HTMLButtonElement>("[data-article]")
    .forEach(
      (b) =>
        (b.onclick = safe(async () => {
          if (!(await beforeSwitch())) return;
          article =
            theme!.articles.find((a) => a.id === b.dataset.article) || null;
          mount();
          render();
        })),
    );
}
function render() {
  renderLists();
  $("status").textContent = theme
    ? `${theme.title} / v${theme.revision}${generating ? " / AI応答待ち" : ""}`
    : "テーマを作成してください";
  $("chat").innerHTML =
    (theme?.messages || [])
      .map(
        (m) =>
          `<div data-message-id="${esc(m.id)}" class="message ${m.role === "user" ? "user" : ""}"><b>${m.role === "user" ? "あなた" : "AI"}</b><p>${esc(m.text)}</p></div>`,
      )
      .join("") ||
    '<p class="muted">テーマについて話して、記事の方向性を決めましょう。</p>';
  $("sources").innerHTML =
    (theme?.sources || [])
      .map(
        (s) =>
          `<details><summary>${esc(s.path)}</summary><pre>${esc(s.text)}</pre></details>`,
      )
      .join("") || "<p>素材はまだありません。</p>";
  $("skeletonContent").innerHTML = skeletonHtml(article?.skeleton);
  $("proposals").innerHTML =
    (theme?.proposals || [])
      .filter((p) => !p.article_id || p.article_id === article?.id)
      .map(proposalHtml)
      .join("") || '<p class="muted">AIの提案を全文で比較できます。</p>';
  $("proposals")
    .querySelectorAll<HTMLButtonElement>("[data-revoke]")
    .forEach(
      (b) =>
        (b.onclick = safe(() =>
          mutate("revoke_learning", { proposal_id: b.dataset.revoke }),
        )),
    );
  $("correspondence").innerHTML =
    (article?.blocks || [])
      .map(
        (b) =>
          `<div class="comment"><p>${esc(b.text.slice(0, 100))}</p><small>${b.correspondence_status === "needs_review" ? "編集後の対応を要確認" : "参照候補"}</small><div>${(b.source_refs || []).map((ref) => `<button data-source-ref="${esc(ref)}">${esc(ref.startsWith("message:") ? "対話 " + ref.slice(8) : ref.startsWith("paragraph:") ? "骨組み " + ref.slice(10) : "素材 " + ref.slice(7))}</button>`).join("") || "個別の参照先は未照合"}</div></div>`,
      )
      .join("") || "<p>本文の生成後に参照候補を表示します。</p>";
  $("correspondence")
    .querySelectorAll<HTMLButtonElement>("[data-source-ref]")
    .forEach(
      (button) =>
        (button.onclick = () => {
          const ref = button.dataset.sourceRef!;
          if (ref.startsWith("message:")) {
            const target = document.querySelector<HTMLElement>(
              `[data-message-id="${CSS.escape(ref.slice(8))}"]`,
            );
            if (target) {
              document.querySelector<HTMLDetailsElement>(
                ".right details",
              )!.open = true;
              target.scrollIntoView({ block: "nearest" });
            }
          } else if (ref.startsWith("paragraph:")) {
            tab("skeleton");
            notice(
              "骨組みの段落 " +
                ref.slice(10) +
                " を参照しています。原文との意味の照合は別に行います。",
            );
          } else {
            tab("materials");
            notice("素材一覧から参照した版を確認してください。");
          }
        }),
    );
  const ids = new Set(
    (editor?.getJSON().content || []).map((n) => n.attrs?.blockId),
  );
  $("comments").innerHTML = (theme?.comments || [])
    .filter((c) => c.article_id === article?.id)
    .map(
      (c) =>
        `<div class="comment"><small>${c.block_id && ids.has(c.block_id) ? "本文に紐付き" : "紐付け先を要確認"}</small><q>${esc(c.quote)}</q><p>${esc(c.text)}</p></div>`,
    )
    .join("");
  renderOutline();
}
function skeletonHtml(s: any) {
  return s?.sections?.length
    ? `<ol>${s.sections.map((x: any) => `<li><strong>${esc(x.heading)}</strong><p>${esc((x.paragraph_ids || []).join(" / "))}</p></li>`).join("")}</ol>`
    : '<p class="muted">対話と素材から骨組みを提案できます。</p>';
}
function proposalText(p: Proposal, value: string) {
  if (p.target === "skeleton") {
    try {
      return skeletonHtml(JSON.parse(value));
    } catch {}
  }
  return `<pre>${esc(value)}</pre>`;
}
function proposalHtml(p: Proposal) {
  return `<article class="proposal"><label><input type="checkbox" data-proposal="${esc(p.id)}" ${p.status !== "pending" ? "disabled" : ""}> ${esc(({ pending: "未採用", adopted: "採用済み", rejected: "見送り", stale: "再確認" } as Record<string, string>)[p.status] || p.status)} / ${esc(({ local: "この箇所", article: "この記事", future: "今後にも使う" } as Record<string, string>)[p.scope || "local"])}</label><h3>AIの意図</h3><p>${esc(p.intent)}</p><h3>元の内容</h3>${proposalText(p, p.before)}<h3>変更案</h3>${proposalText(p, p.after)}${p.scope === "future" && p.status === "adopted" ? `<button data-revoke="${esc(p.id)}">今後への適用を取り消す</button>` : ""}</article>`;
}
function renderOutline() {
  const headings: { text: string; pos: number }[] = [];
  editor?.state.doc.forEach((n, pos) => {
    if (n.type.name === "heading") headings.push({ text: n.textContent, pos });
  });
  $("headings").innerHTML = headings
    .map((h) => `<button data-pos="${h.pos}">${esc(h.text)}</button>`)
    .join("");
  $("headings")
    .querySelectorAll<HTMLButtonElement>("[data-pos]")
    .forEach(
      (b) =>
        (b.onclick = () => {
          tab("body");
          editor
            ?.chain()
            .focus()
            .setTextSelection(Number(b.dataset.pos) + 1)
            .scrollIntoView()
            .run();
        }),
    );
}
async function runGenerate(mode: string, instruction = input("instruction")) {
  if (!theme) throw new Error("先にテーマを作成してください");
  if (mode !== "chat" && !article) throw new Error("記事を追加してください");
  if (!instruction) throw new Error("AIへの指示を入力してください");
  if (generating) throw new Error("AIの応答を待っています");
  if (!(await save())) return;
  if (mode !== "chat")
    await mutate("add_message", { role: "user", text: instruction });
  const target = theme.id,
    selected = article?.id;
  generating = true;
  clearTimeout(timer);
  render();
  try {
    const result = await generate(target, {
      article_id: selected,
      mode,
      instruction,
      expected_revision: theme.revision,
    });
    if (theme.id === target) {
      theme = result;
      article = theme.articles.find((a) => a.id === selected) || article;
      render();
    }
  } catch (e) {
    const failure = e as Error & { candidate?: unknown };
    if (failure.candidate)
      $("candidate").innerHTML =
        `<h3>自動反映しなかった候補</h3><pre>${esc(JSON.stringify(failure.candidate, null, 2))}</pre>`;
    report(e);
  } finally {
    generating = false;
    render();
    if (dirty) schedule();
  }
}
function tab(name: string) {
  for (const n of ["body", "materials", "skeleton"]) $(n).hidden = n !== name;
  document
    .querySelectorAll<HTMLButtonElement>("[data-tab]")
    .forEach((b) => b.classList.toggle("active", b.dataset.tab === name));
}
function download(name: string, text: string, type = "text/plain") {
  const url = URL.createObjectURL(new Blob([text], { type }));
  const a = document.createElement("a");
  a.href = url;
  a.download = name;
  a.click();
  setTimeout(() => URL.revokeObjectURL(url), 1000);
}
$("themeForm").onsubmit = (e) => {
  e.preventDefault();
  void (async () => {
    if (!(await beforeSwitch())) return;
    theme = await createTheme(input("themeTitle"));
    article = null;
    mount();
    render();
    ($("themeTitle") as HTMLInputElement).value = "";
  })().catch(report);
};
$("articleForm").onsubmit = (e) => {
  e.preventDefault();
  void (async () => {
    if (!(await beforeSwitch())) return;
    await mutate("create_article", { title: input("articleTitle") });
    article = theme!.articles.at(-1)!;
    mount();
    render();
    ($("articleTitle") as HTMLInputElement).value = "";
  })().catch(report);
};
$("sourceForm").onsubmit = (e) => {
  e.preventDefault();
  void (async () => {
    if (!(await save())) return;
    await mutate("add_source", { path: input("sourcePath") });
  })().catch(report);
};
$("chatForm").onsubmit = (e) => {
  e.preventDefault();
  const text = input("chatInput");
  void (async () => {
    if (!text || !(await save())) return;
    if (generating) throw new Error("AIの応答を待っています");
    await mutate("add_message", { role: "user", text });
    ($("chatInput") as HTMLTextAreaElement).value = "";
    await runGenerate("chat", text);
  })().catch(report);
};
$("openArticleForm").onsubmit = (e) => {
  e.preventDefault();
  void (async () => {
    if (!(await beforeSwitch())) return;
    const episode = input("existingEpisode");
    await mutate("open_article", {
      draft_path: input("existingDraft"),
      ...(input("existingSkeleton")
        ? { skeleton_path: input("existingSkeleton") }
        : {}),
      ...(episode ? { episode: Number(episode) } : {}),
    });
    article = theme!.articles.at(-1)!;
    mount();
    render();
    notice("原稿と骨組みを元の場所に保ったまま接続しました。");
  })().catch(report);
};
$("connectionSettings").addEventListener("toggle", () => {
  if (!($("connectionSettings") as HTMLDetailsElement).open) return;
  void (async () => {
    const config = await connectionInfo();
    ($("settingsPath") as HTMLInputElement).value = config.settings_path;
    ($("profileId") as HTMLInputElement).value = config.profile_id || "";
    ($("modelName") as HTMLInputElement).value =
      config.model === "configured" ? "" : config.model;
    const pf = await connectionPreflight();
    $("connectionState").textContent =
      `CLI: ${pf.ai.installed ? "検出済み" : "未検出"} / ログイン: ${pf.ai.authenticated === true ? "確認済み" : pf.ai.authenticated === false ? "未確認" : "不明"} / 利用枠: 不明。保存先: ${pf.storage.drafts}`;
  })().catch(report);
});
$("connectionForm").onsubmit = (e) => {
  e.preventDefault();
  void (async () => {
    if (!(await beforeSwitch())) return;
    await configureConnection({
      settings_path: input("settingsPath"),
      profile_id: input("profileId"),
      model: input("modelName"),
    });
    themes = (await listThemes()).themes;
    theme = themes[0] ? await getTheme(themes[0].id) : null;
    article = theme?.articles[0] || null;
    mount();
    render();
    notice("接続と保存先を読み戻しました。認証や元の原稿は変更していません。");
  })().catch(report);
};
$("save").onclick = safe(save);
$("toggleRight").onclick = () => {
  const el = document.querySelector(".right") as HTMLElement;
  el.hidden = !el.hidden;
  $("toggleRight").setAttribute("aria-expanded", String(!el.hidden));
  document.querySelector("main")!.classList.toggle("right-hidden", el.hidden);
};
document
  .querySelectorAll<HTMLButtonElement>("[data-tab]")
  .forEach((b) => (b.onclick = () => tab(b.dataset.tab!)));
document
  .querySelectorAll<HTMLButtonElement>("[data-mode]")
  .forEach((b) => (b.onclick = safe(() => runGenerate(b.dataset.mode!))));
document.querySelectorAll<HTMLButtonElement>("[data-format]").forEach(
  (b) =>
    (b.onclick = () => {
      if (!editor) return;
      const c = editor.chain().focus();
      switch (b.dataset.format) {
        case "bold":
          c.toggleBold().run();
          break;
        case "italic":
          c.toggleItalic().run();
          break;
        case "h2":
          c.toggleHeading({ level: 2 }).run();
          break;
        case "h3":
          c.toggleHeading({ level: 3 }).run();
          break;
        case "paragraph":
          c.setParagraph().run();
          break;
        case "bullet":
          c.toggleBulletList().run();
          break;
        case "ordered":
          c.toggleOrderedList().run();
          break;
        case "quote":
          c.toggleBlockquote().run();
          break;
      }
    }),
);
document
  .querySelectorAll<HTMLButtonElement>("[data-history]")
  .forEach(
    (b) =>
      (b.onclick = safe(() =>
        mutate(b.dataset.history!, { article_id: article?.id }, true),
      )),
  );
$("linkButton").onclick = () => {
  $("linkControls").hidden = !$("linkControls").hidden;
};
$("applyLink").onclick = () => {
  const href = input("linkUrl");
  if (!/^https?:\/\//i.test(href)) {
    notice("http または https のURLを入力してください");
    return;
  }
  editor?.chain().focus().extendMarkRange("link").setLink({ href }).run();
  $("linkControls").hidden = true;
};
$("removeLink").onclick = () => {
  editor?.chain().focus().unsetLink().run();
};
document.querySelectorAll<HTMLButtonElement>("[data-decision]").forEach(
  (b) =>
    (b.onclick = safe(async () => {
      const ids = Array.from(
        document.querySelectorAll<HTMLInputElement>("[data-proposal]:checked"),
      ).map((x) => x.dataset.proposal!);
      if (!ids.length) throw new Error("提案を選択してください");
      await mutate(
        "decide",
        {
          proposal_ids: ids,
          decision: b.dataset.decision,
          scope: input("learningScope"),
        },
        true,
      );
    })),
);
$("commentSelection").onclick = safe(async () => {
  if (!editor || !article) throw new Error("本文を選択してください");
  const { from, to } = editor.state.selection;
  if (from === to) throw new Error("本文を選択してください");
  const nodes: { id: string; from: number; to: number }[] = [];
  editor.state.doc.forEach((n, pos) =>
    nodes.push({ id: n.attrs.blockId, from: pos, to: pos + n.nodeSize }),
  );
  const quote = editor.state.doc.textBetween(from, to, "\n");
  const anchor = selectionMetadata(nodes, from, to, quote);
  const text = input("commentText");
  if (!text) throw new Error("コメントを入力してください");
  if (!(await save())) return;
  await mutate("add_comment", { article_id: article.id, ...anchor, text });
  ($("commentText") as HTMLTextAreaElement).value = "";
});
$("exportDraft").onclick = () => {
  if (article) download(`${article.title}.md`, article.draft, "text/markdown");
};
$("downloadBuffer").onclick = () =>
  download("未保存の本文.md", currentMarkdown(), "text/markdown");
$("exportTheme").onclick = () => {
  if (theme)
    download(
      `${theme.title}.json`,
      JSON.stringify(theme, null, 2),
      "application/json",
    );
};
$("refresh").onclick = safe(async () => {
  if (!theme) return;
  const selected = article?.id;
  theme = await getTheme(theme.id);
  article = theme.articles.find((a) => a.id === selected) || article;
  if (!dirty) mount();
  else {
    conflicted = true;
    clearTimeout(timer);
  }
  render();
  notice(
    dirty
      ? "最新状態を取得しました。編集中の本文は保持しています。"
      : "最新状態を取得しました。",
  );
});
$("reloadDraft").onclick = safe(async () => {
  if (dirty) {
    download("再読込み前の本文.md", currentMarkdown(), "text/markdown");
    throw new Error(
      "編集中の本文を退避しました。先に保存または復旧してください。",
    );
  }
  await mutate("reload_draft", { article_id: article?.id }, true);
});
let compared: {themeId:string; articleId:string; revision:number; hash:string; draft:string; blocks:Article["blocks"]; editVersion:number}|null=null;
$("recover").onclick = safe(async () => {
  const hadDirty=dirty;
  await mutate("recover", {});
  if(hadDirty){dirty=true;conflicted=true;} else mount();
  render();
  notice(hadDirty?"中断した保存を巻き戻しました。編集中の本文は保持しています。比較してから保存してください。":"中断した保存を巻き戻し、正常な版を読み戻しました。");
});
$("compareBuffer").onclick=safe(async()=>{
  if(!theme||!article)throw new Error('記事を選択してください');
  const themeId=theme.id,articleId=article.id,draft=currentMarkdown(),blocks=editorBlocks(),version=editVersion;
  clearTimeout(timer);editor?.setEditable(false);
  try{
    const latest=await getTheme(themeId);const current=latest.articles.find(a=>a.id===articleId);
    if(!current?.observed_draft_sha256)throw new Error('最新稿の版を確認できません');
    theme=latest;article=current;compared={themeId,articleId,revision:latest.revision,hash:current.observed_draft_sha256,draft,blocks,editVersion:version};
    $('latestVersion').textContent=current.draft;$('bufferVersion').textContent=draft;$('conflictComparison').hidden=false;
    conflicted=true;dirty=true;render();
  }catch(error){editor?.setEditable(true);throw error;}
});
$('cancelComparison').onclick=()=>{compared=null;$('conflictComparison').hidden=true;editor?.setEditable(true);notice('編集内容を保持しています。最新稿は変更していません。');};
$('applyBuffer').onclick=safe(async()=>{
  if(!compared||editVersion!==compared.editVersion)throw new Error('編集内容が変わりました。もう一度比較してください');
  const pending=compared;
  try{
    const saved=await action(pending.themeId,'resolve_draft',{article_id:pending.articleId,draft:pending.draft,blocks:pending.blocks,expected_draft_sha256:pending.hash},pending.revision);
    const selected=saved.articles.find(a=>a.id===pending.articleId);
    if(selected?.draft!==pending.draft)throw new Error('保存後の本文が一致しません。編集を保持しています。');
    theme=saved;article=selected;compared=null;dirty=false;conflicted=false;$('conflictComparison').hidden=true;mount();render();notice('比較した本文を保存し、読み戻しました。');
  }catch(error){compared=null;dirty=true;conflicted=true;editor?.setEditable(true);throw error;}
});

window.addEventListener("beforeunload", (e) => {
  if (dirty) {
    e.preventDefault();
    e.returnValue = "";
  }
});
void initApi()
  .then(async (result) => {
    themes = result.themes;
    if (themes[0]) {
      theme = await getTheme(themes[0].id);
      article = theme.articles[0] || null;
    }
    mount();
    render();
  })
  .catch(report);
