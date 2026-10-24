import MarkdownIt from "markdown-it";
import type { JSONContent } from "@tiptap/core";
import type { Block } from "./api";
const md = new MarkdownIt({ html: true, breaks: false });
export type Piece = {
  id: string;
  raw: string;
  prefix: string;
  kind: string;
  html: string;
  baseline?: string;
};
export type MarkdownDocument = {
  pieces: Piece[];
  tail: string;
  eol: string;
  frontmatter: string;
  blocks: Block[];
  unknown: string[];
};
let sequence = 0;
export const newId = () => `local-${Date.now().toString(36)}-${++sequence}`;
export function parseBlocks(
  source: string,
  existing: Block[] = [],
): MarkdownDocument {
  const lines = source.match(/[^\n]*\n|[^\n]+$/g) || [];
  const offsets = [0];
  for (const l of lines) offsets.push(offsets.at(-1)! + l.length);
  const eol = source.includes("\r\n") ? "\r\n" : "\n";
  let start = 0;
  let frontmatter = "";
  if (lines[0]?.trim() === "---") {
    const end = lines.findIndex((l, i) => i > 0 && l.trim() === "---");
    if (end >= 0) {
      start = end + 1;
      frontmatter = source.slice(0, offsets[start]);
    }
  }
  const remainder = source.slice(offsets[start]);
  const tokens = md.parse(remainder, {});
  const pieces: Piece[] = [];
  let cursor = 0;
  const used = new Set<string>();
  for (let i = 0; i < tokens.length; i++) {
    const t = tokens[i];
    if (t.level !== 0 || !t.map || t.nesting === -1) continue;
    let last = i;
    if (t.nesting === 1) {
      for (let j = i + 1; j < tokens.length; j++) {
        if (tokens[j].level === 0 && tokens[j].nesting === -1) {
          last = j;
          break;
        }
      }
    }
    const from = offsets[start + t.map[0]] - offsets[start];
    const to = offsets[start + t.map[1]] - offsets[start];
    const raw = remainder.slice(from, to);
    if (
      t.type === "html_block" &&
      /^\s*<!--/.test(raw) &&
      !raw.replace(/<!--[\s\S]*?-->/g, "").trim()
    ) {
      i = last;
      continue;
    }
    const normalized = raw.trim();
    const matched = existing.find(
      (b) =>
        !used.has(b.id) &&
        (b.text.trim() === normalized ||
          normalized.replace(/^#{1,6}\s+/, "") === b.text.trim()),
    );
    const id = matched?.id || newId();
    used.add(id);
    const safe =
      [
        "paragraph_open",
        "heading_open",
        "bullet_list_open",
        "ordered_list_open",
        "blockquote_open",
      ].includes(t.type) &&
      !/(^|\n)\s*(<|\|)|!\[|\n\s*[-=]{3,}\s*(\n|$)/.test(raw) &&
      !tokens
        .slice(i, last + 1)
        .some((x) =>
          x.children?.some((c: any) =>
            ["image", "code_inline", "html_inline"].includes(c.type),
          ),
        );
    pieces.push({
      id,
      raw,
      prefix: remainder.slice(cursor, from),
      kind: safe ? "supported" : "opaque",
      html: safe
        ? md.renderer.render(tokens.slice(i, last + 1), md.options, {})
        : "",
    });
    cursor = to;
    i = last;
  }
  return {
    pieces,
    tail: remainder.slice(cursor),
    eol,
    frontmatter,
    blocks: pieces
      .filter((p) => p.kind === "supported")
      .map((p) => ({ id: p.id, text: p.raw, kind: "paragraph" })),
    unknown: pieces
      .filter((p) => p.kind === "opaque" && p.raw !== frontmatter)
      .map((p) => p.raw),
  };
}
const signature = (node: JSONContent): string =>
  JSON.stringify({
    ...node,
    attrs: node.attrs
      ? Object.fromEntries(
          Object.entries(node.attrs).filter(
            ([k]) => !["blockId", "lineage"].includes(k),
          ),
        )
      : undefined,
    content: node.content?.map((n) => JSON.parse(signature(n))),
  });
export function bindBaseline(doc: MarkdownDocument, nodes: JSONContent[]) {
  nodes.forEach((n) => {
    const p = doc.pieces.find((p) => p.id === n.attrs?.blockId);
    if (p) p.baseline = signature(n);
  });
}
function inline(n: JSONContent): string {
  if (n.type === "hardBreak") return "  \n";
  if (n.type === "text") {
    let s = (n.text || "").replace(/([\\`*_[\]<>])/g, "\\$1");
    for (const m of n.marks || []) {
      if (m.type === "bold") s = `**${s}**`;
      if (m.type === "italic") s = `*${s}*`;
      if (m.type === "link")
        s = `[${s}](${String(m.attrs?.href || "").replace(/\)/g, "%29")})`;
    }
    return s;
  }
  return (n.content || []).map(inline).join("");
}
export function nodeMarkdown(n: JSONContent): string {
  if (n.type === "heading")
    return "#".repeat(n.attrs?.level || 1) + " " + inline(n);
  if (n.type === "paragraph") return inline(n);
  if (n.type === "blockquote")
    return (n.content || [])
      .map(nodeMarkdown)
      .join("\n\n")
      .split("\n")
      .map((l) => "> " + l)
      .join("\n");
  if (n.type === "bulletList" || n.type === "orderedList")
    return (n.content || [])
      .map((item, i) => {
        const marker =
          n.type === "bulletList" ? "- " : `${(n.attrs?.start || 1) + i}. `;
        return (
          marker +
          (item.content || [])
            .map(nodeMarkdown)
            .join("\n\n")
            .replace(/\n/g, "\n" + " ".repeat(marker.length))
        );
      })
      .join("\n");
  return inline(n);
}
export function serializeDocument(
  doc: MarkdownDocument,
  nodes: JSONContent[],
): string {
  const seen = new Set<string>();
  let out = doc.frontmatter;
  for (const n of nodes) {
    const id = n.attrs?.blockId;
    const p = !seen.has(id) ? doc.pieces.find((p) => p.id === id) : undefined;
    seen.add(id);
    if (p && (p.kind === "opaque" || p.baseline === signature(n))) {
      out += p.prefix + p.raw;
      continue;
    }
    const body = nodeMarkdown(n).replace(/\n/g, doc.eol);
    const separation = p
      ? p.prefix
      : !out || out.endsWith(doc.eol + doc.eol)
        ? ""
        : out.endsWith(doc.eol)
          ? doc.eol
          : doc.eol + doc.eol;
    out +=
      separation +
      body +
      (p?.raw.endsWith(doc.eol) ? doc.eol : doc.eol + doc.eol);
  }
  return out + doc.tail;
}
export function serializeBlocks(
  doc: MarkdownDocument,
  edited: Block[],
): string {
  return (
    doc.frontmatter +
    doc.pieces
      .map((p) => {
        const b = edited.find((b) => b.id === p.id);
        return p.prefix + (b && b.text !== p.raw ? b.text : p.raw);
      })
      .join("") +
    doc.tail
  );
}
export function selectionMetadata(
  nodes: { id: string; from: number; to: number }[],
  from: number,
  to: number,
  quote: string,
) {
  const matches = nodes.filter((n) => from < n.to && to > n.from);
  return {
    quote,
    block_id: matches.length === 1 ? matches[0].id : undefined,
    block_ids: matches.map((n) => n.id),
  };
}

/** Preserve every node's provenance, including immutable Markdown and merged ancestors. */
export function blocksForSave(
  nodes: JSONContent[],
  existing: Block[],
): Block[] {
  return nodes.map((n) => {
    const id = n.attrs?.blockId || newId();
    const old = existing.find((b) => b.id === id);
    const lineage: string[] = Array.isArray(n.attrs?.lineage)
      ? n.attrs.lineage
      : n.attrs?.lineage
        ? [n.attrs.lineage]
        : [];
    const ancestors = existing.filter(
      (b) => b.id === id || lineage.includes(b.id),
    );
    const text =
      n.type === "opaque"
        ? String(n.attrs?.raw ?? old?.text ?? "")
        : nodeMarkdown(n);
    return {
      ...old,
      id,
      text,
      kind: n.type,
      source_refs: [...new Set(ancestors.flatMap((b) => b.source_refs || []))],
      correspondence_status:
        old?.text.trim() === text.trim() && ancestors.length <= 1
          ? old?.correspondence_status
          : "needs_review",
      ...(lineage.length ? { lineage } : {}),
    };
  });
}
