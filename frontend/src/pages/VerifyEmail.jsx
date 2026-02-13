import React, { useEffect, useState } from 'react';
import { Link, useSearchParams } from 'react-router-dom';
import { apiVerifyEmail } from '../services/api';

export default function VerifyEmail() {
  const [searchParams] = useSearchParams();
  const token = searchParams.get('token');
  const [status, setStatus] = useState('loading'); // 'loading' | 'success' | 'expired' | 'invalid' | 'missing'
  const [message, setMessage] = useState('');
  const [email, setEmail] = useState('');

  useEffect(() => {
    if (!token || !token.trim()) {
      setStatus('missing');
      setMessage('Missing verification link.');
      return;
    }
    apiVerifyEmail(token)
      .then((data) => {
        setStatus('success');
        setMessage(data.message || 'Email verified. You can now log in.');
        setEmail(data.email || '');
      })
      .catch((err) => {
        setMessage(err.message || 'Verification failed.');
        setStatus(err.errorCode === 'EXPIRED' ? 'expired' : 'invalid');
      });
  }, [token]);

  return (
    <div className="min-h-[70vh] flex items-center justify-center px-4 py-12">
      <div className="w-full max-w-md text-center">
        <h1 className="font-heading text-2xl font-bold text-slate-900 mb-4">Email verification</h1>
        {status === 'loading' && (
          <p className="text-slate-600">Verifying your email…</p>
        )}
        {status === 'success' && (
          <>
            <div className="mb-4 p-4 rounded-lg bg-green-50 border border-green-200 text-green-800 text-sm">
              {message}
              {email && <p className="mt-2 text-green-700">{email}</p>}
            </div>
            <Link
              to="/login"
              className="inline-block py-3 px-6 rounded-lg bg-amber-500 text-slate-900 font-semibold hover:bg-amber-400 transition-colors"
            >
              Sign in
            </Link>
          </>
        )}
        {(status === 'expired' || status === 'invalid' || status === 'missing') && (
          <>
            <div className="mb-4 p-4 rounded-lg bg-amber-50 border border-amber-200 text-amber-800 text-sm">
              {message}
            </div>
            <p className="text-slate-600 text-sm mb-4">
              You can request a new verification link from the sign-in page after entering your email.
            </p>
            <Link
              to="/login"
              className="inline-block py-3 px-6 rounded-lg bg-amber-500 text-slate-900 font-semibold hover:bg-amber-400 transition-colors"
            >
              Go to sign in
            </Link>
          </>
        )}
      </div>
    </div>
  );
}
