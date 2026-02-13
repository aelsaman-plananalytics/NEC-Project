import React, { useState } from 'react';
import axios from 'axios';

const AnalyzeContract = () => {
  const [file, setFile] = useState(null);
  const [loading, setLoading] = useState(false);
  const [result, setResult] = useState(null);
  const [error, setError] = useState(null);
  const [dragActive, setDragActive] = useState(false);
  const [aiMode, setAiMode] = useState(null);

  const API_BASE_URL = process.env.REACT_APP_API_URL || 'http://127.0.0.1:8000';

  // Fetch AI_MODE on component mount
  React.useEffect(() => {
    const fetchAiMode = async () => {
      try {
        const response = await axios.get(`${API_BASE_URL}/api/ai_mode`);
        setAiMode(response.data);
      } catch (err) {
        console.warn('Could not fetch AI_MODE:', err);
        setAiMode({ ai_mode: 'unknown', description: 'Unable to determine AI mode' });
      }
    };
    fetchAiMode();
  }, [API_BASE_URL]);

  const handleDrag = (e) => {
    e.preventDefault();
    e.stopPropagation();
    if (e.type === 'dragenter' || e.type === 'dragover') {
      setDragActive(true);
    } else if (e.type === 'dragleave') {
      setDragActive(false);
    }
  };

  const handleDrop = (e) => {
    e.preventDefault();
    e.stopPropagation();
    setDragActive(false);

    if (e.dataTransfer.files && e.dataTransfer.files[0]) {
      const droppedFile = e.dataTransfer.files[0];
      if (droppedFile.type === 'application/pdf' || 
          droppedFile.name.endsWith('.pdf') ||
          droppedFile.type === 'application/vnd.openxmlformats-officedocument.wordprocessingml.document' ||
          droppedFile.name.endsWith('.docx')) {
        setFile(droppedFile);
        setError(null);
      } else {
        setError('Please upload a PDF or DOCX file');
      }
    }
  };

  const handleFileChange = (e) => {
    if (e.target.files && e.target.files[0]) {
      const selectedFile = e.target.files[0];
      if (selectedFile.name.endsWith('.pdf') || selectedFile.name.endsWith('.docx')) {
        setFile(selectedFile);
        setError(null);
      } else {
        setError('Please upload a PDF or DOCX file');
      }
    }
  };

  const handleAnalyze = async () => {
    if (!file) {
      setError('Please select a file first');
      return;
    }

    setLoading(true);
    setError(null);
    setResult(null);

    const formData = new FormData();
    formData.append('file', file);

    try {
      console.log('Sending request to:', `${API_BASE_URL}/api/v1/analyze_contract`);
      console.log('File:', file.name, 'Size:', file.size);
      
      const response = await axios.post(
        `${API_BASE_URL}/api/v1/analyze_contract`,
        formData,
        {
          headers: {
            'Content-Type': 'multipart/form-data',
          },
          timeout: 300000, // 5 minutes timeout for large files
          onUploadProgress: (progressEvent) => {
            if (progressEvent.total) {
              const percentCompleted = Math.round((progressEvent.loaded * 100) / progressEvent.total);
              console.log(`Upload progress: ${percentCompleted}%`);
            }
          },
        }
      );

      console.log('Response received:', response.status, response.data);
      setResult(response.data);
    } catch (err) {
      console.error('Analysis error:', err);
      let errorMessage = 'Failed to analyze contract. Please try again.';
      
      if (err.code === 'ERR_NETWORK' || err.message === 'Network Error') {
        errorMessage = `Network Error: Cannot connect to backend at ${API_BASE_URL}. Make sure the backend server is running on port 8000.`;
      } else if (err.response) {
        // Server responded with error status
        errorMessage = err.response.data?.detail || err.response.data?.message || `Server error: ${err.response.status}`;
      } else if (err.message) {
        errorMessage = err.message;
      }
      
      setError(errorMessage);
    } finally {
      setLoading(false);
    }
  };

  const formatFeatures = (features) => {
    const formatted = {};
    if (features.discipline) formatted.discipline = features.discipline;
    if (features.assets?.length > 0) formatted.assets = features.assets;
    if (features.actions?.length > 0) formatted.actions = features.actions;
    if (features.materials?.length > 0) formatted.materials = features.materials;
    if (features.chainages?.length > 0) formatted.chainages = features.chainages;
    if (features.drawings?.length > 0) formatted.drawings = features.drawings;
    if (features.activity_codes?.length > 0) formatted.activity_codes = features.activity_codes;
    return formatted;
  };

  return (
    <div className="min-h-screen bg-gray-50 py-8 px-4">
      <div className="max-w-7xl mx-auto">
        <h1 className="text-3xl font-bold text-gray-900 mb-8">
          Contract Analysis
        </h1>

        {/* AI Mode Indicator */}
        {aiMode && (
          <div className={`mb-6 p-3 rounded-lg border-2 ${
            aiMode.ai_mode === 'mock' 
              ? 'bg-yellow-50 border-yellow-300' 
              : 'bg-blue-50 border-blue-300'
          }`}>
            <div className="flex items-center justify-between">
              <div>
                <span className="font-semibold text-gray-700">AI Mode: </span>
                <span className={`font-bold ${
                  aiMode.ai_mode === 'mock' ? 'text-yellow-700' : 'text-blue-700'
                }`}>
                  {aiMode.ai_mode === 'mock' ? 'MOCK' : 'REAL'}
                </span>
                <span className="text-sm text-gray-600 ml-2">
                  ({aiMode.description})
                </span>
              </div>
              {aiMode.engines && (
                <div className="text-xs text-gray-500">
                  {aiMode.ai_mode === 'mock' ? '🔧 Mock Engines' : '🤖 OpenAI Engines'}
                </div>
              )}
            </div>
          </div>
        )}

        {/* File Upload Section */}
        <div className="bg-white rounded-lg shadow-md p-6 mb-6">
          <h2 className="text-xl font-semibold text-gray-800 mb-4">
            Upload Contract Document
          </h2>

          {/* Drag & Drop Area */}
          <div
            className={`border-2 border-dashed rounded-lg p-8 text-center transition-colors ${
              dragActive
                ? 'border-blue-500 bg-blue-50'
                : 'border-gray-300 hover:border-gray-400'
            }`}
            onDragEnter={handleDrag}
            onDragLeave={handleDrag}
            onDragOver={handleDrag}
            onDrop={handleDrop}
          >
            <input
              type="file"
              id="file-upload"
              className="hidden"
              accept=".pdf,.docx"
              onChange={handleFileChange}
            />
            <label
              htmlFor="file-upload"
              className="cursor-pointer flex flex-col items-center"
            >
              <svg
                className="w-12 h-12 text-gray-400 mb-4"
                fill="none"
                stroke="currentColor"
                viewBox="0 0 24 24"
              >
                <path
                  strokeLinecap="round"
                  strokeLinejoin="round"
                  strokeWidth={2}
                  d="M7 16a4 4 0 01-.88-7.903A5 5 0 1115.9 6L16 6a5 5 0 011 9.9M15 13l-3-3m0 0l-3 3m3-3v12"
                />
              </svg>
              <p className="text-gray-600 mb-2">
                Drag and drop your PDF or DOCX file here, or{' '}
                <span className="text-blue-600 hover:text-blue-800">
                  browse
                </span>
              </p>
              <p className="text-sm text-gray-500">
                Supports PDF and DOCX files
              </p>
            </label>
          </div>

          {/* Selected File */}
          {file && (
            <div className="mt-4 p-4 bg-gray-50 rounded-lg">
              <p className="text-sm text-gray-600">
                <span className="font-medium">Selected:</span> {file.name} (
                {(file.size / 1024).toFixed(2)} KB)
              </p>
            </div>
          )}

          {/* Error Message */}
          {error && (
            <div className="mt-4 p-4 bg-red-50 border border-red-200 rounded-lg">
              <p className="text-sm text-red-800">{error}</p>
            </div>
          )}

          {/* Analyze Button */}
          <button
            onClick={handleAnalyze}
            disabled={!file || loading}
            className={`mt-6 w-full py-3 px-6 rounded-lg font-semibold transition-colors ${
              !file || loading
                ? 'bg-gray-300 text-gray-500 cursor-not-allowed'
                : 'bg-blue-600 text-white hover:bg-blue-700'
            }`}
          >
            {loading ? (
              <span className="flex items-center justify-center">
                <svg
                  className="animate-spin -ml-1 mr-3 h-5 w-5 text-white"
                  xmlns="http://www.w3.org/2000/svg"
                  fill="none"
                  viewBox="0 0 24 24"
                >
                  <circle
                    className="opacity-25"
                    cx="12"
                    cy="12"
                    r="10"
                    stroke="currentColor"
                    strokeWidth="4"
                  ></circle>
                  <path
                    className="opacity-75"
                    fill="currentColor"
                    d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"
                  ></path>
                </svg>
                Analyzing...
              </span>
            ) : (
              'Analyze Contract'
            )}
          </button>
        </div>

        {/* Results Section */}
        {result && (
          <div className="bg-white rounded-lg shadow-md p-6">
            <h2 className="text-xl font-semibold text-gray-800 mb-4">
              Analysis Results
            </h2>
            
            {/* Summary */}
            {result.summary && (
              <div className="mb-6 p-4 bg-blue-50 rounded-lg">
                <div className="grid grid-cols-2 md:grid-cols-3 gap-4 text-sm">
                  <div>
                    <span className="font-semibold text-gray-700">Total Lines:</span>{' '}
                    <span className="text-gray-900">{result.summary.total_lines}</span>
                  </div>
                  <div>
                    <span className="font-semibold text-green-700">Scope Work Items:</span>{' '}
                    <span className="text-green-900">{result.summary.scope_work_count || result.summary.scope_count || 0}</span>
                  </div>
                  <div>
                    <span className="font-semibold text-blue-700">Admin Items:</span>{' '}
                    <span className="text-blue-900">{result.summary.admin_count || 0}</span>
                  </div>
                </div>
              </div>
            )}

            {/* Backward compatibility: if old format (result.lines), show it */}
            {result.lines && !result.scope_items && (
              <div className="mb-6">
                <h3 className="text-lg font-semibold text-gray-700 mb-3">
                  All Lines ({result.lines.length})
                </h3>
                <div className="overflow-x-auto">
                  <table className="min-w-full divide-y divide-gray-200">
                    <thead className="bg-gray-50">
                      <tr>
                        <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Line #</th>
                        <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Text</th>
                        <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Features</th>
                      </tr>
                    </thead>
                    <tbody className="bg-white divide-y divide-gray-200">
                      {result.lines.map((line, idx) => {
                        const features = formatFeatures(line.features || {});
                        const hasFeatures = Object.keys(features).length > 0;
                        return (
                          <tr key={idx} className="hover:bg-gray-50">
                            <td className="px-6 py-4 whitespace-nowrap text-sm font-medium text-gray-900">{line.line_no || idx + 1}</td>
                            <td className="px-6 py-4 text-sm text-gray-700 max-w-md">
                              <div className="truncate" title={line.text}>{line.text}</div>
                            </td>
                            <td className="px-6 py-4 text-sm text-gray-700">
                              {hasFeatures ? (
                                <div className="space-y-1">
                                  {features.discipline && <div><span className="font-medium">Discipline:</span> {features.discipline}</div>}
                                  {features.assets?.length > 0 && <div><span className="font-medium">Assets:</span> {features.assets.join(', ')}</div>}
                                  {features.actions?.length > 0 && <div><span className="font-medium">Actions:</span> {features.actions.join(', ')}</div>}
                                  {features.materials?.length > 0 && <div><span className="font-medium">Materials:</span> {features.materials.join(', ')}</div>}
                                  {features.chainages?.length > 0 && <div><span className="font-medium">Chainages:</span> {features.chainages.join(', ')}</div>}
                                  {features.drawings?.length > 0 && <div><span className="font-medium">Drawings:</span> {features.drawings.join(', ')}</div>}
                                </div>
                              ) : (
                                <span className="text-gray-400 italic">No features extracted</span>
                              )}
                            </td>
                          </tr>
                        );
                      })}
                    </tbody>
                  </table>
                </div>
              </div>
            )}

            {/* Scope Items Table (Main Focus) */}
            {result.scope_items && result.scope_items.length > 0 && (
              <div className="mb-6">
                <h3 className="text-lg font-semibold text-green-700 mb-3">
                  Scope Items ({result.scope_items.length})
                </h3>
                <div className="overflow-x-auto">
                  <table className="min-w-full divide-y divide-gray-200">
                    <thead className="bg-green-50">
                      <tr>
                        <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                          Line #
                        </th>
                        <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                          Section Type
                        </th>
                        <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                          Text
                        </th>
                        <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                          Features
                        </th>
                      </tr>
                    </thead>
                    <tbody className="bg-white divide-y divide-gray-200">
                      {result.scope_items.map((line, idx) => {
                        const features = formatFeatures(line.features || {});
                        const hasFeatures = Object.keys(features).length > 0;

                        return (
                          <tr key={idx} className="hover:bg-gray-50">
                            <td className="px-6 py-4 whitespace-nowrap text-sm font-medium text-gray-900">
                              {line.line_no || idx + 1}
                            </td>
                            <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-600">
                              <span className="px-2 py-1 bg-green-100 rounded text-xs font-medium">
                                {line.section_type || 'scope_work'}
                              </span>
                            </td>
                            <td className="px-6 py-4 text-sm text-gray-700 max-w-md">
                              <div className="truncate" title={line.text}>
                                {line.text}
                              </div>
                            </td>
                            <td className="px-6 py-4 text-sm text-gray-700">
                              {hasFeatures ? (
                                <div className="space-y-1">
                                  {features.discipline && (
                                    <div>
                                      <span className="font-medium">Discipline:</span>{' '}
                                      {features.discipline}
                                    </div>
                                  )}
                                  {features.assets?.length > 0 && (
                                    <div>
                                      <span className="font-medium">Assets:</span>{' '}
                                      {features.assets.join(', ')}
                                    </div>
                                  )}
                                  {features.actions?.length > 0 && (
                                    <div>
                                      <span className="font-medium">Actions:</span>{' '}
                                      {features.actions.join(', ')}
                                    </div>
                                  )}
                                  {features.materials?.length > 0 && (
                                    <div>
                                      <span className="font-medium">Materials:</span>{' '}
                                      {features.materials.join(', ')}
                                    </div>
                                  )}
                                  {features.chainages?.length > 0 && (
                                    <div>
                                      <span className="font-medium">Chainages:</span>{' '}
                                      {features.chainages.join(', ')}
                                    </div>
                                  )}
                                  {features.drawings?.length > 0 && (
                                    <div>
                                      <span className="font-medium">Drawings:</span>{' '}
                                      {features.drawings.join(', ')}
                                    </div>
                                  )}
                                </div>
                              ) : (
                                <span className="text-gray-400 italic">No features extracted</span>
                              )}
                            </td>
                          </tr>
                        );
                      })}
                    </tbody>
                  </table>
                </div>
              </div>
            )}

            {/* Admin Items Section */}
            {result.admin_items && result.admin_items.length > 0 && (
              <div className="mb-6">
                <h3 className="text-lg font-semibold text-blue-700 mb-3">
                  Admin Items ({result.admin_items.length})
                </h3>
                <div className="overflow-x-auto">
                  <table className="min-w-full divide-y divide-gray-200">
                    <thead className="bg-blue-50">
                      <tr>
                        <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                          Line #
                        </th>
                        <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                          Section Type
                        </th>
                        <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                          Text
                        </th>
                      </tr>
                    </thead>
                    <tbody className="bg-white divide-y divide-gray-200">
                      {result.admin_items.map((line, idx) => (
                        <tr key={idx} className="hover:bg-gray-50">
                          <td className="px-6 py-4 whitespace-nowrap text-sm font-medium text-gray-900">
                            {line.line_no || idx + 1}
                          </td>
                          <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-600">
                            <span className="px-2 py-1 bg-gray-100 rounded text-xs">
                              {line.section_type || 'admin_general'}
                            </span>
                          </td>
                          <td className="px-6 py-4 text-sm text-gray-700 max-w-md">
                            <div className="truncate" title={line.text}>
                              {line.text}
                            </div>
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </div>
            )}

            {result.drawing_references && result.drawing_references.length > 0 && (
              <details className="mb-4">
                <summary className="text-md font-semibold text-purple-700 cursor-pointer hover:text-purple-800">
                  Drawing References ({result.drawing_references.length})
                </summary>
                <div className="mt-2 overflow-x-auto">
                  <table className="min-w-full divide-y divide-gray-200">
                    <thead className="bg-purple-50">
                      <tr>
                        <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase">Line #</th>
                        <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase">Text</th>
                      </tr>
                    </thead>
                    <tbody className="bg-white divide-y divide-gray-200">
                      {result.drawing_references.map((line, idx) => (
                        <tr key={idx} className="hover:bg-gray-50">
                          <td className="px-6 py-4 text-sm text-gray-900">{line.line_no || idx + 1}</td>
                          <td className="px-6 py-4 text-sm text-gray-700">{line.text}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </details>
            )}

            {/* JSON Viewer */}
            <div className="mt-6">
              <div className="flex justify-between items-center mb-3">
                <h3 className="text-lg font-semibold text-gray-800">
                  Full JSON Response
                </h3>
                <button
                  onClick={() => {
                    navigator.clipboard.writeText(JSON.stringify(result, null, 2));
                    alert('JSON copied to clipboard!');
                  }}
                  className="px-3 py-1 bg-blue-600 text-white text-sm rounded hover:bg-blue-700 transition-colors"
                >
                  Copy JSON
                </button>
              </div>
              <div className="bg-gray-900 rounded-lg p-4 overflow-auto max-h-96 border border-gray-700">
                <pre 
                  className="text-xs text-green-400 font-mono whitespace-pre overflow-x-auto"
                  style={{ 
                    whiteSpace: 'pre',
                    wordBreak: 'normal',
                    overflowWrap: 'normal'
                  }}
                >
                  {JSON.stringify(result, null, 2)}
                </pre>
              </div>
            </div>
          </div>
        )}
      </div>
    </div>
  );
};

export default AnalyzeContract;


