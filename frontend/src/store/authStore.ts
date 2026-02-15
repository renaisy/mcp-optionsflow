/**
 * Auth store - manages authentication state
 */
import { create } from 'zustand';
import { persist } from 'zustand/middleware';
import type { User, AuthTokens } from '../types';
import { authAPI } from '../services/api';

interface AuthState {
  user: User | null;
  accessToken: string | null;
  refreshToken: string | null;
  isAuthenticated: boolean;
  
  // Actions
  setUser: (user: User | null) => void;
  setTokens: (tokens: AuthTokens) => void;
  login: (username: string, password: string) => Promise<void>;
  register: (username: string, email: string, password: string) => Promise<void>;
  logout: () => void;
  loadUser: () => Promise<void>;
}

export const useAuthStore = create<AuthState>()(
  persist(
    (set, get) => ({
      user: null,
      accessToken: null,
      refreshToken: null,
      isAuthenticated: false,
      
      setUser: (user) => set({ user, isAuthenticated: !!user }),
      
      setTokens: (tokens) => {
        localStorage.setItem('access_token', tokens.access_token);
        localStorage.setItem('refresh_token', tokens.refresh_token);
        set({
          accessToken: tokens.access_token,
          refreshToken: tokens.refresh_token,
          isAuthenticated: true,
        });
      },
      
      login: async (username, password) => {
        try {
          const response = await authAPI.login({ username, password });
          const tokens = response.data;
          get().setTokens(tokens);
          
          // Load user data
          await get().loadUser();
        } catch (error) {
          console.error('Login error:', error);
          throw error;
        }
      },
      
      register: async (username, email, password) => {
        try {
          await authAPI.register({ username, email, password });
          // Auto login after registration
          await get().login(username, password);
        } catch (error) {
          console.error('Registration error:', error);
          throw error;
        }
      },
      
      logout: () => {
        localStorage.removeItem('access_token');
        localStorage.removeItem('refresh_token');
        set({
          user: null,
          accessToken: null,
          refreshToken: null,
          isAuthenticated: false,
        });
      },
      
      loadUser: async () => {
        try {
          const response = await authAPI.getMe();
          set({ user: response.data, isAuthenticated: true });
        } catch (error) {
          console.error('Load user error:', error);
          get().logout();
        }
      },
    }),
    {
      name: 'auth-storage',
      partialize: (state) => ({
        accessToken: state.accessToken,
        refreshToken: state.refreshToken,
      }),
    }
  )
);
