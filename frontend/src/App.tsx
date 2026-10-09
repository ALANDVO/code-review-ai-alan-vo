import { useEffect, useState } from 'react';
import { NavLink, Navigate, Route, Routes, useNavigate } from 'react-router-dom';
import { healthApi } from './api/client';
import { login, logout, handleCallback } from './auth/oidc';
import { SubmitReviewPage } from './pages/SubmitReviewPage';
import { ReviewListPage } from './pages/ReviewListPage';
import { ReviewDetailPage } from './pages/ReviewDetailPage';
import { EvaluationPage } from './pages/EvaluationPage';

export function App() {
  const [demo, setDemo] = useState(false);
  const [identity, setIdentity] = useState('');
  const [error, setError] = useState('');
  const navigate = useNavigate();
  useEffect(() => {
    healthApi.check().then(h => setDemo(h.demo_mode)).catch(e => setError(String(e)));
    if (window.location.pathname === '/callback') {
      handleCallback().then(user => { setIdentity(user.email || user.sub); navigate('/reviews', { replace: true }); })
        .catch(e => { setError(String(e)); navigate('/', { replace: true }); });
    }
  }, [navigate]);
  return <div className="app-shell"><nav className="nav" aria-label="Main navigation">
    <NavLink className="nav-brand" to="/reviews">Code Review AI</NavLink>
    <div className="nav-links"><NavLink className="nav-link" to="/reviews">Reviews</NavLink>
      <NavLink className="nav-link" to="/submit">Analyze code</NavLink>
      <NavLink className="nav-link" to="/evaluations">Evaluation</NavLink></div>
    <div className="nav-actions">{demo ? <span>Local demo · operator</span> : identity ?
      <><span>{identity}</span><button className="btn btn-secondary" onClick={logout}>Sign out</button></> :
      <button className="btn btn-primary" onClick={() => { void login().catch(e => setError(String(e))); }}>Sign in with SSO</button>}</div>
    </nav><main className="main-content">
    {error && <div role="alert" className="alert alert-error">{error}</div>}
    <Routes><Route path="/reviews" element={<ReviewListPage />} /><Route path="/reviews/:id" element={<ReviewDetailPage />} />
      <Route path="/submit" element={<SubmitReviewPage />} /><Route path="/evaluations" element={<EvaluationPage />} />
      <Route path="/callback" element={<p>Completing sign-in…</p>} /><Route path="*" element={<Navigate to="/reviews" replace />} /></Routes>
    <footer>Alan Vo · <a href="mailto:alanvo@gmail.com">alanvo@gmail.com</a> · Findings require human review.</footer>
    </main></div>;
}
