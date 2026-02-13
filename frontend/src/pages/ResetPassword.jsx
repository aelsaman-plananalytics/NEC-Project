import React, { useState } from 'react';
import { Link, useSearchParams } from 'react-router-dom';
import { apiResetPassword } from '../services/api';

export default function ResetPassword() {
  const [searchParams] = useSearchParams();
  const tokenFromUrl = searchParams.get('token') || '';
  const [password, setPassword] = useState('');
  const [confirm, setConfirm] = useState('');
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  const [success, setSuccess] = useState(false);

  const handleSubmit = async (e) => {
    e.preventDefault();
    setError('');
    if (password.length < 8) {
      setError('Password must be at least 8 characters.');
      return;
    }
    if (password !== confirm) {
      setError('Passwords do not match.');
      return;
    }
    if (!tokenFromUrl.trim()) {
      setError('Invalid reset link. Use the link from your email.');
      return;
    }
    setLoading(true);
    try {
      await apiResetPassword(tokenFromUrl.trim(), password);
      setSuccess(true);
    } catch (err) {
      setError(err.message || 'Reset failed. The link may have expired.');
    } finally {
      setLoading(false);
    }
  };

  if (success) {
    return (
      <div className="min-h-[70vh] flex items-center justify-center px-4">
        <div className="w-full max-w-md text-center">
          <h1 className="font-heading text-2xl font-bold text-slate-900 mb-2">Password reset</h1>
          <p className="text-slate-600 mb-6">Your password has been reset. You can now sign in.</p>
          <Link
            to="/login"
            className="inline-block py-3 px-6 rounded-lg bg-amber-500 text-slate-900 font-semibold hover:bg-amber-400"
          >
            Sign in
          </Link>
        </div>
      </div>
    );
  }

  return (
    <div className="min-h-[70vh] flex items-center justify-center px-4">
      <div className="w-full max-w-md">
        <h1 className="font-heading text-2xl font-bold text-slate-900 mb-2">Set new password</h1>
        <p className="text-slate-600 text-sm mb-6">
          Enter your new password below. Use at least 8 characters.
        </p>
        {!tokenFromUrl && (
          <div className="mb-4 p-3 rounded-lg bg-amber-50 border border-amber-200 text-amber-800 text-sm">
            No reset token found. Use the link from your password reset email.
          </div>
        )}
        <form onSubmit={handleSubmit} className="space-y-4">
          {error && (
            <div className="p-3 rounded-lg bg-red-50 border border-red-200 text-red-800 text-sm">
              {error}
            </div>
          )}
          <div>
            <label htmlFor="new-password" className="block text-sm font-medium text-slate-700 mb-1">
              New password
            </label>
            <input
              id="new-password"
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
          <div>
            <label htmlFor="confirm-password" className="block text-sm font-medium text-slate-700 mb-1">
              Confirm password
            </label>
            <input
              id="confirm-password"
              type="password"
              value={confirm}
              onChange={(e) => setConfirm(e.target.value)}
              required
              minLength={8}
              className="w-full px-4 py-2 rounded-lg border border-slate-300 focus:ring-2 focus:ring-amber-500 focus:border-amber-500"
              placeholder="••••••••"
              autoComplete="new-password"
            />
          </div>
          <button
            type="submit"
            disabled={loading || !tokenFromUrl.trim()}
            className="w-full py-3 rounded-lg bg-amber-500 text-slate-900 font-semibold hover:bg-amber-400 transition-colors disabled:opacity-50"
          >
            {loading ? 'Resetting…' : 'Reset password'}
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
