import React, { useEffect } from 'react';

const typeStyles = {
  success: 'bg-green-50 border-green-200 text-green-800',
  error: 'bg-red-50 border-red-200 text-red-800',
  info: 'bg-blue-50 border-blue-200 text-blue-800',
  warning: 'bg-amber-50 border-amber-200 text-amber-800',
};

export default function Toast({ id, type = 'info', message, onDismiss, duration = 4000 }) {
  useEffect(() => {
    const t = setTimeout(() => {
      onDismiss(id);
    }, duration);
    return () => clearTimeout(t);
  }, [id, duration, onDismiss]);

  return (
    <div
      role="alert"
      className={`px-4 py-3 rounded-lg border shadow-sm animate-toast-in ${typeStyles[type] || typeStyles.info}`}
    >
      <p className="text-sm font-medium">{message}</p>
    </div>
  );
}
