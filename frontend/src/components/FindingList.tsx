import type { Finding } from '@/types/api';

interface FindingListProps {
  findings: Finding[];
}

const ICONS: Record<string, string> = {
  critical: '🔴',
  high: '🟠',
  medium: '🟡',
  low: '🔵',
};

export function FindingList({ findings }: FindingListProps) {
  if (findings.length === 0) {
    return (
      <div className="state-empty">
        <div className="icon">✅</div>
        <p>No findings — code looks clean.</p>
      </div>
    );
  }

  const sorted = [...findings].sort((a, b) => {
    const order: Record<string, number> = { critical: 0, high: 1, medium: 2, low: 3 };
    return (order[a.severity] ?? 4) - (order[b.severity] ?? 4) || a.line_number - b.line_number;
  });

  return (
    <div>
      {sorted.map((f) => (
        <div key={f.id} className="finding-row">
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
  );
}
