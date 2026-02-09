import React, { useState, useCallback } from 'react';
import { useNavigate } from 'react-router-dom';
import { usePipeline } from '../context/PipelineContext';
import { analyzeContract } from '../services/api';

const STAGE_UPLOAD = 'upload';
const STAGE_REVIEW = 'review';

export default function ContractAnalysis() {
  const navigate = useNavigate();
  const { setContractAnalysis, contractAnalysis, contractFile, setStage, resetPipeline } = usePipeline();
  const [stage, setLocalStage] = useState(contractAnalysis ? STAGE_REVIEW : STAGE_UPLOAD);
  const [file, setFile] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  const [dragActive, setDragActive] = useState(false);

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
    if (f && (f.name.endsWith('.pdf') || f.name.endsWith('.docx'))) {
      setFile(f);
      setError('');
    } else {
      setError('Please upload a PDF or Word document.');
    }
  };

  const handleFileChange = (e) => {
    const f = e.target?.files?.[0];
    if (f && (f.name.endsWith('.pdf') || f.name.endsWith('.docx'))) {
      setFile(f);
      setError('');
    } else if (f) {
      setError('Please upload a PDF or Word document.');
    }
  };

  const handleAnalyze = useCallback(async () => {
    if (!file) {
      setError('Please select a file first.');
      return;
    }
    setLoading(true);
    setError('');
    try {
      const result = await analyzeContract(file);
      setContractAnalysis(result, file);
      setLocalStage(STAGE_REVIEW);
    } catch (err) {
      setError(err.message || 'We couldn’t process the contract. Please check the file is a valid PDF or Word document and try again.');
    } finally {
      setLoading(false);
    }
  }, [file, setContractAnalysis]);

  const handleConfirmAndContinue = () => {
    setStage(2);
    navigate('/programme');
  };

  const showingReview = stage === STAGE_REVIEW && contractAnalysis;

  const summary = contractAnalysis && (() => {
    const md = contractAnalysis.metadata || {};
    const dates = contractAnalysis.contract_dates || {};
    const scopeCount = md.total_scope_items ?? (contractAnalysis.scope_items?.length ?? 0);
    const constraints = contractAnalysis.constraints;
    const constraintCount = Array.isArray(constraints) ? constraints.length : 0;
    const pcm = contractAnalysis.programme_compliance_model || {};
    const requiredActivities = pcm.required_activities || [];
    const programmeReqsCount = requiredActivities.length;
    return {
      project: contractAnalysis.project || 'Contract',
      startingDate: dates.starting_date || 'Not specified',
      completionDate: dates.completion_date || 'Not specified',
      scopeCount,
      constraintCount,
      programmeReqsCount,
    };
  })();

  if (showingReview && summary) {
    return (
      <div className="max-w-3xl mx-auto px-4 py-8">
        <h1 className="font-heading text-2xl font-bold text-slate-900 mb-2">Review contract extraction</h1>
        <p className="text-slate-600 mb-6">
          The system has extracted the following from your contract. Please confirm before continuing to programme upload.
        </p>
        <div className="bg-white border border-slate-200 rounded-xl p-6 space-y-6">
          <div>
            <h2 className="font-semibold text-slate-800 mb-2">What the system identified from the contract</h2>
            <ul className="space-y-2 text-slate-700">
              <li><strong>Contract / project:</strong> {summary.project}</li>
              <li><strong>Key dates — start:</strong> {summary.startingDate}</li>
              <li><strong>Key dates — completion:</strong> {summary.completionDate}</li>
              <li><strong>Scope items:</strong> {summary.scopeCount} obligations identified</li>
              <li><strong>Constraints:</strong> {summary.constraintCount} constraints identified</li>
              <li><strong>Programme requirements:</strong> {summary.programmeReqsCount} required activities or gates</li>
            </ul>
          </div>
          <p className="text-slate-600 text-sm">
            This information will be used to validate your programme in the next step.
          </p>
          <div className="flex flex-wrap gap-3">
            <button
              type="button"
              onClick={handleConfirmAndContinue}
              className="px-6 py-3 rounded-lg bg-amber-500 text-slate-900 font-semibold hover:bg-amber-400"
            >
              Confirm and continue
            </button>
            <button
              type="button"
              onClick={() => {
                resetPipeline();
                setLocalStage(STAGE_UPLOAD);
              }}
              className="px-6 py-3 rounded-lg border border-slate-300 text-slate-700 font-medium hover:bg-slate-50"
            >
              Upload a different contract
            </button>
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className="max-w-3xl mx-auto px-4 py-8">
      <h1 className="font-heading text-2xl font-bold text-slate-900 mb-2">Contract analysis</h1>
      <p className="text-slate-600 mb-6">
        Upload your NEC contract (PDF or Word). The system will extract key dates, scope items, constraints, and programme requirements.
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
            id="contract-upload"
            accept=".pdf,.docx"
            onChange={handleFileChange}
            className="hidden"
          />
          <label htmlFor="contract-upload" className="cursor-pointer block">
            <p className="text-slate-600 mb-2">
              Drag and drop your contract here, or <span className="text-amber-600 font-medium">browse</span> to choose a file.
            </p>
            <p className="text-sm text-slate-500">PDF or Word (.docx) only.</p>
          </label>
        </div>
        {file && (
          <p className="mt-4 text-sm text-slate-600">
            Selected: <strong>{file.name}</strong> ({(file.size / 1024).toFixed(1)} KB)
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
          onClick={handleAnalyze}
          className="mt-6 w-full py-3 rounded-lg bg-amber-500 text-slate-900 font-semibold hover:bg-amber-400 disabled:opacity-50 disabled:cursor-not-allowed"
        >
          {loading ? 'Analysing…' : 'Analyse contract'}
        </button>
      </div>
      <p className="mt-4 text-sm text-slate-500">
        Step 1 of 4 — After analysis you’ll review what was extracted, then upload your programme.
      </p>
    </div>
  );
}
