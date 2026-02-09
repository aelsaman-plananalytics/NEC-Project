import React from 'react';
import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom';
import { AuthProvider } from './context/AuthContext';
import { PipelineProvider } from './context/PipelineContext';
import Layout from './components/Layout';
import ProtectedRoute from './components/ProtectedRoute';
import HomePage from './pages/HomePage';
import Login from './pages/Login';
import Signup from './pages/Signup';
import ForgotPassword from './pages/ForgotPassword';
import Dashboard from './pages/Dashboard';
import AccountSettings from './pages/AccountSettings';
import Help from './pages/Help';
import ContractAnalysis from './pages/ContractAnalysis';
import ProgrammeValidation from './pages/ProgrammeValidation';
import ProgrammeCompare from './pages/ProgrammeCompare';
import ValidationReview from './pages/ValidationReview';
import ResultsReport from './pages/ResultsReport';
import './App.css';

function App() {
  return (
    <AuthProvider>
      <PipelineProvider>
        <BrowserRouter>
          <Routes>
            <Route path="/" element={<Layout />}>
              <Route
                index
                element={
                  <ProtectedRoute>
                    <HomePage />
                  </ProtectedRoute>
                }
              />
              <Route path="login" element={<Login />} />
              <Route path="signup" element={<Signup />} />
              <Route path="forgot-password" element={<ForgotPassword />} />
              <Route path="help" element={<Help />} />
              <Route
                path="dashboard"
                element={
                  <ProtectedRoute>
                    <Dashboard />
                  </ProtectedRoute>
                }
              />
              <Route
                path="account"
                element={
                  <ProtectedRoute>
                    <AccountSettings />
                  </ProtectedRoute>
                }
              />
              <Route
                path="analysis"
                element={
                  <ProtectedRoute>
                    <ContractAnalysis />
                  </ProtectedRoute>
                }
              />
              <Route
                path="programme"
                element={
                  <ProtectedRoute>
                    <ProgrammeValidation />
                  </ProtectedRoute>
                }
              />
              <Route
                path="compare"
                element={
                  <ProtectedRoute>
                    <ProgrammeCompare />
                  </ProtectedRoute>
                }
              />
              <Route
                path="review"
                element={
                  <ProtectedRoute>
                    <ValidationReview />
                  </ProtectedRoute>
                }
              />
              <Route
                path="results"
                element={
                  <ProtectedRoute>
                    <ResultsReport />
                  </ProtectedRoute>
                }
              />
            </Route>
            <Route path="*" element={<Navigate to="/" replace />} />
          </Routes>
        </BrowserRouter>
      </PipelineProvider>
    </AuthProvider>
  );
}

export default App;
