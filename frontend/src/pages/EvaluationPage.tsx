import { useEffect, useState } from 'react';
import { evalsApi } from '../api/client';
import type { EvalRun } from '../types/api';
export function EvaluationPage() {
  const [runs, setRuns] = useState<EvalRun[]>([]);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  const load = () => evalsApi.list().then(result => setRuns(result.items)).catch(e => setError(String(e)));
  useEffect(() => { void load(); }, []);
  async function run() {
    setBusy(true); setError('');
    try { await evalsApi.trigger(); await load(); } catch (e) { setError(String(e)); } finally { setBusy(false); }
  }
  return <section><div className="page-header"><h1>Rule evaluation</h1>
    <button className="btn btn-primary" disabled={busy} onClick={run}>{busy ? 'Evaluating…' : 'Run benchmark (admin)'}</button></div>
    <p>Curated synthetic cases measure rule behavior. These scores do not estimate production defect coverage. No external LLM calls are made.</p>
    {error && <p role="alert" className="alert alert-error">{error}</p>}
    {!runs.length && <p>No saved evaluations yet. An administrator can run the benchmark; local users can also use the documented command.</p>}
    {runs.map(run => <article className="card" key={run.id}><h2>{new Date(run.created_at).toLocaleString()}</h2>
      <p>Precision {(run.precision * 100).toFixed(1)}% · Recall {(run.recall * 100).toFixed(1)}% · F1 {run.f1_score.toFixed(3)}</p>
      <p>{run.total_samples} cases · TP {run.true_positives} · FP {run.false_positives} · FN {run.false_negatives}</p>
      <details><summary>Evidence and limitations</summary><p>{run.details.data_provenance}</p><p>{run.details.baseline}</p><p>{run.details.limitations}</p>
        <div className="table-wrap"><table><thead><tr><th>Case</th><th>Expected rules</th><th>Detected rules</th><th>Result</th></tr></thead><tbody>
          {run.details.samples.map(sample => <tr key={sample.sample_id}><td>{sample.description}</td><td>{sample.expected_rules.join(', ') || 'None'}</td>
            <td>{sample.fired_rules.join(', ') || 'None'}</td><td>{sample.pass ? 'Pass' : 'Mismatch'}</td></tr>)}
        </tbody></table></div></details></article>)}
  </section>;
}
