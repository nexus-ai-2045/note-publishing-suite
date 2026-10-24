export type Theme = {
  id: string;
  title: string;
  revision: number;
  messages: Message[];
  sources: Source[];
  articles: Article[];
  proposals: Proposal[];
  comments: Comment[];
  conflicts?: { article_id: string; kind: string; path: string }[];
};
export type Message = { id: string; role: string; text: string };
export type Source = { id: string; path: string; text: string; kind: string };
export type Block = {
  id: string;
  text: string;
  kind?: string;
  source_refs?: string[];
  provenance_kind?: string;
  correspondence_status?: string;
  lineage?: string[];
};
export type Article = {
  id: string;
  title: string;
  revision: number;
  draft: string;
  observed_draft_sha256?: string;
  blocks: Block[];
  skeleton: {
    sections: { id: string; heading: string; paragraph_ids: string[] }[];
  };
};
export type Proposal = {
  id: string;
  article_id: string;
  target: string;
  before: string;
  after: string;
  intent: string;
  status: string;
  scope: string;
  base_revision: number;
};
export type Comment = {
  id: string;
  article_id: string;
  quote: string;
  text: string;
  block_id?: string;
  status: string;
};
let token = "";
export function articlePayload(
  name: string,
  payload: Record<string, unknown>,
  articleId?: string,
) {
  const scoped = [
    "decide",
    "save_draft",
    "set_skeleton",
    "add_comment",
    "propose",
    "undo",
    "redo",
    "reload_draft",
    "revoke_learning",
    "resolve_draft",
  ];
  if (!scoped.includes(name)) return payload;
  if (!articleId && !payload.article_id)
    throw new Error("対象の記事を選んでください");
  return { article_id: articleId, ...payload };
}
async function request<T>(url: string, init: RequestInit = {}): Promise<T> {
  const headers = new Headers(init.headers);
  headers.set("Accept", "application/json");
  if (init.body) headers.set("Content-Type", "application/json");
  if (token) headers.set("X-NPS-Session", token);
  const res = await fetch(url, { ...init, headers });
  const body = await res.json();
  if (!res.ok)
    throw Object.assign(new Error(body.error || "要求に失敗しました"), body);
  return body as T;
}
export async function initApi() {
  const config = await request<{ session_token: string }>("/api/config");
  token = config.session_token;
  return request<{ themes: { id: string; title: string; revision: number }[] }>(
    "/api/themes",
  );
}
export const getTheme = (id: string) =>
  request<Theme>(`/api/themes/${encodeURIComponent(id)}`);
export const createTheme = (title: string) =>
  request<Theme>("/api/themes", {
    method: "POST",
    body: JSON.stringify({ title }),
  });
export async function action(
  id: string,
  action: string,
  payload: Record<string, unknown>,
  revision: number,
) {
  return request<Theme>(`/api/themes/${encodeURIComponent(id)}/actions`, {
    method: "POST",
    body: JSON.stringify({ action, payload, expected_revision: revision }),
  });
}
export async function generate(id: string, payload: Record<string, unknown>) {
  const job = await request<{ job_id: string }>(
    `/api/themes/${encodeURIComponent(id)}/generate`,
    { method: "POST", body: JSON.stringify(payload) },
  );
  for (let i = 0; i < 240; i++) {
    await new Promise((r) => setTimeout(r, 1000));
    const state = await request<{
      status: string;
      theme?: Theme;
      error?: string;
      candidate?: unknown;
    }>(`/api/jobs/${job.job_id}`);
    if (state.status === "complete" && state.theme) return state.theme;
    if (state.status === "failed")
      throw Object.assign(
        new Error(state.error || "生成に失敗しました"),
        state,
        { job_id: job.job_id },
      );
  }
  throw new Error("生成の待機がタイムアウトしました。処理ID: " + job.job_id);
}

export const connectionInfo = () => request<any>("/api/config");
export const connectionPreflight = () => request<any>("/api/preflight");
export const configureConnection = (payload: Record<string, unknown>) =>
  request<any>("/api/preferences", {
    method: "POST",
    body: JSON.stringify(payload),
  });
export const listThemes = () =>
  request<{ themes: { id: string; title: string; revision: number }[] }>(
    "/api/themes",
  );
