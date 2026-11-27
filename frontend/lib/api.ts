"use client";

/** Thin API client. Authorisation is always decided by the backend; this only transports requests. */

export class ApiError extends Error {
  status: number;
  code: string;
  details: unknown;
  constructor(status: number, code: string, message: string, details: unknown) {
    super(message);
    this.status = status;
    this.code = code;
    this.details = details;
  }
}

function csrfToken(): string {
  const match = document.cookie.split("; ").find((c) => c.startsWith("vx_csrf="));
  return match ? decodeURIComponent(match.split("=")[1]) : "";
}

async function handle<T>(res: Response): Promise<T> {
  if (res.ok) {
    const type = res.headers.get("content-type") || "";
    return (type.includes("application/json") ? await res.json() : await res.text()) as T;
  }
  let code = "error";
  let message = `Request failed (${res.status})`;
  let details: unknown = null;
  try {
    const body = await res.json();
    if (body?.error) {
      code = body.error.code;
      message = body.error.message;
      details = body.error.details;
    }
  } catch {
    /* non-JSON error */
  }
  if (res.status === 401 && typeof window !== "undefined") {
    const path = window.location.pathname;
    const publicPaths = ["/login", "/register", "/forgot-password", "/reset-password", "/verify-email", "/mfa"];
    if (code === "mfa_required" && path !== "/mfa") window.location.href = "/mfa";
    else if (code === "unauthenticated" && !publicPaths.includes(path)) {
      window.location.href = `/login?next=${encodeURIComponent(path + window.location.search)}`;
    }
  }
  throw new ApiError(res.status, code, message, details);
}

export async function apiGet<T = any>(path: string): Promise<T> {
  return handle<T>(await fetch(`/api/v1${path}`, { credentials: "same-origin", cache: "no-store" }));
}

export async function apiSend<T = any>(method: "POST" | "PATCH" | "DELETE", path: string, body?: unknown): Promise<T> {
  return handle<T>(
    await fetch(`/api/v1${path}`, {
      method,
      credentials: "same-origin",
      headers: { "content-type": "application/json", "x-csrf-token": csrfToken() },
      body: body === undefined ? undefined : JSON.stringify(body),
    }),
  );
}

export async function apiUpload<T = any>(path: string, form: FormData): Promise<T> {
  return handle<T>(
    await fetch(`/api/v1${path}`, {
      method: "POST",
      credentials: "same-origin",
      headers: { "x-csrf-token": csrfToken() },
      body: form,
    }),
  );
}

export function downloadUrl(path: string): string {
  return `/api/v1${path}`;
}
