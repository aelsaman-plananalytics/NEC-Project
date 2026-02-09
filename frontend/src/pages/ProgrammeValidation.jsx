import React, { useState, useCallback } from 'react';
import { useNavigate } from 'react-router-dom';
import { usePipeline } from '../context/PipelineContext';
import { validateProgramme } from '../services/api';

export default function ProgrammeValidation() {
  const navigate = useNavigate();
  const { contractAnalysis, setValidationResult, setStage, contractFile } = usePipeline();
  const [file, setFile] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  const [dragActive, setDragActive] = useState(false);

  const handleValidate = useCallback(async () => {
    if (!contractAnalysis) return;
    if (!file) {
      setError('Please select a programme file first.');
      return;
    }
    setLoading(true);
    setError('');
    try {
      const result = await validateProgramme(file, contractAnalysis);
      setValidationResult(result, file);
      setStage(3);
      navigate('/review');
    } catch (err) {
      setError(err.message || 'We couldn’t process the programme file. Please check it is a valid XER file and try again.');
    } finally {
      setLoading(false);
    }
  }, [file, contractAnalysis, setValidationResult, setStage, navigate]);

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
        {error && (
          <div className="mt-4 p-3 rounded-lg bg-red-50 border border-red-200 text-red-800 text-sm">
            {error}
          </div>
        )}
        <button
          type="button"
          disabled={!file || loading}
          onClick={handleValidate}
          className="mt-6 w-full py-3 rounded-lg bg-amber-500 text-slate-900 font-semibold hover:bg-amber-400 disabled:opacity-50 disabled:cursor-not-allowed"
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
