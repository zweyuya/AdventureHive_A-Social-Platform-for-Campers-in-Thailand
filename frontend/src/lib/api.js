// Talks to the Django API. Tokens live in httpOnly cookies the browser sends
// automatically; we add the CSRF token (double-submit) on every unsafe request
// and transparently refresh the 15-minute access token once on a 401.

export function getCookie(name) {
  const m = document.cookie.match(new RegExp("(?:^|; )" + name + "=([^;]*)"));
  return m ? decodeURIComponent(m[1]) : null;
}

async function ensureCsrf() {
  if (!getCookie("csrftoken")) await fetch("/api/auth/csrf/", { credentials: "include" });
}

export class ApiError extends Error {
  constructor(status, data) {
    super(flatten(data) || `Request failed (${status})`);
    this.status = status;
    this.data = data || {};
  }
  field(name) {
    const v = this.data?.[name];
    return Array.isArray(v) ? v.join(" ") : typeof v === "string" ? v : null;
  }
}

function flatten(data) {
  if (!data) return "";
  if (typeof data === "string") return data;
  if (Array.isArray(data)) return data.map(flatten).join(" ");
  if (data.detail) return flatten(data.detail);
  return Object.entries(data)
    .map(([k, v]) => (k === "non_field_errors" ? flatten(v) : `${k.replaceAll("_", " ")}: ${flatten(v)}`))
    .join(" ");
}

let refreshing = null;
function refreshToken() {
  refreshing ??= fetch("/api/auth/token/refresh/", { method: "POST", credentials: "include" })
    .then((r) => r.ok)
    .finally(() => setTimeout(() => (refreshing = null), 0));
  return refreshing;
}

export async function api(path, { method = "GET", body, retry = true } = {}) {
  const unsafe = method !== "GET";
  if (unsafe) await ensureCsrf();
  const res = await fetch(`/api${path}`, {
    method,
    credentials: "include",
    headers: {
      ...(body !== undefined && { "Content-Type": "application/json" }),
      ...(unsafe && { "X-CSRFToken": getCookie("csrftoken") || "" }),
    },
    body: body !== undefined ? JSON.stringify(body) : undefined,
  });
  if (res.status === 401 && retry && !path.startsWith("/auth/")) {
    if (await refreshToken()) return api(path, { method, body, retry: false });
  }
  if (res.status === 204) return null;
  const data = await res.json().catch(() => null);
  if (!res.ok) throw new ApiError(res.status, data);
  return data;
}

/** Upload a file (multipart/form-data). Same cookie, CSRF and refresh handling as api(). */
export async function apiUpload(path, formData, { method = "PUT", retry = true } = {}) {
  await ensureCsrf();
  const res = await fetch(`/api${path}`, {
    method, credentials: "include", body: formData,
    headers: { "X-CSRFToken": getCookie("csrftoken") || "" }, // browser sets the multipart boundary
  });
  if (res.status === 401 && retry && (await refreshToken())) return apiUpload(path, formData, { method, retry: false });
  const data = await res.json().catch(() => null);
  if (!res.ok) throw new ApiError(res.status, data);
  return data;
}

// Paginated endpoints return {count, results}; some lists are plain arrays.
export const results = (data) => (Array.isArray(data) ? data : data?.results ?? []);
