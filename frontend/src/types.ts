export interface Series {
  dates: string[];
  values: number[];
}

export interface Perf {
  annual_return?: number;
  annual_vol?: number;
  sharpe?: number;
  max_drawdown?: number;
  calmar?: number;
  total_return?: number;
  n_periods?: number;
  years?: number;
  model?: string;
  factor?: string;
}

export interface ModelNav {
  nav: Series;
  perf: Perf;
  turnover: { avg?: number; max?: number; n_rebalances?: number; annualized?: number };
}

export interface Meta {
  generated_at?: string;
  data_source?: string;
  start_date?: string;
  end_date?: string;
  universe_size?: number;
  n_factors?: number;
  factor_names?: string[];
  models?: string[];
  top_k?: number;
  rebal_freq?: number;
  cost_bps?: number;
  cost_scenarios_bps?: number[];
  n_folds?: number;
  hpo_trials?: number;
  deep_enabled?: boolean;
}

export interface IcRow {
  factor: string;
  method: string;
  n_periods: number;
  ic_mean: number;
  ic_std: number;
  ir: number;
  ic_pos_ratio: number;
  abs_ic_mean: number;
}

export interface DecayRow {
  lag: number;
  ic_mean: number;
  ir: number;
  n_periods: number;
}

export interface GroupFactor {
  groups: Record<string, Series>;
  long_short: Series;
  ls_stats: Perf;
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
