import { useState, useEffect, useCallback } from 'react';
import { useNavigate } from 'react-router-dom';
import { reviewsApi, statsApi } from '@/api/client';
import type { Review, ReviewList, Stats } from '@/types/api';

const LANGUAGES = ['', 'python', 'javascript', 'typescript', 'go', 'rust'];
const SEVERITIES = ['', 'critical', 'high', 'medium', 'low'];
const PAGE_SIZE = 20;

export function ReviewListPage() {
  const navigate = useNavigate();
  const [data, setData] = useState<ReviewList | null>(null);
  const [stats, setStats] = useState<Stats | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [offset, setOffset] = useState(0);
  const [language, setLanguage] = useState('');
  const [severity, setSeverity] = useState('');
  const [search, setSearch] = useState('');
  const [deleting, setDeleting] = useState<string | null>(null);

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const [result, summary] = await Promise.all([
        reviewsApi.list({
          limit: PAGE_SIZE,
          offset,
          language: language || undefined,
          severity: severity || undefined,
          search: search.trim() || undefined,
        }),
        statsApi.get().catch(() => null),
      ]);
      setData(result);
      if (summary) setStats(summary);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to load reviews');
    } finally {
      setLoading(false);
    }
  }, [offset, language, severity, search]);

  useEffect(() => {
    void load();
  }, [load]);

  const handleDelete = async (e: React.MouseEvent, id: string) => {
    e.stopPropagation();
    if (!confirm('Delete this review?')) return;
    setDeleting(id);
    try {
      await reviewsApi.delete(id);
      await load();
    } catch (err) {
      alert(err instanceof Error ? err.message : 'Delete failed');
    } finally {
      setDeleting(null);
    }
  };

  return (
    <div>
      <div className="page-header">
        <h1 className="page-title">Review History</h1>
        <button className="btn btn-primary" onClick={() => navigate('/submit')}>
          + New Review
        </button>
      </div>

      {stats && (
        <div
          className="stats-grid"
          style={{
            display: 'grid',
            gridTemplateColumns: 'repeat(auto-fit, minmax(160px, 1fr))',
            gap: 12,
            marginBottom: 16,
          }}
        >
          <div className="card" style={{ padding: 14 }}>
            <div className="stat-label">Total Reviews</div>
            <div style={{ fontSize: 22, fontWeight: 700 }}>{stats.total_reviews}</div>
          </div>
          <div className="card" style={{ padding: 14 }}>
            <div className="stat-label">Total Findings</div>
            <div style={{ fontSize: 22, fontWeight: 700 }}>{stats.total_findings}</div>
          </div>
          <div className="card" style={{ padding: 14 }}>
            <div className="stat-label">Critical / High</div>
            <div style={{ fontSize: 22, fontWeight: 700 }}>
              {stats.critical_count} / {stats.high_count}
            </div>
          </div>
          <div className="card" style={{ padding: 14 }}>
            <div className="stat-label">Benchmark Runs</div>
            <div style={{ fontSize: 22, fontWeight: 700 }}>{stats.eval_runs}</div>
          </div>
        </div>
      )}

      <div className="card">
        <div style={{ display: 'flex', gap: 12, marginBottom: 16, alignItems: 'center', flexWrap: 'wrap' }}>
          <div className="form-group" style={{ flex: '1 1 200px' }}>
            <input
              aria-label="Search reviews"
              className="form-input"
              placeholder="Search title or code..."
              value={search}
              onChange={e => { setSearch(e.target.value); setOffset(0); }}
            />
          </div>
          <div className="form-group" style={{ flex: '0 0 auto' }}>
            <select
              aria-label="Filter by language"
              className="form-select"
              value={language}
              onChange={e => { setLanguage(e.target.value); setOffset(0); }}
              style={{ width: 150 }}
            >
              <option value="">All Languages</option>
              {LANGUAGES.filter(Boolean).map(l => <option key={l} value={l}>{l}</option>)}
            </select>
          </div>
          <div className="form-group" style={{ flex: '0 0 auto' }}>
            <select
              aria-label="Filter by severity"
              className="form-select"
              value={severity}
              onChange={e => { setSeverity(e.target.value); setOffset(0); }}
              style={{ width: 150 }}
            >
              <option value="">All Severities</option>
              {SEVERITIES.filter(Boolean).map(s => <option key={s} value={s}>{s}</option>)}
            </select>
          </div>
          <button className="btn btn-secondary" onClick={load}>Refresh</button>
          {data && <span style={{ color: 'var(--text-muted)', fontSize: 12 }}>{data.total} total</span>}
        </div>

        {loading && (
          <div className="state-loading">
            <div className="spinner" />
            <p>Loading reviews...</p>
          </div>
        )}

        {error && <div className="alert alert-error">{error}</div>}

        {!loading && !error && data && data.items.length === 0 && (
          <div className="state-empty">
            <div className="icon">📋</div>
            <p>No reviews yet.</p>
            <button className="btn btn-primary" onClick={() => navigate('/submit')}>Submit your first review</button>
          </div>
        )}

        {!loading && data && data.items.length > 0 && (
          <div className="table-wrap">
            <table>
              <thead>
                <tr>
                  <th>Title</th>
                  <th>Language</th>
                  <th>Type</th>
                  <th>Findings</th>
                  <th>Severity</th>
                  <th>Provider</th>
                  <th>Date</th>
                  <th></th>
                </tr>
              </thead>
              <tbody>
                {data.items.map((r: Review) => (
                  <tr key={r.id} onClick={() => navigate(`/reviews/${r.id}`)}>
                    <td>{r.title}</td>
                    <td><span className="badge badge-low">{r.language}</span></td>
                    <td style={{ color: 'var(--text-muted)' }}>{r.review_type}</td>
                    <td>
                      {r.total_findings === 0
                        ? <span style={{ color: 'var(--success)' }}>✓ Clean</span>
                        : <strong>{r.total_findings}</strong>}
                    </td>
                    <td>
                      <div style={{ display: 'flex', gap: 4 }}>
                        {r.critical_count > 0 && <span className="badge badge-critical">{r.critical_count}</span>}
                        {r.high_count > 0 && <span className="badge badge-high">{r.high_count}</span>}
                        {r.medium_count > 0 && <span className="badge badge-medium">{r.medium_count}</span>}
                        {r.low_count > 0 && <span className="badge badge-low">{r.low_count}</span>}
                      </div>
                    </td>
                    <td style={{ color: 'var(--text-muted)', fontSize: 11 }}>{r.provider}</td>
                    <td style={{ color: 'var(--text-muted)', fontSize: 11 }}>
                      {new Date(r.created_at).toLocaleDateString()}
                    </td>
                    <td>
                      <button
                        className="btn btn-danger"
                        style={{ padding: '4px 8px', fontSize: 11 }}
                        onClick={e => handleDelete(e, r.id)}
                        disabled={deleting === r.id}
                      >
                        Delete
                      </button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}

        {data && data.total > PAGE_SIZE && (
          <div className="pagination">
            <button
              className="btn btn-secondary"
              disabled={offset === 0}
              onClick={() => setOffset(Math.max(0, offset - PAGE_SIZE))}
            >
              Previous
            </button>
            <span style={{ fontSize: 12, color: 'var(--text-muted)' }}>
              {offset + 1}–{Math.min(offset + PAGE_SIZE, data.total)} of {data.total}
            </span>
            <button
              className="btn btn-secondary"
              disabled={offset + PAGE_SIZE >= data.total}
              onClick={() => setOffset(offset + PAGE_SIZE)}
            >
              Next
            </button>
          </div>
        )}
      </div>
    </div>
  );
}
