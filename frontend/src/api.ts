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
