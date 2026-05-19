// Typed fetch client wrapping the FastAPI backend.

const API_BASE = import.meta.env.VITE_API_BASE ?? "";

class ApiError extends Error {
  constructor(public status: number, public body: unknown, message: string) {
    super(message);
  }
}

async function request<T>(
  path: string,
  init: RequestInit & { params?: Record<string, unknown> } = {}
): Promise<T> {
  const { params, ...rest } = init;
  const url = new URL(API_BASE + path, window.location.origin);
  if (params) {
    for (const [k, v] of Object.entries(params)) {
      if (v == null || v === "") continue;
      if (Array.isArray(v)) v.forEach((vv) => url.searchParams.append(k, String(vv)));
      else url.searchParams.append(k, String(v));
    }
  }
  const res = await fetch(url.toString(), {
    credentials: "include",
    headers: { "Content-Type": "application/json", ...(rest.headers ?? {}) },
    ...rest,
  });
  if (!res.ok) {
    let body: unknown = null;
    try { body = await res.json(); } catch { /* empty */ }
    if (res.status === 401) {
      window.location.href = "/login";
    }
    throw new ApiError(res.status, body, `${res.status} ${res.statusText}`);
  }
  // 204 / empty body
  const txt = await res.text();
  return (txt ? JSON.parse(txt) : null) as T;
}

export const api = {
  get:  <T>(p: string, params?: Record<string, unknown>) => request<T>(p, { method: "GET", params }),
  post: <T>(p: string, body?: unknown, params?: Record<string, unknown>) =>
        request<T>(p, { method: "POST", body: body == null ? null : JSON.stringify(body), params }),
};

// Convenience helper for binary downloads (Excel exports).
export async function downloadFile(path: string, filename: string) {
  const res = await fetch(API_BASE + path, { credentials: "include" });
  if (!res.ok) throw new Error(`Download failed: ${res.status}`);
  const blob = await res.blob();
  const a = document.createElement("a");
  a.href = URL.createObjectURL(blob);
  a.download = filename;
  document.body.appendChild(a);
  a.click();
  a.remove();
  URL.revokeObjectURL(a.href);
}
