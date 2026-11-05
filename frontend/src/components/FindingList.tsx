import { useState, useMemo } from 'react';
import type { Finding } from '@/types/api';

interface FindingListProps {
  findings: Finding[];
  onFindingClick?: (finding: Finding) => void;
  selectedFindingId?: string;
}

const ICONS: Record<string, string> = {
  critical: '🔴',
  high: '🟠',
  medium: '🟡',
  low: '🔵',
};

const SEVERITY_ORDER: Record<string, number> = { critical: 0, high: 1, medium: 2, low: 3 };
const CATEGORIES = ['bug', 'security', 'performance', 'style', 'maintainability'] as const;
const SEVERITIES = ['critical', 'high', 'medium', 'low'] as const;

export function FindingList({ findings, onFindingClick, selectedFindingId }: FindingListProps) {
  const [severityFilter, setSeverityFilter] = useState<string>('all');
  const [categoryFilter, setCategoryFilter] = useState<string>('all');

  const filteredFindings = useMemo(() => {
    return findings.filter(f => {
      if (severityFilter !== 'all' && f.severity !== severityFilter) return false;
      if (categoryFilter !== 'all' && f.category !== categoryFilter) return false;
      return true;
    });
  }, [findings, severityFilter, categoryFilter]);

  const sortedFindings = useMemo(() => {
    return [...filteredFindings].sort((a, b) => {
      return (SEVERITY_ORDER[a.severity] ?? 4) - (SEVERITY_ORDER[b.severity] ?? 4) || a.line_number - b.line_number;
    });
  }, [filteredFindings]);

  if (sortedFindings.length === 0 && findings.length > 0) {
    return (
      <div className="state-empty">
        <div className="icon">🔍</div>
        <p>No findings match the current filters.</p>
      </div>
    );
  }

  if (sortedFindings.length === 0) {
    return (
      <div className="state-empty">
        <div className="icon">✅</div>
        <p>No findings — code looks clean.</p>
      </div>
    );
  }

  return (
    <div>
      <div className="finding-filters">
        <div className="filter-group">
          <label htmlFor="severity-filter" style={{ fontSize: 12, color: 'var(--text-muted)' }}>Severity</label>
          <select
            id="severity-filter"
            value={severityFilter}
            onChange={e => setSeverityFilter(e.target.value)}
            className="filter-select"
          >
            <option value="all">All</option>
            {SEVERITIES.map(s => (
              <option key={s} value={s}>{s.charAt(0).toUpperCase() + s.slice(1)}</option>
            ))}
          </select>
        </div>
        <div className="filter-group">
          <label htmlFor="category-filter" style={{ fontSize: 12, color: 'var(--text-muted)' }}>Category</label>
          <select
            id="category-filter"
            value={categoryFilter}
            onChange={e => setCategoryFilter(e.target.value)}
            className="filter-select"
          >
            <option value="all">All</option>
            {CATEGORIES.map(c => (
              <option key={c} value={c}>{c.charAt(0).toUpperCase() + c.slice(1)}</option>
            ))}
          </select>
        </div>
      </div>
      <div className="finding-list">
        {sortedFindings.map((f) => (
          <div
            key={f.id}
            className={`finding-row ${f.id === selectedFindingId ? 'selected' : ''}`}
            onClick={() => onFindingClick?.(f)}
            style={{ cursor: onFindingClick ? 'pointer' : 'default' }}
          >
            <div className="finding-header">
              <span>{ICONS[f.severity] ?? '⚪'}</span>
              <span className={`badge badge-${f.severity}`}>{f.severity}</span>
              <span className={`badge badge-${f.category === 'security' ? 'critical' : 'low'}`} style={{ textTransform: 'none', fontSize: '11px' }}>
                {f.category}
              </span>
              <span style={{ fontSize: '12px', color: 'var(--text-muted)' }}>L{f.line_number}</span>
              {f.rule_id && (
                <span style={{ fontSize: '11px', fontFamily: 'monospace', color: 'var(--text-muted)' }}>
                  [{f.rule_id}]
                </span>
              )}
              {f.cwe && <span className="finding-cwe">{f.cwe}</span>}
            </div>
            <div className="finding-message">{f.message}</div>
            {f.suggestion && (
              <div className="finding-suggestion">→ {f.suggestion}</div>
            )}
            {f.advisory_note && (
              <div style={{ marginTop: 6, padding: '8px', background: 'rgba(99,102,241,0.1)', borderRadius: 4, fontSize: 12, color: '#a5b4fc' }}>
                <strong>Advisory:</strong> {f.advisory_note}
              </div>
            )}
          </div>
        ))}
      </div>
    </div>
  );
}
