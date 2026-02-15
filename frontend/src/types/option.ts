/**
 * Option types
 */
export interface OptionData {
  contractSymbol: string;
  strike: number;
  lastPrice?: number;
  bid?: number;
  ask?: number;
  change?: number;
  percentChange?: number;
  volume?: number;
  openInterest?: number;
  impliedVolatility?: number;
  inTheMoney?: boolean;
  contractSize?: string;
  expiration?: string;
  lastTradeDate?: string;
  option_type?: 'call' | 'put';
  underlying_price?: number;
  delta?: number;
  gamma?: number;
  theta?: number;
  vega?: number;
  rho?: number;
}

export interface OptionChain {
  symbol: string;
  expiration_date: string;
  underlying_price?: number;
  calls: OptionData[];
  puts: OptionData[];
  timestamp: string;
}

export interface StockInfo {
  symbol: string;
  currentPrice?: number;
  previousClose?: number;
  open?: number;
  dayHigh?: number;
  dayLow?: number;
  volume?: number;
  marketCap?: number;
  dividendYield?: number;
  fiftyTwoWeekHigh?: number;
  fiftyTwoWeekLow?: number;
  companyName?: string;
}

export interface ExpirationDates {
  symbol: string;
  expiration_dates: string[];
}
