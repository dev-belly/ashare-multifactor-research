export interface Series {
  dates: string[];
  values: number[];
}

export interface Perf {
  annual_return?: number | null;
  annual_vol?: number | null;
  sharpe?: number | null;
  max_drawdown?: number | null;
  calmar?: number | null;
  total_return?: number | null;
  n_periods?: number;
  years?: number;
  model?: string;
  factor?: string;
}

export interface ModelNav {
  nav?: Partial<Series>;
  perf?: Perf;
  turnover?: { avg?: number; max?: number; n_rebalances?: number; annualized?: number };
}

export interface OosFoldCoverage {
  fold_id: number;
  status: "success" | "failed";
  reason?: string;
  error?: string;
  expected_oos_date_count: number;
  scored_oos_date_count: number;
  oos_date_coverage_ratio: number;
}

export interface ModelOosCoverage {
  requested_fold_count: number;
  successful_fold_count: number;
  failed_fold_count: number;
  successful_fold_ids: number[];
  failed_fold_ids: number[];
  expected_oos_date_count: number;
  scored_oos_date_count: number;
  oos_date_coverage_ratio: number;
  expected_oos_start?: string | null;
  expected_oos_end?: string | null;
  scored_oos_start?: string | null;
  scored_oos_end?: string | null;
  backtest_return_start?: string;
  backtest_return_end?: string;
  post_last_score_return_date_count?: number;
  folds: OosFoldCoverage[];
}

export interface Meta {
  generated_at?: string;
  data_source?: string;
  requested_data_source?: string;
  actual_data_source?: string;
  fallback_reason?: string | null;
  start_date?: string;
  end_date?: string;
  universe_size?: number;
  n_factors?: number;
  factor_names?: string[];
  models?: string[];
  top_k?: number;
  max_weight_per_stock?: number;
  portfolio_cash_policy?: string;
  rebal_freq?: number;
  cost_bps?: number;
  cost_scenarios_bps?: number[];
  n_folds?: number;
  model_oos_coverage?: Record<string, ModelOosCoverage>;
  label_horizon_days?: number;
  execution_lag_days?: number;
  hpo_trials?: number;
  deep_enabled?: boolean;
}

export interface IcRow {
  factor: string;
  method: string;
  n_periods: number;
  ic_mean: number | null;
  ic_std: number | null;
  ir: number | null;
  ic_pos_ratio: number | null;
  abs_ic_mean: number | null;
}

export interface DecayRow {
  lag: number;
  ic_mean: number | null;
  ir: number | null;
  n_periods: number;
}

export interface GroupFactor {
  groups?: Record<string, Partial<Series>>;
  long_short?: Partial<Series>;
  ls_stats?: Perf;
}

export interface RobustRegime {
  bull?: Perf;
  neutral?: Perf;
  bear?: Perf;
}

export interface Results {
  meta: Meta;
  model_nav: Record<string, ModelNav>;
  cost_scenarios: Record<string, Record<string, Perf>>;
  ic_summary: IcRow[];
  group_returns: Record<string, GroupFactor>;
  factor_decay: Record<string, DecayRow[]>;
  robustness: Record<string, RobustRegime>;
  feature_importance: Record<string, { factor: string; importance: number }[]>;
}
