import { afterEach, expect, test, vi } from 'vitest';
import { reviewsApi, setAccessToken } from '../api/client';
import { handleCallback } from '../auth/oidc';
afterEach(() => { vi.unstubAllGlobals(); setAccessToken(null); sessionStorage.clear(); history.replaceState({}, '', '/'); });
test('sends bearer token and escapes query filters', async () => {
  const mock = vi.fn().mockResolvedValue(new Response(JSON.stringify({items:[],total:0,limit:20,offset:0})));
  vi.stubGlobal('fetch', mock); setAccessToken('synthetic-session');
  await reviewsApi.list({ language: 'python&x=1' });
  expect(mock.mock.calls[0][0]).toContain('language=python%26x%3D1');
  expect(mock.mock.calls[0][1].headers.Authorization).toBe('Bearer synthetic-session');
});
test('preserves empty DELETE responses', async () => {
  vi.stubGlobal('fetch', vi.fn().mockResolvedValue(new Response(null, {status:204})));
  await expect(reviewsApi.delete('review')).resolves.toBeUndefined();
});
test('rejects unsuccessful requests', async () => {
  vi.stubGlobal('fetch', vi.fn().mockResolvedValue(new Response(JSON.stringify({detail:'Denied'}), {status:403})));
  await expect(reviewsApi.list()).rejects.toThrow('Denied');
});
test('rejects OIDC state mismatch before sending credentials', async () => {
  const fetch = vi.fn(); vi.stubGlobal('fetch', fetch); sessionStorage.setItem('__pkce_state__', 'expected');
  history.replaceState({}, '', '/callback?code=unused&state=wrong');
  await expect(handleCallback()).rejects.toThrow('State mismatch'); expect(fetch).not.toHaveBeenCalled();
  expect(sessionStorage.getItem('__pkce_state__')).toBeNull();
});
