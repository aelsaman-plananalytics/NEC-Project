import React, { useState } from 'react';
import { Link } from 'react-router-dom';
import { apiRequestPasswordReset } from '../services/api';

export default function ForgotPassword() {
  const [email, setEmail] = useState('');
  const [sent, setSent] = useState(false);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');

  const handleSubmit = async (e) => {
    e.preventDefault();
    setError('');
    setLoading(true);
    try {
      await apiRequestPasswordReset(email.trim().toLowerCase());
      setSent(true);
    } catch (err) {
      setError(err.message || 'Failed to send reset link.');
    } finally {
      setLoading(false);
    }
  };

  if (sent) {
    return (
      <div className="min-h-[70vh] flex items-center justify-center px-4">
        <div className="w-full max-w-md text-center">
          <h1 className="font-heading text-2xl font-bold text-slate-900 mb-2">Check your email</h1>
          <p className="text-slate-600 mb-6">
            If an account exists for {email}, we’ve sent instructions to reset your password.
            The link expires in 1 hour.
          </p>
          <Link
            to="/login"
            className="inline-block py-2 px-4 rounded-lg bg-amber-500 text-slate-900 font-medium hover:bg-amber-400"
          >
            Back to sign in
          </Link>
        </div>
      </div>
    );
  }

  return (
    <div className="min-h-[70vh] flex items-center justify-center px-4">
      <div className="w-full max-w-md">
        <h1 className="font-heading text-2xl font-bold text-slate-900 mb-2">Reset password</h1>
        <p className="text-slate-600 text-sm mb-6">
          Enter your email and we’ll send you a link to reset your password.
        </p>
        <form onSubmit={handleSubmit} className="space-y-4">
          {error && (
            <div className="p-3 rounded-lg bg-red-50 border border-red-200 text-red-800 text-sm">
              {error}
            </div>
          )}
          <div>
            <label htmlFor="reset-email" className="block text-sm font-medium text-slate-700 mb-1">
              Email
            </label>
            <input
              id="reset-email"
              type="email"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              required
              className="w-full px-4 py-2 rounded-lg border border-slate-300 focus:ring-2 focus:ring-amber-500 focus:border-amber-500"
              placeholder="you@company.com"
              autoComplete="email"
            />
          </div>
          <button
            type="submit"
            disabled={loading}
            className="w-full py-3 rounded-lg bg-amber-500 text-slate-900 font-semibold hover:bg-amber-400 transition-colors disabled:opacity-50"
          >
            {loading ? 'Sending…' : 'Send reset link'}
          </button>
        </form>
        <p className="mt-6 text-center text-slate-600 text-sm">
          <Link to="/login" className="text-amber-600 font-medium hover:text-amber-700">
            Back to sign in
          </Link>
        </p>
      </div>
    </div>
  );
}
