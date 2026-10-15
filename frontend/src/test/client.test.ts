import React from 'react';
import { afterEach, expect, test, vi } from 'vitest';
import { render, screen, waitFor, fireEvent } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { exportJWK, generateKeyPair, SignJWT } from 'jose';
import { reviewsApi, setAccessToken, getAccessToken } from '../api/client';
import { handleCallback } from '../auth/oidc';
import { ReviewListPage } from '../pages/ReviewListPage';

afterEach(() => {
  vi.unstubAllGlobals();
  setAccessToken(null);
  sessionStorage.clear();
  history.replaceState({}, '', '/');
});

test('sends bearer token and escapes query filters including search and severity', async () => {
  const mock = vi.fn().mockResolvedValue(new Response(JSON.stringify({ items: [], total: 0, limit: 20, offset: 0 })));
  vi.stubGlobal('fetch', mock);
  setAccessToken('synthetic-session');
  await reviewsApi.list({ language: 'python&x=1', search: 'eval(x)', severity: 'critical' });
  const calledUrl = String(mock.mock.calls[0][0]);
  expect(calledUrl).toContain('language=python%26x%3D1');
  expect(calledUrl).toContain('search=eval%28x%29');
  expect(calledUrl).toContain('severity=critical');
  expect(mock.mock.calls[0][1].headers.Authorization).toBe('Bearer synthetic-session');
});

test('preserves empty DELETE responses', async () => {
  vi.stubGlobal('fetch', vi.fn().mockResolvedValue(new Response(null, { status: 204 })));
  await expect(reviewsApi.delete('review')).resolves.toBeUndefined();
});

test('rejects unsuccessful requests', async () => {
  vi.stubGlobal('fetch', vi.fn().mockResolvedValue(new Response(JSON.stringify({ detail: 'Denied' }), { status: 403 })));
  await expect(reviewsApi.list()).rejects.toThrow('Denied');
});

test('rejects OIDC state mismatch before sending credentials', async () => {
  const fetchMock = vi.fn();
  vi.stubGlobal('fetch', fetchMock);
  sessionStorage.setItem('__pkce_state__', 'expected');
  history.replaceState({}, '', '/callback?code=unused&state=wrong');
  await expect(handleCallback()).rejects.toThrow('State mismatch');
  expect(fetchMock).not.toHaveBeenCalled();
  expect(sessionStorage.getItem('__pkce_state__')).toBeNull();
});

test('completes PKCE callback with signed ID token verification and propagates access token', async () => {
  const { publicKey, privateKey } = await generateKeyPair('RS256');
  const publicJwk = await exportJWK(publicKey);
  publicJwk.alg = 'RS256';
  publicJwk.use = 'sig';
  publicJwk.kid = 'test-key-1';

  const issuer = 'http://127.0.0.1:8080/realms/code-review-realm';
  const clientId = 'code-review-client';
  const state = 'state-123';
  const nonce = 'nonce-456';
  const verifier = 'verifier-789';

  sessionStorage.setItem('__pkce_state__', state);
  sessionStorage.setItem('__pkce_nonce__', nonce);
  sessionStorage.setItem('__pkce_verifier__', verifier);
  history.replaceState({}, '', `/callback?code=auth-code-1&state=${state}`);

  const idToken = await new SignJWT({ email: 'alanvo@gmail.com', nonce })
    .setProtectedHeader({ alg: 'RS256', kid: 'test-key-1' })
    .setIssuer(issuer)
    .setAudience(clientId)
    .setSubject('user-alan')
    .setIssuedAt()
    .setExpirationTime('5m')
    .sign(privateKey);

  const accessToken = await new SignJWT({
    email: 'alanvo@gmail.com',
    realm_access: { roles: ['operator'] },
  })
    .setProtectedHeader({ alg: 'RS256', kid: 'test-key-1' })
    .setIssuer(issuer)
    .setAudience(clientId)
    .setSubject('user-alan')
    .setIssuedAt()
    .setExpirationTime('5m')
    .sign(privateKey);

  const fetchMock = vi.fn(async (input: RequestInfo | URL) => {
    const url = String(input);
    if (url.endsWith('/protocol/openid-connect/token')) {
      return new Response(JSON.stringify({ access_token: accessToken, id_token: idToken }), { status: 200 });
    }
    if (url.endsWith('/protocol/openid-connect/certs')) {
      return new Response(JSON.stringify({ keys: [publicJwk] }), { status: 200 });
    }
    return new Response(JSON.stringify({ items: [], total: 0, offset: 0, limit: 20 }), { status: 200 });
  });
  vi.stubGlobal('fetch', fetchMock);

  const principal = await handleCallback();
  expect(principal.sub).toBe('user-alan');
  expect(principal.role).toBe('operator');
  expect(getAccessToken()).toBe(accessToken);
  expect(sessionStorage.getItem('__pkce_verifier__')).toBeNull();
});

test('renders dashboard stats and filters reviews by search and severity in ReviewListPage', async () => {
  const fetchMock = vi.fn(async (input: RequestInfo | URL) => {
    const url = String(input);
    if (url.includes('/api/stats')) {
      return new Response(
        JSON.stringify({
          total_reviews: 4,
          total_findings: 7,
          critical_count: 2,
          high_count: 3,
          medium_count: 1,
          low_count: 1,
          languages: { python: 4 },
          eval_runs: 2,
        }),
        { status: 200 },
      );
    }
    return new Response(
      JSON.stringify({
        items: [
          {
            id: 'rev-1',
            title: 'Pickle parser review',
            language: 'python',
            review_type: 'full_file',
            focus_areas: 'security',
            code_snippet: 'pickle.loads(buf)',
            diff_text: null,
            total_findings: 1,
            critical_count: 1,
            high_count: 0,
            medium_count: 0,
            low_count: 0,
            created_at: new Date().toISOString(),
            created_by: 'demo-user',
            advisory_llm_used: 0,
            provider: 'offline-engine',
          },
        ],
        total: 1,
        offset: 0,
        limit: 20,
      }),
      { status: 200 },
    );
  });
  vi.stubGlobal('fetch', fetchMock);

  render(React.createElement(MemoryRouter, null, React.createElement(ReviewListPage)));

  await waitFor(() => {
    expect(screen.getByText('Pickle parser review')).toBeInTheDocument();
  });
  expect(screen.getByText('Total Reviews')).toBeInTheDocument();
  expect(screen.getByText('2 / 3')).toBeInTheDocument();

  const searchInput = screen.getByLabelText('Search reviews');
  fireEvent.change(searchInput, { target: { value: 'pickle' } });

  const severitySelect = screen.getByLabelText('Filter by severity');
  fireEvent.change(severitySelect, { target: { value: 'critical' } });

  await waitFor(() => {
    const urls = fetchMock.mock.calls.map(c => String(c[0]));
    expect(urls.some(u => u.includes('search=pickle') && u.includes('severity=critical'))).toBe(true);
  });
});

