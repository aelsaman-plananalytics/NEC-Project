import React, { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { usePipeline } from '../context/PipelineContext';
import { useAuth } from '../context/AuthContext';
import { apiGetRun } from '../services/api';

export default function Dashboard() {
  const navigate = useNavigate();
  const { history, removeFromHistory, resetPipeline, loadSavedRun, contractAnalysis } = usePipeline();
  const { user } = useAuth();
  const [openingId, setOpeningId] = useState(null);
  const [openError, setOpenError] = useState('');

  const handleStartNewAnalysis = () => {
    resetPipeline();
    navigate('/analysis');
  };

  const handleOpenAnalysis = async (entryId) => {
    setOpenError('');
    setOpeningId(entryId);
    try {
      const run = await apiGetRun(entryId);
      if (!run) {
        setOpenError('Analysis not found.');
        return;
      }
      loadSavedRun(run);
      if (run.validation_result) {
        navigate('/review');
      } else {
        navigate('/analysis');
      }
    } catch (err) {
      setOpenError(err.message || 'Could not open analysis.');
    } finally {
      setOpeningId(null);
    }
  };

  return (
    <div className="max-w-4xl mx-auto px-4 py-8">
      <h1 className="font-heading text-2xl font-bold text-slate-900 mb-2">Dashboard</h1>
      <p className="text-slate-600 mb-8">
        {user?.name ? `Welcome back, ${user.name}.` : 'Welcome.'} Start a new analysis or open one from your history.
      </p>

      <div className="mb-10 flex flex-wrap gap-3">
        <button
          type="button"
          onClick={handleStartNewAnalysis}
          className="inline-flex items-center justify-center px-8 py-4 rounded-xl bg-amber-500 text-slate-900 font-semibold text-lg hover:bg-amber-400 transition-colors"
        >
          Start new analysis
        </button>
        {contractAnalysis && (
          <button
            type="button"
            onClick={() => navigate('/compare')}
            className="inline-flex items-center justify-center px-6 py-4 rounded-xl border border-slate-300 text-slate-700 font-medium hover:bg-slate-50 transition-colors"
          >
            Compare two programmes
          </button>
        )}
      </div>

      <section>
        <h2 className="font-heading text-lg font-semibold text-slate-800 mb-4">Recent analyses</h2>
        {openError && (
          <p className="text-sm text-red-600 mb-3" role="alert">
            {openError}
          </p>
        )}
        {history.length === 0 ? (
          <p className="text-slate-600 text-sm">No analyses yet. Start one above.</p>
        ) : (
          <ul className="space-y-3">
            {history.map((entry) => (
              <li
                key={entry.id}
                className="flex items-center justify-between p-4 rounded-lg bg-white border border-slate-200"
              >
                <div>
                  <p className="font-medium text-slate-900">
                    {entry.contractName || 'Contract'} {entry.programmeName ? `· ${entry.programmeName}` : ''}
                  </p>
                  <p className="text-sm text-slate-500">
                    {entry.createdAt ? new Date(entry.createdAt).toLocaleString() : ''}
                  </p>
                </div>
                <div className="flex items-center gap-2">
                  <button
                    type="button"
                    onClick={() => handleOpenAnalysis(entry.id)}
                    disabled={openingId != null}
                    className="text-sm font-medium text-amber-600 hover:text-amber-700 disabled:opacity-50"
                    aria-label="Open this analysis"
                  >
                    {openingId === entry.id ? 'Opening…' : 'Open'}
                  </button>
                  <button
                    type="button"
                    onClick={() => removeFromHistory(entry.id)}
                    className="text-sm text-slate-500 hover:text-red-600"
                    aria-label="Remove from history"
                  >
                    Remove
                  </button>
                </div>
              </li>
            ))}
          </ul>
        )}
      </section>
    </div>
  );
}
