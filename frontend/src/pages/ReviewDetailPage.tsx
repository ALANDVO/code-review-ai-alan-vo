import { useState, useEffect } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { reviewsApi } from '@/api/client';
import type { Review } from '@/types/api';
import { FindingList } from '@/components/FindingList';

export function ReviewDetailPage() {
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();
  const [review, setReview] = useState<Review | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [showCode, setShowCode] = useState(false);

  useEffect(() => {
    if (!id) return;
    setLoading(true);
    reviewsApi.get(id)
      .then(setReview)
      .catch(err => setError(err instanceof Error ? err.message : 'Failed to load'))
      .finally(() => setLoading(false));
  }, [id]);

  const handleExport = () => {
    if (!review) return;
    const json = JSON.stringify(review, null, 2);
    const blob = new Blob([json], { type: 'application/json' });
    const a = document.createElement('a');
    a.href = URL.createObjectURL(blob);
    a.download = `review-${review.id.slice(0, 8)}.json`;
    a.click();
  };

  const handleDelete = async () => {
    if (!review || !confirm('Delete this review permanently?')) return;
    try {
      await reviewsApi.delete(review.id);
      navigate('/reviews');
    } catch (err) {
      alert(err instanceof Error ? err.message : 'Delete failed');
    }
  };

  if (loading) {
    return (
      <div className="state-loading">
        <div className="spinner" />
        <p>Loading review...</p>
      </div>
    );
  }

  if (error) {
    return <div className="alert alert-error" style={{ marginTop: 24 }}>{error}</div>;
  }

  if (!review) return null;

  return (
    <div>
      <div className="page-header">
        <div>
          <button
            style={{ background: 'none', border: 'none', color: 'var(--text-muted)', cursor: 'pointer', marginBottom: 8, fontSize: 13 }}
            onClick={() => navigate('/reviews')}
          >
            ← Back to reviews
          </button>
          <h1 className="page-title">{review.title}</h1>
        </div>
        <div style={{ display: 'flex', gap: 8 }}>
          <button className="btn btn-secondary" onClick={handleExport}>Export JSON</button>
          <button className="btn btn-danger" onClick={handleDelete}>Delete</button>
        </div>
      </div>

      <div className="section-gap">
        {/* Metadata card */}
        <div className="card">
          <div style={{ display: 'flex', gap: 24, flexWrap: 'wrap' }}>
            <div>
              <div className="stat-label">Language</div>
              <span className="badge badge-low">{review.language}</span>
            </div>
            <div>
              <div className="stat-label">Type</div>
              <span style={{ fontSize: 13 }}>{review.review_type}</span>
            </div>
            <div>
              <div className="stat-label">Focus</div>
              <span style={{ fontSize: 13 }}>{review.focus_areas}</span>
            </div>
            <div>
              <div className="stat-label">Provider</div>
              <span style={{ fontSize: 13 }}>{review.provider}</span>
            </div>
            <div>
              <div className="stat-label">Submitted</div>
              <span style={{ fontSize: 13 }}>{new Date(review.created_at).toLocaleString()}</span>
            </div>
          </div>

          <div style={{ display: 'flex', gap: 8, marginTop: 16, flexWrap: 'wrap' }}>
            {review.critical_count > 0 && <span className="badge badge-critical">{review.critical_count} Critical</span>}
            {review.high_count > 0 && <span className="badge badge-high">{review.high_count} High</span>}
            {review.medium_count > 0 && <span className="badge badge-medium">{review.medium_count} Medium</span>}
            {review.low_count > 0 && <span className="badge badge-low">{review.low_count} Low</span>}
            {review.total_findings === 0 && <span className="badge badge-success">Clean</span>}
          </div>
        </div>

        {/* Findings */}
        <div className="card">
          <div className="card-header">
            <h2 className="card-title">
              Findings ({review.findings?.length ?? review.total_findings})
            </h2>
          </div>
          <FindingList findings={review.findings ?? []} />
        </div>

        {/* Code view */}
        <div className="card">
          <div className="card-header">
            <h2 className="card-title">Source</h2>
            <button className="btn btn-secondary" onClick={() => setShowCode(!showCode)}>
              {showCode ? 'Hide' : 'Show'} Code
            </button>
          </div>
          {showCode && (
            <div className="code-block">{review.code_snippet}</div>
          )}
        </div>
      </div>
    </div>
  );
}
