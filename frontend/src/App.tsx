/**
 * Main App component with routing
 */
import React, { useEffect } from 'react';
import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom';
import { Layout } from './components/layout';
import { Dashboard, Login, OptionsChain, StrategyAnalysis, AgentChat, History, GreeksVisualizer, Settings } from './pages';
import { useAuthStore } from './store';

// Protected Route component
const ProtectedRoute: React.FC<{ children: React.ReactElement }> = ({ children }) => {
  const { isAuthenticated } = useAuthStore();
  
  if (!isAuthenticated) {
    return <Navigate to="/login" replace />;
  }
  
  return children;
};

function App() {
  const { isAuthenticated, loadUser, accessToken } = useAuthStore();

  useEffect(() => {
    // Load user data if token exists
    if (accessToken && !isAuthenticated) {
      loadUser();
    }
  }, [accessToken, isAuthenticated, loadUser]);

  return (
    <BrowserRouter>
      <Routes>
        {/* Public routes */}
        <Route path="/login" element={<Login />} />
        
        {/* Protected routes */}
        <Route
          path="/"
          element={
            <ProtectedRoute>
              <Layout />
            </ProtectedRoute>
          }
        >
          <Route index element={<Dashboard />} />
          <Route path="options" element={<OptionsChain />} />
          <Route path="strategies" element={<StrategyAnalysis />} />
          <Route path="chat" element={<AgentChat />} />
          <Route path="greeks" element={<GreeksVisualizer />} />
          <Route path="history" element={<History />} />
          <Route path="settings" element={<Settings />} />
        </Route>
        
        {/* Catch-all redirect */}
        <Route path="*" element={<Navigate to="/" replace />} />
      </Routes>
    </BrowserRouter>
  );
}

export default App;
