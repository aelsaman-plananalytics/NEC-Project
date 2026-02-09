import React, { createContext, useContext, useState, useCallback, useEffect } from 'react';
import { setAuthToken, getAuthToken, apiLogin, apiSignup, apiGetMe, apiUpdateMe } from '../services/api';

const DEFAULT_PREFERENCES = {
  programme_stage_assumption: 'auto',
  reporting_posture: 'conservative',
  show_confidence_indicators: true,
  expand_assurance_by_default: false,
  always_show_contract_excerpts: false,
  always_show_activity_names: true,
  default_report_format: 'pdf',
  auto_download_report: false,
  include_user_notes_by_default: true,
  include_timestamps_authorship: true,
  confidentiality_mode: false,
};

function mapUserFromApi(apiUser) {
  if (!apiUser) return null;
  const prefs = apiUser.preferences && typeof apiUser.preferences === 'object'
    ? { ...DEFAULT_PREFERENCES, ...apiUser.preferences }
    : DEFAULT_PREFERENCES;
  return {
    id: apiUser.id,
    email: apiUser.email || '',
    name: apiUser.name || '',
    organisation: apiUser.organisation || '',
    role: apiUser.role || 'Consultant',
    timezone: apiUser.timezone || 'UTC',
    reportNamingPreference: apiUser.report_naming_preference || 'contract_date_validation',
    dataRetentionDays: apiUser.data_retention_days ?? 365,
    organisationLogoUrl: apiUser.organisation_logo_url ?? null,
    preferences: prefs,
  };
}

const AuthContext = createContext(null);

export function AuthProvider({ children }) {
  const [user, setUserState] = useState(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const token = getAuthToken();
    if (!token) {
      setLoading(false);
      return;
    }
    apiGetMe()
      .then((data) => {
        if (data) {
          setUserState(mapUserFromApi(data));
        } else {
          setAuthToken(null);
        }
      })
      .catch(() => {
        setAuthToken(null);
      })
      .finally(() => {
        setLoading(false);
      });
  }, []);

  const login = useCallback(async (email, password) => {
    if (!email || !password) {
      throw new Error('Please enter your email and password.');
    }
    const data = await apiLogin(email, password);
    setAuthToken(data.access_token);
    setUserState(mapUserFromApi(data.user));
    return mapUserFromApi(data.user);
  }, []);

  const signup = useCallback(async (email, password, name, organisation) => {
    if (!email || !password) {
      throw new Error('Please enter your email and password.');
    }
    if (password.length < 8) {
      throw new Error('Password must be at least 8 characters.');
    }
    const data = await apiSignup(email, password, name, organisation);
    setAuthToken(data.access_token);
    setUserState(mapUserFromApi(data.user));
    return mapUserFromApi(data.user);
  }, []);

  const logout = useCallback(() => {
    setAuthToken(null);
    setUserState(null);
  }, []);

  const updateProfile = useCallback(async (updates) => {
    const payload = {};
    if (updates.name !== undefined) payload.name = updates.name;
    if (updates.organisation !== undefined) payload.organisation = updates.organisation;
    if (updates.role !== undefined) payload.role = updates.role;
    if (updates.timezone !== undefined) payload.timezone = updates.timezone;
    if (updates.reportNamingPreference !== undefined) payload.report_naming_preference = updates.reportNamingPreference;
    if (updates.dataRetentionDays !== undefined) payload.data_retention_days = updates.dataRetentionDays;
    if (updates.organisationLogoUrl !== undefined) payload.organisation_logo_url = updates.organisationLogoUrl;
    if (updates.preferences !== undefined) payload.preferences = updates.preferences;
    const data = await apiUpdateMe(payload);
    setUserState(mapUserFromApi(data));
    return mapUserFromApi(data);
  }, []);

  const value = {
    user,
    loading,
    login,
    signup,
    logout,
    updateProfile,
    isAuthenticated: !!user,
  };

  return (
    <AuthContext.Provider value={value}>
      {children}
    </AuthContext.Provider>
  );
}

export function useAuth() {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error('useAuth must be used within AuthProvider');
  return ctx;
}
