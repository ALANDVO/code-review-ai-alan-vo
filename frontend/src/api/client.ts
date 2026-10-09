/**
 * Typed API client for Code Review AI backend.
 *
 * SPA PKCE architecture: access tokens kept in memory only.
 * Bearer token is injected when available; requests fall through
 * to demo mode on the server when no token is present.
 */

import type {
  EvalRun,
  EvalRunList,
  HealthStatus,
  Review,
  ReviewList,
  ReviewRequest,
  Stats,
} from '@/types/api';

const BASE = import.meta.env.VITE_API_BASE_URL ?? '';

// In-memory token store (never written to localStorage or sessionStorage)
let _accessToken: string | null = null;

export function setAccessToken(token: string | null): void {
  _accessToken = token;
}

export function getAccessToken(): string | null {
  return _accessToken;
}

// ── Internal fetch wrapper ─────────────────────────────────────────────────────

interface ApiError {
  detail: string;
}

async function request<T>(
  method: string,
  path: string,
  body?: unknown,
): Promise<T> {
  const headers: Record<string, string> = {
    'Content-Type': 'application/json',
  };
  if (_accessToken) {
    headers['Authorization'] = `Bearer ${_accessToken}`;
  }

  const resp = await fetch(`${BASE}${path}`, {
    method,
    headers,
    body: body !== undefined ? JSON.stringify(body) : undefined,
  });

  if (resp.status === 204) {
    return undefined as T;
  }

  const data = await resp.json().catch(() => ({ detail: `HTTP ${resp.status}` }));
  if (!resp.ok) {
    const err = data as ApiError;
    throw new Error(err.detail ?? `HTTP ${resp.status}`);
  }
  return data as T;
}

// ── Reviews ────────────────────────────────────────────────────────────────────

export const reviewsApi = {
  submit: (req: ReviewRequest): Promise<Review> =>
    request<Review>('POST', '/api/reviews', req),

  list: (params?: { limit?: number; offset?: number; language?: string }): Promise<ReviewList> => {
    const qs = new URLSearchParams();
    if (params?.limit !== undefined) qs.set('limit', String(params.limit));
    if (params?.offset !== undefined) qs.set('offset', String(params.offset));
    if (params?.language) qs.set('language', params.language);
    const q = qs.toString();
    return request<ReviewList>('GET', `/api/reviews${q ? `?${q}` : ''}`);
  },

  get: (id: string): Promise<Review> =>
    request<Review>('GET', `/api/reviews/${id}`),

  delete: (id: string): Promise<void> =>
    request<void>('DELETE', `/api/reviews/${id}`),
};

// ── Evaluations ────────────────────────────────────────────────────────────────

export const evalsApi = {
  trigger: (trigger = 'manual'): Promise<EvalRun> =>
    request<EvalRun>('POST', '/api/evals', { trigger }),

  list: (params?: { limit?: number; offset?: number }): Promise<EvalRunList> => {
    const qs = new URLSearchParams();
    if (params?.limit !== undefined) qs.set('limit', String(params.limit));
    if (params?.offset !== undefined) qs.set('offset', String(params.offset));
    const q = qs.toString();
    return request<EvalRunList>('GET', `/api/evals${q ? `?${q}` : ''}`);
  },

  get: (id: string): Promise<EvalRun> =>
    request<EvalRun>('GET', `/api/evals/${id}`),
};

// ── Stats ──────────────────────────────────────────────────────────────────────

export const statsApi = {
  get: (): Promise<Stats> => request<Stats>('GET', '/api/stats'),
};

// ── Health ─────────────────────────────────────────────────────────────────────

export const healthApi = {
  check: (): Promise<HealthStatus> => request<HealthStatus>('GET', '/api/health'),
};
