import { describe, it, expect } from "vitest";
import {
  blocksForSave,
  parseBlocks,
  serializeBlocks,
  serializeDocument,
  bindBaseline,
  selectionMetadata,
} from "./metadata";
import type { JSONContent } from "@tiptap/core";
describe("lossless Markdown", () => {
  it.each([
    "---\ntitle: demo\n---\n\n<!-- source: abc -->\n\n# Heading\n\nBody\n",
    "first\r\n\r\nsecond\r\n\r\n",
    'first\n\n<figure>\n<img src="a">\n<figcaption>caption</figcaption>\n</figure>\n\nlast',
    "first\n\n| a | b |\n| - | - |\n| 1 | 2 |\n\nlast\n",
    "x\n\n```ts\nlet x=1\n```\n\ny",
    "no newline",
  ])("preserves bytes: %s", (source) => {
    const doc = parseBlocks(source);
    expect(serializeBlocks(doc, doc.blocks)).toBe(source);
  });
  it("keeps internal metadata outside visible editor nodes", () => {
    const doc = parseBlocks(
      "---\ntitle: x\n---\n\n<!-- paragraph-id: source-1 -->\nBody\n",
    );
    expect(
      doc.pieces.some(
        (p) => p.raw.includes("title:") || p.raw.includes("paragraph-id:"),
      ),
    ).toBe(false);
    expect(serializeDocument(doc, [])).toContain("title: x");
  });
  it("keeps duplicate paragraphs distinct", () => {
    const doc = parseBlocks("same\n\nsame\n");
    expect(doc.blocks).toHaveLength(2);
    expect(doc.blocks[0].id).not.toBe(doc.blocks[1].id);
  });
  it("reuses matched server IDs once", () => {
    const doc = parseBlocks("same\n\nsame", [{ id: "saved", text: "same" }]);
    expect(doc.blocks[0].id).toBe("saved");
    expect(doc.blocks[1].id).not.toBe("saved");
  });
  it("edits only one node and retains metadata and unknown position", () => {
    const source =
      "---\ntitle: x\n---\n\nfirst\n\n<figure>\ncaption\n</figure>\n\nlast\n";
    const doc = parseBlocks(source);
    const nodes: JSONContent[] = doc.pieces.map((p) =>
      p.kind === "opaque"
        ? { type: "opaque", attrs: { blockId: p.id, raw: p.raw } }
        : {
            type: "paragraph",
            attrs: { blockId: p.id },
            content: [{ type: "text", text: p.raw.trim() }],
          },
    );
    bindBaseline(doc, nodes);
    expect(serializeDocument(doc, nodes)).toBe(source);
    nodes.find(
      (n) => n.type === "paragraph" && n.content?.[0]?.text === "first",
    )!.content![0].text = "updated";
    expect(serializeDocument(doc, nodes)).toBe(
      source.replace("first", "updated"),
    );
  });
  it("detects heading attribute changes", () => {
    const doc = parseBlocks("# title\n");
    const nodes: JSONContent[] = [
      {
        type: "heading",
        attrs: { blockId: doc.pieces[0].id, level: 1 },
        content: [{ type: "text", text: "title" }],
      },
    ];
    bindBaseline(doc, nodes);
    nodes[0].attrs!.level = 2;
    expect(serializeDocument(doc, nodes)).toBe("## title\n");
  });
  it("selection has a stable block anchor only within one block", () => {
    const blocks = [
      { id: "a", from: 0, to: 7 },
      { id: "b", from: 7, to: 13 },
    ];
    expect(selectionMetadata(blocks, 1, 5, "text").block_id).toBe("a");
    expect(selectionMetadata(blocks, 1, 10, "text").block_id).toBeUndefined();
  });
});

it.each(["first", "first\r\n"])(
  "new paragraph remains separate after a source without blank separator: %s",
  (source) => {
    const doc = parseBlocks(source);
    const initial: JSONContent = {
      type: "paragraph",
      attrs: { blockId: doc.pieces[0].id },
      content: [{ type: "text", text: "first" }],
    };
    bindBaseline(doc, [initial]);
    const appended: JSONContent = {
      type: "paragraph",
      attrs: { blockId: "new-paragraph" },
      content: [{ type: "text", text: "second" }],
    };
    const serialized = serializeDocument(doc, [initial, appended]);
    expect(parseBlocks(serialized).blocks.map((b) => b.text.trim())).toEqual([
      "first",
      "second",
    ]);
  },
);

describe("saved provenance", () => {
  it("retains immutable table metadata when another paragraph changes", () => {
    const table = {
      id: "table",
      text: "| A | B |",
      source_refs: ["source:s1"],
      provenance_kind: "external-fact",
      correspondence_status: "proposed",
    };
    const saved = blocksForSave(
      [
        { type: "opaque", attrs: { blockId: "table", raw: table.text } },
        {
          type: "paragraph",
          attrs: { blockId: "p" },
          content: [{ type: "text", text: "Edited" }],
        },
      ],
      [table, { id: "p", text: "Original" }],
    );
    expect(saved[0]).toMatchObject(table);
    expect(saved[1].correspondence_status).toBe("needs_review");
  });
  it("unions retained ID and every merged ancestor reference", () => {
    const saved = blocksForSave(
      [
        {
          type: "paragraph",
          attrs: { blockId: "first", lineage: ["first", "second"] },
          content: [{ type: "text", text: "One Two" }],
        },
      ],
      [
        {
          id: "first",
          text: "One",
          source_refs: ["message:m1", "source:shared"],
        },
        {
          id: "second",
          text: "Two",
          source_refs: ["message:m2", "source:shared"],
        },
      ],
    );
    expect(saved[0].source_refs).toEqual([
      "message:m1",
      "source:shared",
      "message:m2",
    ]);
    expect(saved[0].correspondence_status).toBe("needs_review");
  });
});
