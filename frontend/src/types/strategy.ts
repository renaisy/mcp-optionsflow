/**
 * Strategy types
 */
export interface StrategyAnalysisResult {
  symbol: string;
  strategy_type: 'ccs' | 'pcs' | 'csp' | 'cc';
  expiration_date?: string;
  current_price?: number;
  timestamp: string;
  short_strike?: number;
  long_strike?: number;
  premium?: number;
  max_profit?: number;
  max_loss?: number;
  breakeven?: number;
  probability_of_profit?: number;
  delta?: number;
  gamma?: number;
  theta?: number;
  vega?: number;
  rho?: number;
  days_to_expiration?: number;
  implied_volatility?: number;
  full_analysis?: Record<string, unknown>;
  analysis_id?: number;
}

export interface StrategyAnalysisRequest {
  symbol: string;
  strategy_type: 'ccs' | 'pcs' | 'csp' | 'cc';
  expiration_date?: string;
  delta_target?: number;
  width_pct?: number;
  save_result?: boolean;
}

export interface MultiStrategyRequest {
  symbol: string;
  strategies: StrategyAnalysisRequest[];
  save_results?: boolean;
}

export interface StrategyComparison {
  symbol: string;
  strategies: StrategyAnalysisResult[];
  timestamp: string;
}

export interface AnalysisHistory {
  id: number;
  symbol: string;
  strategy_type: string;
  expiration_date: string;
  current_price: number;
  created_at: string;
  analysis_result: StrategyAnalysisResult;
}
