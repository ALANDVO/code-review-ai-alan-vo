/** API types derived from backend response schemas. */

export interface Finding {
  id: string;
  review_id: string;
  line_number: number;
  severity: 'critical' | 'high' | 'medium' | 'low';
  category: 'bug' | 'security' | 'performance' | 'style' | 'maintainability';
  cwe: string | null;
  message: string;
  suggestion: string | null;
  rule_id: string | null;
  advisory_note: string | null;
  created_at: string;
}

export interface Review {
  id: string;
  title: string;
  language: string;
  review_type: string;
  focus_areas: string;
  code_snippet: string;
  diff_text: string | null;
  total_findings: number;
  critical_count: number;
  high_count: number;
  medium_count: number;
  low_count: number;
  created_at: string;
  created_by: string;
  advisory_llm_used: number;
  provider: string;
  findings?: Finding[];
}

export interface ReviewList {
  items: Review[];
  total: number;
  offset: number;
  limit: number;
}

export interface EvalSampleResult {
  sample_id: string;
  description: string;
  expected_rules: string[];
  fired_rules: string[];
  tp: number;
  fp: number;
  fn: number;
  latency_ms: number;
  pass: boolean;
}

export interface EvalDetails {
  samples: EvalSampleResult[];
  pass_rate: number;
  data_provenance: string;
  baseline: string;
  limitations: string;
}

export interface EvalRun {
  id: string;
  trigger: string;
  total_samples: number;
  true_positives: number;
  false_positives: number;
  false_negatives: number;
  precision: number;
  recall: number;
  f1_score: number;
  mean_latency_ms: number;
  status: string;
  details: EvalDetails;
  created_at: string;
  created_by: string;
}

export interface EvalRunList {
  items: EvalRun[];
  total: number;
}

export interface Stats {
  total_reviews: number;
  total_findings: number;
  critical_count: number;
  high_count: number;
  medium_count: number;
  low_count: number;
  languages: Record<string, number>;
  eval_runs: number;
}

export interface HealthStatus {
  status: string;
  version: string;
  demo_mode: boolean;
}

export interface ReviewRequest {
  title: string;
  language: string;
  review_type: string;
  focus_areas: string;
  code_snippet: string;
  diff_text?: string;
  use_llm_advisory: boolean;
}
