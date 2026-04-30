export const BASE_URL = 'http://localhost:8000';

export async function apiFetch(path, options = {}) {
  const { headers: extraHeaders, ...rest } = options;
  const res = await fetch(`${BASE_URL}${path}`, {
    headers: { Accept: 'application/json', ...extraHeaders },
    ...rest,
  });
  if (!res.ok) {
    const body = await res.json().catch(() => ({}));
    throw new Error(body?.detail || `HTTP ${res.status}`);
  }
  return res.json();
}
