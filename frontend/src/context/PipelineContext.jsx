import React, { createContext, useContext, useState, useCallback, useEffect, useRef } from 'react';
import { useAuth } from './AuthContext';
import { apiListRuns, apiCreateRun, apiDeleteRun } from '../services/api';

const PipelineContext = createContext(null);

/** Map API run to dashboard entry shape */
function runToEntry(run) {
  return {
    id: String(run.id),
    contractName: run.contract_name || 'Contract',
    programmeName: run.programme_name ?? null,
    createdAt: run.created_at,
  };
}

export function PipelineProvider({ children }) {
  const { user } = useAuth();
  const userId = user?.id ?? null;
  const previousUserIdRef = useRef(undefined);

  const [contractAnalysis, setContractAnalysisState] = useState(null);
  const [contractFile, setContractFile] = useState(null);
  const [validationResult, setValidationResultState] = useState(null);
  const [programmeFile, setProgrammeFile] = useState(null);
  const [stage, setStageState] = useState(1);
  const [history, setHistory] = useState([]);
  const [userConfirmations, setUserConfirmationsState] = useState([]);
  // Data is only exposed when it belongs to the current user (no cross-account visibility)
  const [pipelineOwnerId, setPipelineOwnerId] = useState(null);

  // When user logs out or switches account: clear pipeline and load that user's runs from DB
  useEffect(() => {
    const prev = previousUserIdRef.current;
    const changed = prev !== userId;
    previousUserIdRef.current = userId;

    if (changed) {
      setContractAnalysisState(null);
      setContractFile(null);
      setValidationResultState(null);
      setProgrammeFile(null);
      setStageState(1);
      setPipelineOwnerId(null);
      setUserConfirmationsState([]);
      if (userId != null) {
        apiListRuns()
          .then((runs) => setHistory(runs.map(runToEntry)))
          .catch(() => setHistory([]));
      } else {
        setHistory([]);
      }
    }
  }, [userId]);

  const setContractAnalysis = useCallback((analysis, file) => {
    setContractAnalysisState(analysis);
    setContractFile(file ? { name: file.name, size: file.size } : null);
    setValidationResultState(null);
    setProgrammeFile(null);
    setStageState(2);
    setPipelineOwnerId(userId);
  }, [userId]);

  const setValidationResult = useCallback((result, file) => {
    setValidationResultState(result);
    setProgrammeFile(file ? { name: file.name } : null);
    setStageState(3);
    setPipelineOwnerId(userId);
    setUserConfirmationsState([]);
  }, [userId]);

  const proceedToReport = useCallback(() => {
    setStageState(4);
  }, []);

  const goToStage = useCallback((s) => {
    setStageState(Math.max(1, Math.min(4, s)));
  }, []);

  const resetPipeline = useCallback(() => {
    setContractAnalysisState(null);
    setContractFile(null);
    setValidationResultState(null);
    setProgrammeFile(null);
    setStageState(1);
    setPipelineOwnerId(null);
    setUserConfirmationsState([]);
  }, []);

  const addUserConfirmation = useCallback((findingId, { confirmed, note }) => {
    const entry = {
      findingId,
      confirmed: !!confirmed,
      note: note ? String(note).trim() : '',
      timestamp: new Date().toISOString(),
    };
    setUserConfirmationsState((prev) => {
      const rest = prev.filter((e) => e.findingId !== findingId);
      return [...rest, entry];
    });
  }, []);

  const getUserConfirmations = useCallback(() => {
    return userConfirmations;
  }, [userConfirmations]);

  /** Load a previously saved run (from GET /api/runs/:id) into the pipeline so the user can view it. */
  const loadSavedRun = useCallback(
    (run) => {
      if (!run) return;
      setContractAnalysisState(run.contract_analysis || null);
      setContractFile(
        run.contract_name ? { name: run.contract_name, size: null } : null
      );
      setValidationResultState(run.validation_result || null);
      setProgrammeFile(
        run.programme_name ? { name: run.programme_name } : null
      );
      setStageState(run.validation_result ? 3 : 2);
      setPipelineOwnerId(userId);
    },
    [userId]
  );

  const addToHistory = useCallback(
    (entry) => {
      const contractName = entry.contractName || contractAnalysis?.project || contractFile?.name || 'Contract';
      const programmeName = entry.programmeName ?? programmeFile?.name ?? null;
      apiCreateRun({
        contractName,
        programmeName,
        contractAnalysis,
        validationResult,
      })
        .then((run) => {
          setHistory((prev) => [runToEntry(run), ...prev].slice(0, 50));
        })
        .catch(() => {
          // Keep UI unchanged; run not persisted (e.g. offline or server error)
        });
    },
    [userId, contractAnalysis, validationResult, contractFile, programmeFile]
  );

  const removeFromHistory = useCallback((id) => {
    apiDeleteRun(id).catch(() => {});
    setHistory((prev) => prev.filter((e) => e.id !== id));
  }, []);

  // Expose pipeline data only when it belongs to the current user (avoids showing other account's data on switch)
  const isOwner = pipelineOwnerId != null && pipelineOwnerId === userId;

  const value = {
    contractAnalysis: isOwner ? contractAnalysis : null,
    contractFile: isOwner ? contractFile : null,
    validationResult: isOwner ? validationResult : null,
    programmeFile: isOwner ? programmeFile : null,
    stage: isOwner ? stage : 1,
    setContractAnalysis,
    setValidationResult,
    setStage: setStageState,
    proceedToReport,
    goToStage,
    resetPipeline,
    loadSavedRun,
    history,
    addToHistory,
    removeFromHistory,
    userConfirmations: isOwner ? userConfirmations : [],
    addUserConfirmation,
    getUserConfirmations,
  };

  return (
    <PipelineContext.Provider value={value}>
      {children}
    </PipelineContext.Provider>
  );
}

export function usePipeline() {
  const ctx = useContext(PipelineContext);
  if (!ctx) throw new Error('usePipeline must be used within PipelineProvider');
  return ctx;
}
