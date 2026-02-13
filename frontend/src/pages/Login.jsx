import React, { useState } from 'react';
import { Link, useNavigate, useLocation } from 'react-router-dom';
import { useAuth } from '../context/AuthContext';
import { apiResendVerification } from '../services/api';

export default function Login() {
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(false);
  const [emailNotVerified, setEmailNotVerified] = useState(false);
  const [resendMessage, setResendMessage] = useState('');
  const { login } = useAuth();
  const navigate = useNavigate();
  const location = useLocation();
  const from = location.state?.from || '/dashboard';
  const fromSignup = location.state?.fromSignup === true;
  const signupMessage = location.state?.signupMessage || '';

  const isValidEmail = (value) => {
    const trimmed = (value || '').trim();
    if (!trimmed) return false;
    const at = trimmed.indexOf('@');
    if (at <= 0 || at === trimmed.length - 1) return false;
    const domain = trimmed.slice(at + 1);
    if (!domain.includes('.') || domain.startsWith('.') || domain.endsWith('.') || domain.includes('..')) return false;
    const tld = domain.split('.').pop();
    if (!tld || tld.length < 2 || !/^[a-zA-Z]{2,}$/.test(tld)) return false;
    return /^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(trimmed);
  };

  const handleSubmit = async (e) => {
    e.preventDefault();
    setError('');
    setEmailNotVerified(false);
    setResendMessage('');
    if (!isValidEmail(email)) {
      setError('Please enter a valid email address.');
      return;
    }
    setLoading(true);
    try {
      await login(email.trim().toLowerCase(), password);
      navigate(from, { replace: true });
    } catch (err) {
      setError(err.message || 'Login failed.');
      if (err.errorCode === 'EMAIL_NOT_VERIFIED') setEmailNotVerified(true);
    } finally {
      setLoading(false);
    }
  };

  const handleResendVerification = async () => {
    const addr = email.trim().toLowerCase();
    if (!addr) {
      setResendMessage('Enter your email above first.');
      return;
    }
    setResendMessage('');
    try {
      const data = await apiResendVerification(addr);
      setResendMessage(data.message || 'Verification email sent. Check your inbox.');
    } catch (err) {
      setResendMessage(err.message || 'Failed to resend verification email.');
    }
  };

  return (
    <div className="min-h-[70vh] flex items-center justify-center px-4">
      <div className="w-full max-w-md">
        <h1 className="font-heading text-2xl font-bold text-slate-900 mb-2">Sign in</h1>
        <p className="text-slate-600 text-sm mb-6">
          Sign in to access your analyses and reports.
        </p>
        {(fromSignup && signupMessage) && (
          <div className="mb-4 p-3 rounded-lg bg-green-50 border border-green-200 text-green-800 text-sm">
            {signupMessage}
          </div>
        )}
        {fromSignup && !signupMessage && (
          <div className="mb-4 p-3 rounded-lg bg-green-50 border border-green-200 text-green-800 text-sm">
            Account created. Please sign in.
          </div>
        )}
        {emailNotVerified && (
          <div className="mb-4 p-3 rounded-lg bg-amber-50 border border-amber-200 text-amber-800 text-sm">
            Please verify your email before logging in. Check your inbox for the verification link, or{' '}
            <button type="button" onClick={handleResendVerification} className="underline font-medium hover:text-amber-900">
              resend verification email
            </button>.
          </div>
        )}
        {resendMessage && (
          <div className="mb-4 p-3 rounded-lg bg-slate-50 border border-slate-200 text-slate-800 text-sm">
            {resendMessage}
          </div>
        )}
        <form onSubmit={handleSubmit} className="space-y-4">
          {error && (
            <div className="p-3 rounded-lg bg-red-50 border border-red-200 text-red-800 text-sm">
              {error}
            </div>
          )}
          <div>
            <label htmlFor="login-email" className="block text-sm font-medium text-slate-700 mb-1">
              Email
            </label>
            <input
              id="login-email"
              type="email"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              required
              className="w-full px-4 py-2 rounded-lg border border-slate-300 focus:ring-2 focus:ring-amber-500 focus:border-amber-500"
              placeholder="you@company.com"
              autoComplete="email"
            />
          </div>
          <div>
            <label htmlFor="login-password" className="block text-sm font-medium text-slate-700 mb-1">
              Password
            </label>
            <input
              id="login-password"
              type="password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              required
              className="w-full px-4 py-2 rounded-lg border border-slate-300 focus:ring-2 focus:ring-amber-500 focus:border-amber-500"
              placeholder="••••••••"
              autoComplete="current-password"
            />
          </div>
          <div className="flex items-center justify-between text-sm">
            <Link to="/forgot-password" className="text-amber-600 hover:text-amber-700">
              Forgot password?
            </Link>
          </div>
          <button
            type="submit"
            disabled={loading}
            className="w-full py-3 rounded-lg bg-amber-500 text-slate-900 font-semibold hover:bg-amber-400 transition-colors disabled:opacity-50"
          >
            {loading ? 'Signing in…' : 'Sign in'}
          </button>
        </form>
        <p className="mt-6 text-center text-slate-600 text-sm">
          Don’t have an account?{' '}
          <Link to="/signup" className="text-amber-600 font-medium hover:text-amber-700">
            Sign up
          </Link>
        </p>
      </div>
    </div>
  );
}
