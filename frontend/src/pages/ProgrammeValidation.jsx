import React, { useState, useCallback } from 'react';
import { useNavigate } from 'react-router-dom';
import { usePipeline } from '../context/PipelineContext';
import { useAuth } from '../context/AuthContext';
import { useToast } from '../context/ToastContext';
import { validateProgramme, parseApiError } from '../services/api';
import ErrorModal from '../components/ErrorModal';
import Spinner from '../components/Spinner';

export default function ProgrammeValidation() {
  const navigate = useNavigate();
  const { handleUnauthorized } = useAuth();
  const { addToast } = useToast();
  const { contractAnalysis, setValidationResult, setStage, contractFile, addToHistory } = usePipeline();
  const [file, setFile] = useState(null);
  const [previousFile, setPreviousFile] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  const [errorCode, setErrorCode] = useState(null);
  const [errorDetails, setErrorDetails] = useState(null);
  const [dragActive, setDragActive] = useState(false);

  const handleValidate = useCallback(async () => {
    if (!contractAnalysis) return;
    if (!file) {
      setError('Please select a programme file first.');
      return;
    }
    setLoading(true);
    setError('');
    setErrorCode(null);
    setErrorDetails(null);
    try {
      const result = await validateProgramme(file, contractAnalysis, previousFile || undefined);
      setValidationResult(result, file);
      setStage(3);
      if (result.run_id && addToHistory) {
        addToHistory({
          contractName: contractFile?.name || contractAnalysis?.project,
          programmeName: file?.name ?? null,
          validationResult: true,
          runId: result.run_id,
        });
      }
      addToast({ type: 'success', message: 'Validation complete. Review the summary below.' });
      navigate('/review');
    } catch (err) {
      if (err.errorCode === 'UNAUTHORIZED' && handleUnauthorized) {
        handleUnauthorized();
        return;
      }
      const parsed = parseApiError({
        error_code: err.errorCode,
        error_message: err.message,
        details: err.details,
      });
      setError(parsed.userMessage);
      setErrorCode(parsed.errorCode || null);
      setErrorDetails(parsed.details ?? null);
      const toastCodes = ['PLAN_LIMIT_EXCEEDED', 'VALIDATION_TIMEOUT', 'RATE_LIMIT_EXCEEDED'];
      if (toastCodes.includes(parsed.errorCode)) {
        addToast({ type: 'error', message: parsed.userMessage });
      }
    } finally {
      setLoading(false);
    }
  }, [file, previousFile, contractAnalysis, setValidationResult, setStage, navigate, contractFile, addToHistory, handleUnauthorized, addToast]);

  if (!contractAnalysis) {
    navigate('/analysis', { replace: true });
    return null;
  }

  const handleDrag = (e) => {
    e.preventDefault();
    e.stopPropagation();
    setDragActive(e.type === 'dragenter' || e.type === 'dragover');
  };

  const handleDrop = (e) => {
    e.preventDefault();
    e.stopPropagation();
    setDragActive(false);
    const f = e.dataTransfer?.files?.[0];
    if (f && f.name.toLowerCase().endsWith('.xer')) {
      setFile(f);
      setError('');
    } else {
      setError('Please upload a valid XER file (Primavera P6 programme).');
    }
  };

  const handleFileChange = (e) => {
    const f = e.target?.files?.[0];
    if (f && f.name.toLowerCase().endsWith('.xer')) {
      setFile(f);
      setError('');
    } else if (f) {
      setError('Please upload a valid XER file (Primavera P6 programme).');
    }
  };

  const handlePreviousFileChange = (e) => {
    const f = e.target?.files?.[0];
    if (!f) {
      setPreviousFile(null);
      return;
    }
    if (f.name.toLowerCase().endsWith('.xer')) {
      setPreviousFile(f);
    } else {
      setPreviousFile(null);
    }
  };

  return (
    <div className="max-w-3xl mx-auto px-4 py-8">
      <h1 className="font-heading text-2xl font-bold text-slate-900 mb-2">Programme upload</h1>
      <p className="text-slate-600 mb-6">
        Upload your programme (XER from Primavera P6). This programme will be checked against the contract requirements we extracted from {contractFile?.name || 'your contract'}.
      </p>
      <div className="bg-white border border-slate-200 rounded-xl p-6">
        <div
          className={`border-2 border-dashed rounded-lg p-8 text-center transition-colors ${dragActive ? 'border-amber-500 bg-amber-50/50' : 'border-slate-300'}`}
          onDragEnter={handleDrag}
          onDragLeave={handleDrag}
          onDragOver={handleDrag}
          onDrop={handleDrop}
        >
          <input
            type="file"
            id="programme-upload"
            accept=".xer"
            onChange={handleFileChange}
            className="hidden"
          />
          <label htmlFor="programme-upload" className="cursor-pointer block">
            <p className="text-slate-600 mb-2">
              Drag and drop your XER file here, or <span className="text-amber-600 font-medium">browse</span> to choose a file.
            </p>
            <p className="text-sm text-slate-500">XER only (Primavera P6 export).</p>
          </label>
        </div>
        {file && (
          <p className="mt-4 text-sm text-slate-600">
            Selected: <strong>{file.name}</strong>
          </p>
        )}
        <div className="mt-6 pt-6 border-t border-slate-200">
          <label className="block text-sm font-medium text-slate-700 mb-2">
            Compare with previous programme (optional XER)
          </label>
          <p className="text-slate-500 text-sm mb-2">
            Upload a previous XER to see what changed (obligations became aligned/unaligned).
          </p>
          <input
            type="file"
            id="previous-programme-upload"
            accept=".xer"
            onChange={handlePreviousFileChange}
            className="block w-full text-sm text-slate-600 file:mr-4 file:py-2 file:px-4 file:rounded-lg file:border-0 file:text-slate-700 file:bg-slate-100 hover:file:bg-slate-200"
          />
          {previousFile && (
            <p className="mt-2 text-sm text-slate-600">Previous: <strong>{previousFile.name}</strong></p>
          )}
        </div>
        {error && (
          <div className="mt-4 p-3 rounded-lg bg-red-50 border border-red-200 text-red-800 text-sm">
            {error}
          </div>
        )}
        {errorCode && (
          <ErrorModal
            errorCode={errorCode}
            message={error}
            details={errorDetails}
            onClose={() => { setErrorCode(null); setErrorDetails(null); setError(''); }}
          />
        )}
        {loading && (
          <div className="mt-4 flex justify-center">
            <Spinner label="Validating programme…" className="min-h-0 py-4" />
          </div>
        )}
        <button
          type="button"
          disabled={!file || loading}
          onClick={handleValidate}
          className="mt-6 w-full py-3 rounded-lg bg-amber-500 text-slate-900 font-semibold hover:bg-amber-400 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
        >
          {loading ? 'Validating programme…' : 'Validate programme'}
        </button>
      </div>
      <p className="mt-4 text-sm text-slate-500">
        Step 2 of 4 — Next you’ll review the validation summary before generating the report.
      </p>
    </div>
  );
}
