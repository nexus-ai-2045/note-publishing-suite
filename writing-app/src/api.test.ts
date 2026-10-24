import { afterEach, describe, it, expect, vi } from "vitest";
import { initApi, action, generate } from "./api";
const response = (data: unknown, status = 200) => ({
  ok: status < 400,
  status,
  json: async () => data,
});
afterEach(() => {
  vi.unstubAllGlobals();
  vi.useRealTimers();
});
describe("local API contract", () => {
  it("sends session token and optimistic revision", async () => {
    const fetch = vi
      .fn()
      .mockResolvedValueOnce(response({ session_token: "test-session" }))
      .mockResolvedValueOnce(response({ themes: [] }))
      .mockResolvedValueOnce(response({ id: "theme", revision: 2 }));
    vi.stubGlobal("fetch", fetch);
    await initApi();
    await action("theme", "add_message", { role: "user", text: "話そう" }, 1);
    const req = fetch.mock.calls[2][1];
    expect(req.headers.get("X-NPS-Session")).toBe("test-session");
    expect(JSON.parse(req.body)).toMatchObject({
      expected_revision: 1,
      payload: { text: "話そう" },
    });
  });
  it("chat without article waits beyond 30 seconds", async () => {
    vi.useFakeTimers();
    let count = 0;
    const fetch = vi.fn(async (url: string) =>
      url.endsWith("/generate")
        ? response({ job_id: "job" })
        : ++count < 35
          ? response({ status: "running" })
          : response({ status: "complete", theme: { id: "t" } }),
    );
    vi.stubGlobal("fetch", fetch);
    const pending = generate("t", {
      mode: "chat",
      instruction: "考えたい",
      expected_revision: 1,
    });
    await vi.advanceTimersByTimeAsync(35000);
    expect(await pending).toEqual({ id: "t" });
    expect(JSON.parse((fetch.mock.calls[0] as any)[1].body)).not.toHaveProperty(
      "article_id",
    );
  });
  it("retains stale generation candidate in the thrown result", async () => {
    vi.useFakeTimers();
    vi.stubGlobal(
      "fetch",
      vi
        .fn()
        .mockResolvedValueOnce(response({ job_id: "job" }))
        .mockResolvedValueOnce(
          response({
            status: "failed",
            error: "stale",
            candidate: { draft: "keep me" },
          }),
        ),
    );
    const pending = generate("t", { mode: "draft" });
    const assertion = expect(pending).rejects.toMatchObject({
      candidate: { draft: "keep me" },
      job_id: "job",
    });
    await vi.advanceTimersByTimeAsync(1000);
    await assertion;
  });
});

import { articlePayload } from "./api";
it("proposal batch targets the selected article even when the button payload has no article_id", () => {
  expect(
    articlePayload(
      "decide",
      { proposal_ids: ["p1"], decision: "adopted" },
      "selected-article",
    ),
  ).toEqual({
    article_id: "selected-article",
    proposal_ids: ["p1"],
    decision: "adopted",
  });
  expect(() => articlePayload("decide", {}, undefined)).toThrow();
  expect(articlePayload("add_message", { text: "問い" }, "a")).toEqual({
    text: "問い",
  });
});
