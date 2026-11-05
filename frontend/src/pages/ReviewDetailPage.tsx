import { useState, useEffect, useMemo } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { reviewsApi } from '@/api/client';
import type { Review, Finding } from '@/types/api';
import { FindingList } from '@/components/FindingList';

export function ReviewDetailPage() {
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();
  const [review, setReview] = useState<Review | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [showCode, setShowCode] = useState(false);
  const [selectedFinding, setSelectedFinding] = useState<Finding | null>(null);
  const [codeLines, setCodeLines] = useState<string[]>([]);

  useEffect(() => {
    if (!id) return;
    setLoading(true);
    reviewsApi.get(id)
      .then(setReview)
      .catch(err => setError(err instanceof Error ? err.message : 'Failed to load'))
      .finally(() => setLoading(false));
  }, [id]);

  // Parse code into lines for highlighting
  useEffect(() => {
    if (review?.code_snippet) {
      setCodeLines(review.code_snippet.split('\n'));
    }
  }, [review?.code_snippet]);

  const handleFindingClick = (finding: Finding) => {
    setSelectedFinding(finding === selectedFinding ? null : finding);
    if (finding !== selectedFinding) {
      setShowCode(true);
    }
  };

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

  // Highlight the selected finding's line in code
  const highlightedCode = useMemo(() => {
    if (!selectedFinding || codeLines.length === 0) return null;
    const lineIndex = selectedFinding.line_number - 1;
    if (lineIndex < 0 || lineIndex >= codeLines.length) return null;
    return codeLines.map((line, idx) =>
      idx === lineIndex ? <div key={idx} className="highlighted-line">{line}</div> : <div key={idx}>{line}</div>
    );
  }, [selectedFinding, codeLines]);

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
          <FindingList
            findings={review.findings ?? []}
            onFindingClick={handleFindingClick}
            selectedFindingId={selectedFinding?.id}
          />

          {/* Rule details panel for selected finding */}
          {selectedFinding && (
            <div className="rule-details">
              <h3>Rule Details</h3>
              <div className="rule-details-grid">
                <div className="rule-detail-item">
                  <span className="rule-detail-label">Rule ID</span>
                  <span className="rule-detail-value">{selectedFinding.rule_id || 'N/A'}</span>
                </div>
                <div className="rule-detail-item">
                  <span className="rule-detail-label">CWE</span>
                  <span className="rule-detail-value">{selectedFinding.cwe || 'N/A'}</span>
                </div>
                <div className="rule-detail-item">
                  <span className="rule-detail-label">Severity</span>
                  <span className="rule-detail-value">{selectedFinding.severity}</span>
                </div>
                <div className="rule-detail-item">
                  <span className="rule-detail-label">Category</span>
                  <span className="rule-detail-value">{selectedFinding.category}</span>
                </div>
                <div className="rule-detail-item">
                  <span className="rule-detail-label">Line</span>
                  <span className="rule-detail-value">{selectedFinding.line_number}</span>
                </div>
              </div>
              <div style={{ marginTop: 12 }}>
                <span className="rule-detail-label">Message</span>
                <p style={{ margin: '4px 0', fontSize: '13px' }}>{selectedFinding.message}</p>
              </div>
              {selectedFinding.suggestion && (
                <div style={{ marginTop: 8 }}>
                  <span className="rule-detail-label">Suggestion</span>
                  <p style={{ margin: '4px 0', fontSize: '13px' }}>{selectedFinding.suggestion}</p>
                </div>
              )}
            </div>
          )}
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
            <div className="code-block">
              {highlightedCode ? (
                highlightedCode
              ) : (
                review.code_snippet.split('\n').map((line, idx) => <div key={idx}>{line}</div>)
              )}
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
