import { Results } from "./types";

const BASE = import.meta.env.VITE_API_BASE || "";

export async function fetchResults(signal?: AbortSignal): Promise<Results> {
  const res = await fetch(`${BASE}/api/results`, { signal });
  if (!res.ok) throw new Error(`HTTP ${res.status}`);
  return res.json();
}

export async function fetchMeta(): Promise<Record<string, unknown>> {
  const res = await fetch(`${BASE}/api/meta`);
  return res.json();
}

export interface RunParams {
  models?: string;
  top_k?: number;
  rebal_freq?: number;
  cost_bps?: number;
  hpo?: number;
}

export async function triggerRun(params: RunParams): Promise<{ status: string }> {
  const qs = new URLSearchParams();
  if (params.models) qs.set("models", params.models);
  if (params.top_k !== undefined) qs.set("top_k", String(params.top_k));
  if (params.rebal_freq !== undefined) qs.set("rebal_freq", String(params.rebal_freq));
  if (params.cost_bps !== undefined) qs.set("cost_bps", String(params.cost_bps));
  if (params.hpo !== undefined) qs.set("hpo", String(params.hpo));
  const res = await fetch(`${BASE}/api/run`, { method: "POST", body: qs });
  return res.json();
}

export async function fetchRunState(): Promise<{ running: boolean; last_run?: string; error?: string }> {
  const res = await fetch(`${BASE}/api/run/state`);
  return res.json();
}
