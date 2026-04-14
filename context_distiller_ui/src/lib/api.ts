export type Cfg = { base: string };

export class ApiErr extends Error {
  status?: number; body?: unknown;
  constructor(m: string, s?: number, b?: unknown) { super(m); this.status = s; this.body = b; }
}

async function rd(r: Response) { const t = await r.text(); try { return JSON.parse(t); } catch { return t; } }

export async function post<T = unknown>(c: Cfg, p: string, b: unknown): Promise<T> {
  const r = await fetch(`${c.base.replace(/\/$/, "")}${p}`, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(b) });
  if (!r.ok) throw new ApiErr(`HTTP ${r.status}`, r.status, await rd(r));
  return (await rd(r)) as T;
}
export async function get<T = unknown>(c: Cfg, p: string): Promise<T> {
  const r = await fetch(`${c.base.replace(/\/$/, "")}${p}`);
  if (!r.ok) throw new ApiErr(`HTTP ${r.status}`, r.status, await rd(r));
  return (await rd(r)) as T;
}
export async function put<T = unknown>(c: Cfg, p: string, b: unknown): Promise<T> {
  const r = await fetch(`${c.base.replace(/\/$/, "")}${p}`, { method: "PUT", headers: { "Content-Type": "application/json" }, body: JSON.stringify(b) });
  if (!r.ok) throw new ApiErr(`HTTP ${r.status}`, r.status, await rd(r));
  return (await rd(r)) as T;
}
export async function upload(c: Cfg, f: File) {
  const fd = new FormData(); fd.append("file", f);
  const r = await fetch(`${c.base.replace(/\/$/, "")}/v1/upload`, { method: "POST", body: fd });
  if (!r.ok) throw new ApiErr(`Upload ${r.status}`, r.status, await rd(r));
  return (await r.json()) as { filename: string; saved_as: string; path: string };
}
