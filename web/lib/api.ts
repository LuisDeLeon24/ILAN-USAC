export class ApiError extends Error {
  status: number;

  constructor(status: number, message: string) {
    super(message);
    this.status = status;
  }
}

export async function api<T>(path: string, init: RequestInit = {}): Promise<T> {
  const headers = new Headers(init.headers);
  if (init.body) {
    headers.set("Content-Type", "application/json");
  }
  const token = sessionStorage.getItem("sentinel_token");
  if (token) {
    headers.set("Authorization", `Bearer ${token}`);
  }
  const response = await fetch(`/backend${path}`, { ...init, headers });
  if (response.status === 401 && path !== "/auth/login") {
    sessionStorage.removeItem("sentinel_token");
    window.location.assign("/login");
    throw new ApiError(401, "Sesión inválida");
  }
  if (response.status === 204) {
    return undefined as T;
  }
  const payload = (await response.json().catch(() => ({}))) as { detail?: unknown };
  if (!response.ok) {
    const detail = payload.detail;
    const message = typeof detail === "string" ? detail : "No se pudo completar la acción";
    throw new ApiError(response.status, message);
  }
  return payload as T;
}

export async function apiBlob(path: string): Promise<string> {
  const headers = new Headers();
  const token = sessionStorage.getItem("sentinel_token");
  if (token) {
    headers.set("Authorization", `Bearer ${token}`);
  }
  const response = await fetch(`/backend${path}`, { headers });
  if (response.status === 401) {
    sessionStorage.removeItem("sentinel_token");
    window.location.assign("/login");
    throw new ApiError(401, "Sesión inválida");
  }
  if (!response.ok) {
    throw new ApiError(response.status, "No se pudo cargar la imagen");
  }
  return URL.createObjectURL(await response.blob());
}
