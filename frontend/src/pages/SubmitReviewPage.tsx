import { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { reviewsApi } from '@/api/client';
import type { ReviewRequest } from '@/types/api';
import { FindingList } from '@/components/FindingList';
import type { Review } from '@/types/api';

const LANGUAGES = ['python', 'javascript', 'typescript', 'go', 'rust'];
const REVIEW_TYPES = ['full_file', 'diff', 'security_scan'];
const FOCUS_OPTIONS = ['all', 'bug', 'security', 'performance', 'style', 'maintainability'];

export function SubmitReviewPage() {
  const navigate = useNavigate();
  const [form, setForm] = useState<ReviewRequest>({
    title: '',
    language: 'python',
    review_type: 'full_file',
    focus_areas: 'all',
    code_snippet: '',
    use_llm_advisory: false,
  });
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [result, setResult] = useState<Review | null>(null);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError(null);
    setResult(null);
    setLoading(true);
    try {
      const review = await reviewsApi.submit({ ...form, diff_text: form.review_type === 'diff' ? form.code_snippet : undefined });
      setResult(review);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Submission failed');
    } finally {
      setLoading(false);
    }
  };

  const handleExport = () => {
    if (!result) return;
    const json = JSON.stringify(result, null, 2);
    const blob = new Blob([json], { type: 'application/json' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `review-${result.id.slice(0, 8)}.json`;
    a.click();
    URL.revokeObjectURL(url);
  };

  return (
    <div>
      <div className="page-header">
        <h1 className="page-title">Submit Code Review</h1>
        <button className="btn btn-secondary" onClick={() => navigate('/reviews')}>
          View All Reviews
        </button>
      </div>

      <div className="section-gap">
        <div className="card">
          <form onSubmit={handleSubmit}>
            <div className="section-gap">
              <div className="form-group">
                <label className="form-label" htmlFor="review-title">Title</label>
                <input id="review-title"
                  className="form-input"
                  value={form.title}
                  onChange={e => setForm(f => ({ ...f, title: e.target.value }))}
                  placeholder="Describe what you are reviewing..."
                  required
                />
              </div>

              <div className="review-options">
                <div className="form-group">
                  <label className="form-label" htmlFor="review-language">Language</label>
                  <select id="review-language"
                    className="form-select"
                    value={form.language}
                    onChange={e => setForm(f => ({ ...f, language: e.target.value }))}
                  >
                    {LANGUAGES.map(l => <option key={l} value={l}>{l}</option>)}
                  </select>
                </div>

                <div className="form-group">
                  <label className="form-label" htmlFor="review-type">Review Type</label>
                  <select id="review-type"
                    className="form-select"
                    value={form.review_type}
                    onChange={e => setForm(f => ({ ...f, review_type: e.target.value }))}
                  >
                    {REVIEW_TYPES.map(t => <option key={t} value={t}>{t}</option>)}
                  </select>
                </div>

                <div className="form-group">
                  <label className="form-label" htmlFor="review-focus">Focus Areas</label>
                  <select id="review-focus"
                    className="form-select"
                    value={form.focus_areas}
                    onChange={e => setForm(f => ({ ...f, focus_areas: e.target.value }))}
                  >
                    {FOCUS_OPTIONS.map(o => <option key={o} value={o}>{o}</option>)}
                  </select>
                </div>
              </div>

              <div className="form-group">
                <label className="form-label" htmlFor="review-code">Code / Diff</label>
                <textarea id="review-code"
                  className="form-textarea"
                  value={form.code_snippet}
                  onChange={e => setForm(f => ({ ...f, code_snippet: e.target.value }))}
                  placeholder={form.review_type === 'diff'
                    ? 'Paste a unified diff here...'
                    : 'Paste your source code here...'}
                  required
                  style={{ minHeight: 280 }}
                />
              </div>

              <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
                <input
                  type="checkbox"
                  id="llm-advisory"
                  checked={form.use_llm_advisory}
                  onChange={e => setForm(f => ({ ...f, use_llm_advisory: e.target.checked }))}
                />
                <label htmlFor="llm-advisory" style={{ fontSize: 13, cursor: 'pointer' }}>
                  Request LLM advisory notes (requires LLM_API_KEY on server; results are labeled advisory)
                </label>
              </div>

              {error && <div className="alert alert-error">{error}</div>}

              <button className="btn btn-primary" type="submit" disabled={loading}>
                {loading ? <><span className="spinner" style={{ width: 14, height: 14 }} /> Analysing...</> : 'Analyse Code'}
              </button>
            </div>
          </form>
        </div>

        {result && (
          <div className="card">
            <div className="card-header">
              <h2 className="card-title">
                Results — {result.total_findings} finding{result.total_findings !== 1 ? 's' : ''}
              </h2>
              <div style={{ display: 'flex', gap: 8 }}>
                <button className="btn btn-secondary" onClick={handleExport}>Export JSON</button>
                <button className="btn btn-secondary" onClick={() => navigate(`/reviews/${result.id}`)}>
                  View Detail
                </button>
              </div>
            </div>
            <div style={{ display: 'flex', gap: 8, marginBottom: 16, flexWrap: 'wrap' }}>
              {result.critical_count > 0 && <span className="badge badge-critical">{result.critical_count} Critical</span>}
              {result.high_count > 0 && <span className="badge badge-high">{result.high_count} High</span>}
              {result.medium_count > 0 && <span className="badge badge-medium">{result.medium_count} Medium</span>}
              {result.low_count > 0 && <span className="badge badge-low">{result.low_count} Low</span>}
              {result.advisory_llm_used ? (
                <span className="badge" style={{ background: 'rgba(99,102,241,0.15)', color: '#a5b4fc' }}>
                  LLM advisory ({result.provider})
                </span>
              ) : (
                <span className="badge" style={{ background: 'rgba(100,100,100,0.2)', color: 'var(--text-muted)' }}>
                  Offline engine
                </span>
              )}
            </div>
            <FindingList findings={result.findings ?? []} />
          </div>
        )}
      </div>
    </div>
  );
}
