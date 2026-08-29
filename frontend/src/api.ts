import { Results } from "./types";

const BASE = import.meta.env.VITE_API_BASE || "";

type JsonRecord = Record<string, unknown>;

function isRecord(value: unknown): value is JsonRecord {
  return value !== null && typeof value === "object" && !Array.isArray(value);
}

function asRecord(value: unknown): JsonRecord {
  return isRecord(value) ? value : {};
}

export function normalizeResults(value: unknown): Results {
  if (!isRecord(value)) {
    throw new Error("结果接口返回了无效的数据格式");
  }
  return {
    meta: asRecord(value.meta),
    model_nav: asRecord(value.model_nav),
    cost_scenarios: asRecord(value.cost_scenarios),
    ic_summary: Array.isArray(value.ic_summary) ? value.ic_summary : [],
    group_returns: asRecord(value.group_returns),
    factor_decay: asRecord(value.factor_decay),
    robustness: asRecord(value.robustness),
    feature_importance: asRecord(value.feature_importance),
  } as Results;
}

function apiErrorMessage(payload: unknown, status: number): string {
  const body = asRecord(payload);
  const error = asRecord(body.error);
  const detail = asRecord(body.detail);
  const message = error.message ?? detail.message ?? body.message;
  return typeof message === "string" ? message : `结果接口请求失败（HTTP ${status}）`;
}

export async function fetchResults(signal?: AbortSignal): Promise<Results> {
  const res = await fetch(`${BASE}/api/results`, { signal });
  let payload: unknown;
  try {
    payload = await res.json();
  } catch {
    throw new Error(`结果接口返回了无法解析的响应（HTTP ${res.status}）`);
  }
  if (!res.ok) throw new Error(apiErrorMessage(payload, res.status));
  return normalizeResults(payload);
}

export async function fetchMeta(): Promise<Record<string, unknown>> {
  const res = await fetch(`${BASE}/api/meta`);
  return res.json();
}
