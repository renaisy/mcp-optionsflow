/**
 * API service configuration
 */
import axios from 'axios';

const API_BASE_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000/api/v1';

const api = axios.create({
  baseURL: API_BASE_URL,
  headers: {
    'Content-Type': 'application/json',
  },
});

// Request interceptor to add auth token
api.interceptors.request.use(
  (config) => {
    const token = localStorage.getItem('access_token');
    if (token) {
      config.headers.Authorization = `Bearer ${token}`;
    }
    return config;
  },
  (error) => {
    return Promise.reject(error);
  }
);

// Response interceptor to handle token refresh
api.interceptors.response.use(
  (response) => response,
  async (error) => {
    const originalRequest = error.config;
    
    // If error is 401 and we haven't tried refreshing yet
    if (error.response?.status === 401 && !originalRequest._retry) {
      originalRequest._retry = true;
      
      try {
        const refreshToken = localStorage.getItem('refresh_token');
        if (refreshToken) {
          const response = await axios.post(`${API_BASE_URL}/auth/refresh`, null, {
            headers: { Authorization: `Bearer ${refreshToken}` },
          });
          
          const { access_token, refresh_token } = response.data;
          localStorage.setItem('access_token', access_token);
          localStorage.setItem('refresh_token', refresh_token);
          
          // Retry original request with new token
          originalRequest.headers.Authorization = `Bearer ${access_token}`;
          return api(originalRequest);
        }
      } catch (refreshError) {
        // Refresh failed, clear tokens and redirect to login
        localStorage.removeItem('access_token');
        localStorage.removeItem('refresh_token');
        window.location.href = '/login';
      }
    }
    
    return Promise.reject(error);
  }
);

export default api;

/**
 * Auth API
 */
export const authAPI = {
  register: (data: { username: string; email: string; password: string }) =>
    api.post('/auth/register', data),
  
  login: (data: { username: string; password: string }) =>
    api.post('/auth/login', data),
  
  refresh: () => {
    const refreshToken = localStorage.getItem('refresh_token');
    return api.post('/auth/refresh', null, {
      headers: { Authorization: `Bearer ${refreshToken}` },
    });
  },
  
  getMe: () => api.get('/auth/me'),
};

/**
 * Options API
 */
export const optionsAPI = {
  getStockInfo: (symbol: string) => api.get(`/options/stock/${symbol}`),
  
  getExpirationDates: (symbol: string) => api.get(`/options/expirations/${symbol}`),
  
  getOptionChain: (symbol: string, expirationDate?: string, optionType?: string) =>
    api.get(`/options/chain/${symbol}`, {
      params: { expiration_date: expirationDate, option_type: optionType },
    }),

  getOptionChainWithGreeks: (symbol: string, expirationDate?: string, optionType?: string) =>
    api.get(`/options/chain/${symbol}/greeks`, {
      params: { expiration_date: expirationDate, option_type: optionType },
    }),
  
  getFilteredOptions: (data: {
    symbol: string;
    expiration_date?: string;
    option_type: 'call' | 'put';
    min_volume?: number;
    min_open_interest?: number;
    min_delta?: number;
    max_delta?: number;
    strike_min?: number;
    strike_max?: number;
  }) => api.post('/options/filtered', data),
  
  getRiskFreeRate: (market?: 'us' | 'cn') =>
    api.get('/options/rate', { params: market ? { market } : undefined }),

  getSourcesStatus: () => api.get('/options/sources-status'),
};

/**
 * Strategies API
 */
export const strategiesAPI = {
  analyzeStrategy: (data: {
    symbol: string;
    strategy_type: 'ccs' | 'pcs' | 'csp' | 'cc';
    expiration_date?: string;
    delta_target?: number;
    width_pct?: number;
    save_result?: boolean;
  }) => api.post('/strategies/analyze', data),
  
  compareStrategies: (data: {
    symbol: string;
    strategies: Array<{
      strategy_type: 'ccs' | 'pcs' | 'csp' | 'cc';
      expiration_date?: string;
      delta_target?: number;
      width_pct?: number;
    }>;
    save_results?: boolean;
  }) => api.post('/strategies/compare', data),
  
  getHistory: (params?: {
    limit?: number;
    symbol?: string;
    strategy_type?: string;
    expiration_date?: string;
    date_from?: string;
    date_to?: string;
  }) => api.get('/strategies/history', { params }),

  getHistoryFilterOptions: () =>
    api.get('/strategies/history/filter-options'),
  
  getAnalysisDetail: (analysisId: number) =>
    api.get(`/strategies/history/${analysisId}`),
  
  deleteAnalysis: (analysisId: number) =>
    api.delete(`/strategies/history/${analysisId}`),
  
  analyzePnlScenarios: (data: {
    symbol: string;
    strategy: 'ccs' | 'pcs' | 'csp' | 'cc';
    expiration_date: string;
    price_range_pct?: number;
    steps?: number;
  }) => api.post('/strategies/pnl-scenarios', data),
  
  findBestStrategies: (data: {
    symbol: string;
    expiration_date?: string;
    min_probability_profit?: number;
    max_risk_reward_ratio?: number;
    strategy_preference?: 'bullish' | 'bearish' | 'neutral' | 'any';
  }) => api.post('/strategies/find-best', data),
};

/**
 * Agent API
 */
export interface AgentModel {
  id: string;
  name: string;
  status: 'available' | 'unavailable' | 'unknown' | 'running';
  provider: string;
  is_current?: boolean;
  note?: string;
}

export const agentAPI = {
  getConfig: () => api.get('/agent/config'),
  getModels: () => api.get<AgentModel[]>('/agent/models'),
  putConfig: (data: {
    provider: string;
    api_key?: string;
    base_url?: string;
    model: string;
    enabled?: boolean;
  }) => api.put('/agent/config', data),
  chatStream: (
    messages: Array<{ role: string; content: string }>,
    onEvent: (event: { type: string; content?: string; tool?: string; data?: unknown; message?: string }) => void,
    options?: { model?: string }
  ) => {
    const token = localStorage.getItem('access_token');
    const url = (import.meta.env.VITE_API_URL || 'http://localhost:8000/api/v1') + '/agent/chat';
    const body: { messages: Array<{ role: string; content: string }>; model?: string } = { messages };
    if (options?.model) body.model = options.model;
    return fetch(url, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        ...(token ? { Authorization: `Bearer ${token}` } : {}),
      },
      body: JSON.stringify(body),
    }).then(async (res) => {
      if (!res.ok) {
        const err = await res.json().catch(() => ({}));
        throw new Error(err.detail || res.statusText);
      }
      const reader = res.body?.getReader();
      if (!reader) throw new Error('No response body');
      const decoder = new TextDecoder();
      let buffer = '';
      while (true) {
        const { done, value } = await reader.read();
        if (done) break;
        buffer += decoder.decode(value, { stream: true });
        const lines = buffer.split('\n');
        buffer = lines.pop() || '';
        for (const line of lines) {
          if (line.startsWith('data: ')) {
            try {
              const obj = JSON.parse(line.slice(6));
              onEvent(obj);
            } catch {
              // ignore parse errors
            }
          }
        }
      }
      if (buffer.startsWith('data: ')) {
        try {
          const obj = JSON.parse(buffer.slice(6));
          onEvent(obj);
        } catch {
          // ignore
        }
      }
      onEvent({ type: 'done' });
    });
  },
};
