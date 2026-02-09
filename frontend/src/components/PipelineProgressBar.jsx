import React from 'react';
import { useLocation, useNavigate } from 'react-router-dom';
import { usePipeline } from '../context/PipelineContext';

const STEPS = [
  { path: '/analysis', label: 'Contract analysis', stage: 1 },
  { path: '/programme', label: 'Programme upload', stage: 2 },
  { path: null, label: 'Validation', stage: 2.5 },
  { path: '/review', label: 'Review', stage: 3 },
  { path: '/results', label: 'Report', stage: 4 },
];

function getCurrentStepIndex(locationPath) {
  if (locationPath.startsWith('/results')) return 4;
  if (locationPath.startsWith('/review')) return 3;
  if (locationPath.startsWith('/programme')) return 1;
  if (locationPath.startsWith('/analysis')) return 0;
  return 0;
}

function stepStatus(stepIndex, currentStepIndex) {
  if (stepIndex < currentStepIndex) return 'completed';
  if (stepIndex === currentStepIndex) return 'active';
  return 'locked';
}

export default function PipelineProgressBar() {
  const location = useLocation();
  const navigate = useNavigate();
  const path = location.pathname;
  const currentStepIndex = getCurrentStepIndex(path);

  const isPipelinePage = ['/analysis', '/programme', '/review', '/results'].some((p) => path.startsWith(p));
  if (!isPipelinePage) return null;

  return (
    <nav
      className="bg-white border-b border-slate-200 px-4 py-3"
      aria-label="Analysis pipeline progress"
    >
      <div className="max-w-4xl mx-auto">
        <ol className="flex flex-wrap items-center gap-2 sm:gap-0">
          {STEPS.map((step, i) => {
            const status = stepStatus(i, currentStepIndex);
            const isClickable = status === 'completed' && step.path;
            const isActive = status === 'active';
            const isLocked = status === 'locked';

            return (
              <li
                key={step.path || 'validation'}
                className="flex items-center"
              >
                <button
                  type="button"
                  onClick={() => isClickable && navigate(step.path)}
                  disabled={!isClickable}
                  className={`
                    flex items-center gap-1.5 rounded-md px-2 py-1.5 text-left text-sm font-medium transition-colors
                    ${isActive ? 'bg-amber-100 text-amber-900 ring-1 ring-amber-300' : ''}
                    ${status === 'completed' ? 'text-slate-600 hover:bg-slate-100 hover:text-slate-900' : ''}
                    ${isLocked ? 'text-slate-400 cursor-default' : ''}
                    ${isClickable ? 'cursor-pointer' : ''}
                  `}
                  aria-current={isActive ? 'step' : undefined}
                  aria-disabled={isLocked}
                >
                  <span
                    className={`
                      flex h-6 w-6 shrink-0 items-center justify-center rounded-full text-xs
                      ${status === 'completed' ? 'bg-slate-600 text-white' : ''}
                      ${isActive ? 'bg-amber-500 text-slate-900' : ''}
                      ${isLocked ? 'bg-slate-200 text-slate-500' : ''}
                    `}
                    aria-hidden
                  >
                    {status === 'completed' ? '✓' : i + 1}
                  </span>
                  <span className="hidden sm:inline">{step.label}</span>
                </button>
                {i < STEPS.length - 1 && (
                  <span
                    className={`mx-1 h-px w-4 sm:w-6 shrink-0 ${
                      status === 'completed' ? 'bg-slate-400' : 'bg-slate-200'
                    }`}
                    aria-hidden
                  />
                )}
              </li>
            );
          })}
        </ol>
        <p className="mt-1.5 text-xs text-slate-500">
          {path === '/analysis' && 'Upload and analyse the contract.'}
          {path === '/programme' && 'Upload programme (XER) and run validation.'}
          {(path === '/review') && 'Review findings and add notes if needed.'}
          {path === '/results' && 'Download your Programme Validation report.'}
        </p>
      </div>
    </nav>
  );
}
