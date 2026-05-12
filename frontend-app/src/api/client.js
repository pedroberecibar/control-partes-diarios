import { routeMockRequest } from './mockRouter';

export const BASE_URL = 'http://localhost:8000';

// Placeholder hasta que haya auth real. El backend usa este header para
// resolver el usuario actual en endpoints que lo requieren (require_admin, etc.).
let _currentUserId = 1;
export const setCurrentUserId = (id) => { _currentUserId = id; };
export const getCurrentUserId = () => _currentUserId;

export async function apiFetch(path, options = {}) {
  if (import.meta.env.VITE_USE_MOCK === 'true') {
    return routeMockRequest(path, options);
  }
  const { headers: extraHeaders, body, ...rest } = options;
  const res = await fetch(`${BASE_URL}${path}`, {
    headers: {
      Accept: 'application/json',
      'X-Usuario-Id': String(_currentUserId),
      ...(body !== undefined ? { 'Content-Type': 'application/json' } : {}),
      ...extraHeaders,
    },
    ...(body !== undefined ? { body } : {}),
    ...rest,
  });
  if (!res.ok) {
    const body = await res.json().catch(() => ({}));
    throw new Error(body?.detail || `HTTP ${res.status}`);
  }
  return res.json();
}
