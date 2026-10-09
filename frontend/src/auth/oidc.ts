/**
 * OIDC / Keycloak PKCE authentication.
 *
 * Architecture: SPA PKCE — access tokens kept in memory only.
 * The temporary verifier and state are stored in sessionStorage
 * ONLY through the redirect round-trip, never access/refresh tokens.
 *
 * Provides:
 *   login()       — initiates PKCE code flow
 *   handleCallback() — exchanges code for token, clears sessionStorage keys
 *   logout()      — clears token from memory and triggers Keycloak logout
 */

import { createRemoteJWKSet, jwtVerify } from 'jose';
import { setAccessToken } from '@/api/client';

const KEYCLOAK_URL = import.meta.env.VITE_KEYCLOAK_URL ?? 'http://127.0.0.1:8080';
const REALM = import.meta.env.VITE_KEYCLOAK_REALM ?? 'code-review-realm';
const CLIENT_ID = import.meta.env.VITE_KEYCLOAK_CLIENT_ID ?? 'code-review-client';
const REDIRECT_URI = `${window.location.origin}/callback`;

// sessionStorage keys — cleared after code exchange, never store tokens here
const SS_CODE_VERIFIER = '__pkce_verifier__';
const SS_STATE = '__pkce_state__';
const SS_NONCE = '__pkce_nonce__';

// ── Crypto helpers ─────────────────────────────────────────────────────────────

function randomBase64Url(length: number): string {
  const arr = crypto.getRandomValues(new Uint8Array(length));
  return btoa(String.fromCharCode(...arr))
    .replace(/\+/g, '-')
    .replace(/\//g, '_')
    .replace(/=/g, '');
}

async function sha256Base64Url(input: string): Promise<string> {
  const encoder = new TextEncoder();
  const data = encoder.encode(input);
  const digest = await crypto.subtle.digest('SHA-256', data);
  const arr = Array.from(new Uint8Array(digest));
  return btoa(String.fromCharCode(...arr))
    .replace(/\+/g, '-')
    .replace(/\//g, '_')
    .replace(/=/g, '');
}

// ── OIDC endpoints ─────────────────────────────────────────────────────────────

const authorizationEndpoint = `${KEYCLOAK_URL}/realms/${REALM}/protocol/openid-connect/auth`;
const tokenEndpoint = `${KEYCLOAK_URL}/realms/${REALM}/protocol/openid-connect/token`;
const logoutEndpoint = `${KEYCLOAK_URL}/realms/${REALM}/protocol/openid-connect/logout`;

// ── Public API ─────────────────────────────────────────────────────────────────

export async function login(): Promise<void> {
  const state = randomBase64Url(16);
  const nonce = randomBase64Url(16);
  const verifier = randomBase64Url(64);
  const challenge = await sha256Base64Url(verifier);

  // Store temporary values for the callback — NOT tokens
  sessionStorage.setItem(SS_STATE, state);
  sessionStorage.setItem(SS_NONCE, nonce);
  sessionStorage.setItem(SS_CODE_VERIFIER, verifier);

  const params = new URLSearchParams({
    response_type: 'code',
    client_id: CLIENT_ID,
    redirect_uri: REDIRECT_URI,
    scope: 'openid email profile',
    state,
    nonce,
    code_challenge: challenge,
    code_challenge_method: 'S256',
  });

  window.location.href = `${authorizationEndpoint}?${params}`;
}

export async function handleCallback(): Promise<{ sub: string; email: string; role: string }> {
  const params = new URLSearchParams(window.location.search);
  const code = params.get('code');
  const returnedState = params.get('state');
  const error = params.get('error');

  if (error) {
    sessionStorage.removeItem(SS_STATE);
    sessionStorage.removeItem(SS_NONCE);
    sessionStorage.removeItem(SS_CODE_VERIFIER);
    throw new Error(`OIDC error: ${error} — ${params.get('error_description') ?? ''}`);
  }

  const savedState = sessionStorage.getItem(SS_STATE);
  const savedNonce = sessionStorage.getItem(SS_NONCE);
  const verifier = sessionStorage.getItem(SS_CODE_VERIFIER);

  // Validate state — CSRF / replay protection
  if (!returnedState || returnedState !== savedState) {
    sessionStorage.removeItem(SS_STATE);
    sessionStorage.removeItem(SS_NONCE);
    sessionStorage.removeItem(SS_CODE_VERIFIER);
    throw new Error('State mismatch — possible CSRF attack. Login aborted.');
  }

  if (!code || !verifier) {
    throw new Error('Missing authorization code or PKCE verifier.');
  }

  // Clear PKCE state from sessionStorage BEFORE token exchange
  sessionStorage.removeItem(SS_STATE);
  sessionStorage.removeItem(SS_NONCE);
  sessionStorage.removeItem(SS_CODE_VERIFIER);

  const body = new URLSearchParams({
    grant_type: 'authorization_code',
    client_id: CLIENT_ID,
    redirect_uri: REDIRECT_URI,
    code,
    code_verifier: verifier,
  });

  const resp = await fetch(tokenEndpoint, {
    method: 'POST',
    headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
    body,
  });

  if (!resp.ok) {
    throw new Error(`Token exchange failed: HTTP ${resp.status}`);
  }

  const tokens = await resp.json() as { access_token: string; id_token: string };

  // Validate nonce in id_token claims
  const { payload: idClaims } = await jwtVerify(tokens.id_token,
    createRemoteJWKSet(new URL(`${KEYCLOAK_URL}/realms/${REALM}/protocol/openid-connect/certs`)),
    { algorithms: ['RS256'], issuer: `${KEYCLOAK_URL}/realms/${REALM}`, audience: CLIENT_ID,
      requiredClaims: ['sub', 'exp', 'iat', 'nonce'] });
  if (idClaims['nonce'] !== savedNonce) {
    throw new Error('Nonce mismatch — replay attack protection triggered.');
  }

  // Store access token in memory only
  setAccessToken(tokens.access_token);

  const [, accessPayload] = tokens.access_token.split('.');
  const claims = JSON.parse(atob(accessPayload.replace(/-/g, '+').replace(/_/g, '/'))) as Record<string, unknown>;
  const realmRoles = ((claims['realm_access'] as { roles?: string[] })?.roles) ?? [];
  const role = realmRoles.includes('admin')
    ? 'admin'
    : realmRoles.includes('operator')
    ? 'operator'
    : 'viewer';

  return {
    sub: String(claims['sub'] ?? ''),
    email: String(claims['email'] ?? ''),
    role,
  };
}

export function logout(): void {
  setAccessToken(null);
  const params = new URLSearchParams({
    client_id: CLIENT_ID,
    post_logout_redirect_uri: window.location.origin,
  });
  window.location.href = `${logoutEndpoint}?${params}`;
}
