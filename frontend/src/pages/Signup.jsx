import React, { useState } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import { apiSignup } from '../services/api';

export default function Signup() {
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [name, setName] = useState('');
  const [organisation, setOrganisation] = useState('');
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(false);
  const navigate = useNavigate();

  const isValidEmail = (value) => {
    const trimmed = (value || '').trim();
    if (!trimmed) return false;
    const at = trimmed.indexOf('@');
    if (at <= 0 || at === trimmed.length - 1) return false;
    const local = trimmed.slice(0, at);
    const domain = trimmed.slice(at + 1);
    if (!/^[^\s@]+$/.test(local)) return false;
    if (!domain.includes('.') || domain.startsWith('.') || domain.endsWith('.') || domain.includes('..')) return false;
    const tld = domain.split('.').pop();
    if (!tld || tld.length < 2 || !/^[a-zA-Z]{2,}$/.test(tld)) return false;
    return /^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(trimmed);
  };

  const handleSubmit = async (e) => {
    e.preventDefault();
    setError('');
    if (!isValidEmail(email)) {
      setError('Please enter a valid email address.');
      return;
    }
    if (password.length < 8) {
      setError('Password must be at least 8 characters.');
      return;
    }
    setLoading(true);
    setError('');
    try {
      const data = await apiSignup(email.trim().toLowerCase(), password, (name || '').trim(), (organisation || '').trim());
      const msg = data.message || 'Check your email to verify your account before logging in.';
      navigate('/login', { replace: true, state: { fromSignup: true, signupMessage: msg } });
    } catch (err) {
      setError(err.message || 'Sign up failed.');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="min-h-[70vh] flex items-center justify-center px-4 py-12">
      <div className="w-full max-w-md">
        <h1 className="font-heading text-2xl font-bold text-slate-900 mb-2">Create an account</h1>
        <p className="text-slate-600 text-sm mb-6">
          You’ll use this to access your analyses and reports.
        </p>
        <form onSubmit={handleSubmit} className="space-y-4">
          {error && (
            <div className="p-3 rounded-lg bg-red-50 border border-red-200 text-red-800 text-sm">
              {error}
            </div>
          )}
          <div>
            <label htmlFor="signup-name" className="block text-sm font-medium text-slate-700 mb-1">
              Full name
            </label>
            <input
              id="signup-name"
              type="text"
              value={name}
              onChange={(e) => setName(e.target.value)}
              className="w-full px-4 py-2 rounded-lg border border-slate-300 focus:ring-2 focus:ring-amber-500 focus:border-amber-500"
              placeholder="Jane Smith"
              autoComplete="name"
            />
          </div>
          <div>
            <label htmlFor="signup-email" className="block text-sm font-medium text-slate-700 mb-1">
              Email
            </label>
            <input
              id="signup-email"
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
            <label htmlFor="signup-org" className="block text-sm font-medium text-slate-700 mb-1">
              Organisation (optional)
            </label>
            <input
              id="signup-org"
              type="text"
              value={organisation}
              onChange={(e) => setOrganisation(e.target.value)}
              className="w-full px-4 py-2 rounded-lg border border-slate-300 focus:ring-2 focus:ring-amber-500 focus:border-amber-500"
              placeholder="Your company"
            />
          </div>
          <div>
            <label htmlFor="signup-password" className="block text-sm font-medium text-slate-700 mb-1">
              Password (at least 8 characters)
            </label>
            <input
              id="signup-password"
              type="password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              required
              minLength={8}
              className="w-full px-4 py-2 rounded-lg border border-slate-300 focus:ring-2 focus:ring-amber-500 focus:border-amber-500"
              placeholder="••••••••"
              autoComplete="new-password"
            />
          </div>
          <button
            type="submit"
            disabled={loading}
            className="w-full py-3 rounded-lg bg-amber-500 text-slate-900 font-semibold hover:bg-amber-400 transition-colors disabled:opacity-50"
          >
            {loading ? 'Creating account…' : 'Create account'}
          </button>
        </form>
        <p className="mt-6 text-center text-slate-600 text-sm">
          Already have an account?{' '}
          <Link to="/login" className="text-amber-600 font-medium hover:text-amber-700">
            Sign in
          </Link>
        </p>
      </div>
    </div>
  );
}
