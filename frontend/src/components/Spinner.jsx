import React from 'react';

export default function Spinner({ label = 'Loading…', className = '' }) {
  return (
    <div
      className={`flex flex-col items-center justify-center min-h-[40vh] ${className}`}
      aria-busy="true"
    >
      <div
        className="w-10 h-10 border-2 border-amber-500 border-t-transparent rounded-full animate-spin mb-3"
        aria-hidden
      />
      {label && <p className="text-slate-600 text-sm">{label}</p>}
    </div>
  );
}
