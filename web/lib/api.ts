const API = "";
const DEFAULT_TIMEOUT_MS = 15_000;

export class ApiError extends Error {
  constructor(
    message: string,
    public status: number,
  ) {
    super(message);
  }
}

async function parseError(res: Response): Promise<string> {
  try {
    const j = await res.json();
    return j.detail || j.message || res.statusText;
  } catch {
    return res.statusText || `HTTP ${res.status}`;
  }
}

type FetchOpts = RequestInit & { timeoutMs?: number };

async function fetchWithTimeout(path: string, init: FetchOpts = {}): Promise<Response> {
  const timeoutMs = init.timeoutMs ?? DEFAULT_TIMEOUT_MS;
  const ctrl = new AbortController();
  const external = init.signal;
  const onAbort = () => ctrl.abort();
  if (external) {
    if (external.aborted) ctrl.abort();
    else external.addEventListener("abort", onAbort, { once: true });
  }
  const timer = setTimeout(() => ctrl.abort(), timeoutMs);
  try {
    const { timeoutMs: _t, signal: _s, ...rest } = init;
    return await fetch(`${API}${path}`, {
      cache: "no-store",
      ...rest,
      signal: ctrl.signal,
    });
  } catch (err) {
    if (err instanceof DOMException && err.name === "AbortError") {
      if (external?.aborted) throw err;
      throw new ApiError(`요청 시간 초과 (${timeoutMs / 1000}초)`, 408);
    }
    throw err;
  } finally {
    clearTimeout(timer);
    external?.removeEventListener("abort", onAbort);
  }
}

export async function apiGet<T>(path: string, init?: FetchOpts): Promise<T> {
  const res = await fetchWithTimeout(path, init);
  if (!res.ok) throw new ApiError(await parseError(res), res.status);
  return res.json();
}

export async function apiPost<T>(path: string, body?: unknown, init?: FetchOpts): Promise<T> {
  const res = await fetchWithTimeout(path, {
    method: "POST",
    headers: body ? { "Content-Type": "application/json" } : undefined,
    body: body ? JSON.stringify(body) : undefined,
    ...init,
  });
  if (!res.ok) throw new ApiError(await parseError(res), res.status);
  return res.json();
}

export async function apiPut<T>(path: string, body: unknown, init?: FetchOpts): Promise<T> {
  const res = await fetchWithTimeout(path, {
    method: "PUT",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
    ...init,
  });
  if (!res.ok) throw new ApiError(await parseError(res), res.status);
  return res.json();
}

export async function apiDelete<T>(path: string, init?: FetchOpts): Promise<T> {
  const res = await fetchWithTimeout(path, { method: "DELETE", ...init });
  if (!res.ok) throw new ApiError(await parseError(res), res.status);
  return res.json();
}

export async function apiUpload<T>(
  path: string,
  files: File[],
  params?: Record<string, string>,
  init?: FetchOpts,
): Promise<T> {
  const fd = new FormData();
  files.forEach((f) => fd.append("files", f));
  const qs = params ? `?${new URLSearchParams(params)}` : "";
  const res = await fetchWithTimeout(`${path}${qs}`, {
    method: "POST",
    body: fd,
    timeoutMs: 120_000,
    ...init,
  });
  if (!res.ok) throw new ApiError(await parseError(res), res.status);
  return res.json();
}
