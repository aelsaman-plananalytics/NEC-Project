import React, { useState, useEffect } from 'react';
import { useAuth } from '../context/AuthContext';
import { apiDeleteAllRuns, apiExportRuns } from '../services/api';

const ROLES = [
  { value: 'Client', label: 'Client' },
  { value: 'Contractor', label: 'Contractor' },
  { value: 'Consultant', label: 'Consultant' },
];

const PROGRAMME_STAGE_OPTIONS = [
  { value: 'auto', label: 'Auto-detect (default)' },
  { value: 'early', label: 'Early-stage' },
  { value: 'design', label: 'Design-stage' },
  { value: 'construction', label: 'Construction-stage' },
];

const REPORTING_POSTURE_OPTIONS = [
  { value: 'conservative', label: 'Conservative (default)' },
  { value: 'neutral', label: 'Neutral' },
  { value: 'exploratory', label: 'Exploratory' },
];

const REPORT_NAMING_OPTIONS = [
  { value: 'contract_date_validation', label: 'Contract name + date + Programme Validation' },
  { value: 'date_only', label: 'Date only' },
  { value: 'custom', label: 'Custom (set per report)' },
];

const REPORT_FORMAT_OPTIONS = [
  { value: 'pdf', label: 'PDF' },
  { value: 'docx', label: 'DOCX' },
];

export default function AccountSettings() {
  const { user, updateProfile } = useAuth();
  const [saved, setSaved] = useState(false);
  const [error, setError] = useState('');
  const [profile, setProfile] = useState({
    name: '',
    organisation: '',
    role: 'Consultant',
    timezone: 'UTC',
    organisationLogoUrl: '',
  });
  const [preferences, setPreferences] = useState({
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
  });
  const [reportNamingPreference, setReportNamingPreference] = useState('contract_date_validation');
  const [dataRetentionDays, setDataRetentionDays] = useState(365);
  const [dataAction, setDataAction] = useState({ type: null, loading: false, message: '' });
  const [activeTab, setActiveTab] = useState('profile');

  const TABS = [
    { id: 'profile', label: 'Profile & organisation' },
    { id: 'analysis', label: 'Analysis & interpretation' },
    { id: 'evidence', label: 'Evidence & transparency' },
    { id: 'reporting', label: 'Reporting & output' },
    { id: 'data', label: 'Data & privacy' },
  ];

  useEffect(() => {
    if (!user) return;
    setProfile({
      name: user.name ?? '',
      organisation: user.organisation ?? '',
      role: user.role ?? 'Consultant',
      timezone: user.timezone ?? ((typeof Intl !== 'undefined' && Intl.DateTimeFormat?.().resolvedOptions?.().timeZone) || 'UTC'),
      organisationLogoUrl: user.organisationLogoUrl ?? '',
    });
    setPreferences((prev) => ({ ...prev, ...(user.preferences || {}) }));
    setReportNamingPreference(user.reportNamingPreference ?? 'contract_date_validation');
    setDataRetentionDays(user.dataRetentionDays ?? 365);
  }, [user]);

  const handleSubmit = async (e) => {
    e.preventDefault();
    setError('');
    try {
      await updateProfile({
        ...profile,
        organisationLogoUrl: profile.organisationLogoUrl || null,
        reportNamingPreference,
        dataRetentionDays: Number(dataRetentionDays) || 365,
        preferences,
      });
      setSaved(true);
      setTimeout(() => setSaved(false), 3000);
    } catch (err) {
      setError(err.message || 'Failed to save.');
    }
  };

  const handleDeleteAllData = async () => {
    if (!window.confirm('Delete all your analysis runs? This cannot be undone.')) return;
    setDataAction({ type: 'deleteAll', loading: true, message: '' });
    try {
      await apiDeleteAllRuns();
      setDataAction({ type: 'deleteAll', loading: false, message: 'All analyses deleted.' });
    } catch (err) {
      setDataAction({ type: 'deleteAll', loading: false, message: err.message || 'Failed to delete.' });
    }
  };

  const handleExportHistory = async () => {
    setDataAction({ type: 'export', loading: true, message: '' });
    try {
      const data = await apiExportRuns();
      const blob = new Blob([JSON.stringify(data, null, 2)], { type: 'application/json' });
      const url = URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = `analysis_history_${new Date().toISOString().slice(0, 10)}.json`;
      a.click();
      URL.revokeObjectURL(url);
      setDataAction({ type: 'export', loading: false, message: 'Export downloaded.' });
    } catch (err) {
      setDataAction({ type: 'export', loading: false, message: err.message || 'Export failed.' });
    }
  };

  const setPref = (key, value) => {
    setPreferences((p) => ({ ...p, [key]: value }));
  };

  if (!user) return null;

  return (
    <div className="max-w-2xl mx-auto px-4 py-8">
      <h1 className="font-heading text-2xl font-bold text-slate-900 mb-2">User settings</h1>
      <p className="text-slate-600 text-sm mb-8">
        Control presentation, reporting, and workflow. These settings do not change validation or acceptability outcomes.
      </p>

      <form onSubmit={handleSubmit} className="space-y-6">
        {error && (
          <div className="p-3 rounded-lg bg-red-50 border border-red-200 text-red-800 text-sm">{error}</div>
        )}
        {saved && (
          <div className="p-3 rounded-lg bg-green-50 border border-green-200 text-green-800 text-sm">
            Settings saved.
          </div>
        )}

        {/* Tab bar */}
        <div className="border-b border-slate-200">
          <nav className="flex flex-wrap gap-1 -mb-px" aria-label="Settings sections">
            {TABS.map((tab) => (
              <button
                key={tab.id}
                type="button"
                onClick={() => setActiveTab(tab.id)}
                className={`px-4 py-3 text-sm font-medium border-b-2 transition-colors ${
                  activeTab === tab.id
                    ? 'border-amber-500 text-amber-700'
                    : 'border-transparent text-slate-600 hover:text-slate-800 hover:border-slate-300'
                }`}
              >
                {tab.label}
              </button>
            ))}
          </nav>
        </div>

        {/* 1. Profile & Organisation */}
        {activeTab === 'profile' && (
        <section className="pb-6">
          <h2 className="font-heading text-lg font-semibold text-slate-800 mb-4">Profile & organisation</h2>
          <div className="space-y-4">
            <div>
              <label className="block text-sm font-medium text-slate-700 mb-1">Email</label>
              <p className="text-slate-600">{user.email}</p>
            </div>
            <div>
              <label htmlFor="acc-name" className="block text-sm font-medium text-slate-700 mb-1">Name</label>
              <input
                id="acc-name"
                type="text"
                value={profile.name}
                onChange={(e) => setProfile((p) => ({ ...p, name: e.target.value }))}
                className="w-full px-4 py-2 rounded-lg border border-slate-300 focus:ring-2 focus:ring-amber-500 focus:border-amber-500"
              />
            </div>
            <div>
              <label htmlFor="acc-org" className="block text-sm font-medium text-slate-700 mb-1">Organisation</label>
              <input
                id="acc-org"
                type="text"
                value={profile.organisation}
                onChange={(e) => setProfile((p) => ({ ...p, organisation: e.target.value }))}
                className="w-full px-4 py-2 rounded-lg border border-slate-300 focus:ring-2 focus:ring-amber-500 focus:border-amber-500"
              />
            </div>
            <div>
              <label htmlFor="acc-role" className="block text-sm font-medium text-slate-700 mb-1">Role</label>
              <select
                id="acc-role"
                value={profile.role}
                onChange={(e) => setProfile((p) => ({ ...p, role: e.target.value }))}
                className="w-full px-4 py-2 rounded-lg border border-slate-300 focus:ring-2 focus:ring-amber-500 focus:border-amber-500"
              >
                {ROLES.map((r) => (
                  <option key={r.value} value={r.value}>{r.label}</option>
                ))}
              </select>
            </div>
            <div>
              <label htmlFor="acc-timezone" className="block text-sm font-medium text-slate-700 mb-1">Timezone</label>
              <input
                id="acc-timezone"
                type="text"
                value={profile.timezone}
                onChange={(e) => setProfile((p) => ({ ...p, timezone: e.target.value }))}
                className="w-full px-4 py-2 rounded-lg border border-slate-300 focus:ring-2 focus:ring-amber-500 focus:border-amber-500"
                placeholder="Europe/London"
              />
            </div>
            <div>
              <label htmlFor="acc-logo" className="block text-sm font-medium text-slate-700 mb-1">Organisation logo (URL, optional)</label>
              <input
                id="acc-logo"
                type="url"
                value={profile.organisationLogoUrl}
                onChange={(e) => setProfile((p) => ({ ...p, organisationLogoUrl: e.target.value }))}
                className="w-full px-4 py-2 rounded-lg border border-slate-300 focus:ring-2 focus:ring-amber-500 focus:border-amber-500"
                placeholder="https://…"
              />
              <p className="text-slate-500 text-xs mt-1">Used in reports if provided.</p>
            </div>
          </div>
        </section>
        )}

        {/* 2. Analysis & Interpretation Preferences */}
        {activeTab === 'analysis' && (
        <section className="pb-6">
          <h2 className="font-heading text-lg font-semibold text-slate-800 mb-2">Analysis & interpretation preferences</h2>
          <p className="text-slate-600 text-sm mb-4">Affects wording and emphasis only. Does not change acceptability outcomes.</p>
          <div className="space-y-4">
            <div>
              <label className="block text-sm font-medium text-slate-700 mb-2">Programme stage assumption</label>
              <select
                value={preferences.programme_stage_assumption}
                onChange={(e) => setPref('programme_stage_assumption', e.target.value)}
                className="w-full px-4 py-2 rounded-lg border border-slate-300 focus:ring-2 focus:ring-amber-500 focus:border-amber-500"
              >
                {PROGRAMME_STAGE_OPTIONS.map((o) => (
                  <option key={o.value} value={o.value}>{o.label}</option>
                ))}
              </select>
            </div>
            <div>
              <label className="block text-sm font-medium text-slate-700 mb-2">Reporting posture</label>
              <select
                value={preferences.reporting_posture}
                onChange={(e) => setPref('reporting_posture', e.target.value)}
                className="w-full px-4 py-2 rounded-lg border border-slate-300 focus:ring-2 focus:ring-amber-500 focus:border-amber-500"
              >
                {REPORTING_POSTURE_OPTIONS.map((o) => (
                  <option key={o.value} value={o.value}>{o.label}</option>
                ))}
              </select>
              <p className="text-slate-500 text-xs mt-1">Influences guidance tone; does not change decisions.</p>
            </div>
          </div>
        </section>
        )}

        {/* 3. Evidence & Transparency */}
        {activeTab === 'evidence' && (
        <section className="pb-6">
          <h2 className="font-heading text-lg font-semibold text-slate-800 mb-2">Evidence & transparency</h2>
          <p className="text-slate-600 text-sm mb-4">Control how much detail is shown by default. Defaults favour clarity.</p>
          <div className="space-y-3">
            <label className="flex items-center gap-3">
              <input
                type="checkbox"
                checked={!!preferences.show_confidence_indicators}
                onChange={(e) => setPref('show_confidence_indicators', e.target.checked)}
                className="rounded border-slate-300 text-amber-600 focus:ring-amber-500"
              />
              <span className="text-slate-700">Show confidence indicators</span>
            </label>
            <label className="flex items-center gap-3">
              <input
                type="checkbox"
                checked={!!preferences.expand_assurance_by_default}
                onChange={(e) => setPref('expand_assurance_by_default', e.target.checked)}
                className="rounded border-slate-300 text-amber-600 focus:ring-amber-500"
              />
              <span className="text-slate-700">Expand assurance-based explanations by default</span>
            </label>
            <label className="flex items-center gap-3">
              <input
                type="checkbox"
                checked={!!preferences.always_show_contract_excerpts}
                onChange={(e) => setPref('always_show_contract_excerpts', e.target.checked)}
                className="rounded border-slate-300 text-amber-600 focus:ring-amber-500"
              />
              <span className="text-slate-700">Always show contract excerpts</span>
            </label>
            <label className="flex items-center gap-3">
              <input
                type="checkbox"
                checked={!!preferences.always_show_activity_names}
                onChange={(e) => setPref('always_show_activity_names', e.target.checked)}
                className="rounded border-slate-300 text-amber-600 focus:ring-amber-500"
              />
              <span className="text-slate-700">Always show programme activity names</span>
            </label>
          </div>
        </section>
        )}

        {/* 4. Reporting & Output */}
        {activeTab === 'reporting' && (
        <section className="pb-6">
          <h2 className="font-heading text-lg font-semibold text-slate-800 mb-2">Reporting & output</h2>
          <div className="space-y-4">
            <div>
              <label className="block text-sm font-medium text-slate-700 mb-2">Default report format</label>
              <div className="flex gap-4">
                {REPORT_FORMAT_OPTIONS.map((o) => (
                  <label key={o.value} className="flex items-center gap-2">
                    <input
                      type="radio"
                      name="reportFormat"
                      value={o.value}
                      checked={preferences.default_report_format === o.value}
                      onChange={() => setPref('default_report_format', o.value)}
                    />
                    <span className="text-slate-700">{o.label}</span>
                  </label>
                ))}
              </div>
            </div>
            <div>
              <label className="block text-sm font-medium text-slate-700 mb-2">Report naming convention</label>
              <div className="space-y-2">
                {REPORT_NAMING_OPTIONS.map((opt) => (
                  <label key={opt.value} className="flex items-center gap-2">
                    <input
                      type="radio"
                      name="reportNaming"
                      value={opt.value}
                      checked={reportNamingPreference === opt.value}
                      onChange={() => setReportNamingPreference(opt.value)}
                    />
                    <span className="text-slate-700">{opt.label}</span>
                  </label>
                ))}
              </div>
            </div>
            <div className="space-y-3">
              <label className="flex items-center gap-3">
                <input
                  type="checkbox"
                  checked={!!preferences.auto_download_report}
                  onChange={(e) => setPref('auto_download_report', e.target.checked)}
                  className="rounded border-slate-300 text-amber-600 focus:ring-amber-500"
                />
                <span className="text-slate-700">Auto-download after generation</span>
              </label>
              <label className="flex items-center gap-3">
                <input
                  type="checkbox"
                  checked={!!preferences.include_user_notes_by_default}
                  onChange={(e) => setPref('include_user_notes_by_default', e.target.checked)}
                  className="rounded border-slate-300 text-amber-600 focus:ring-amber-500"
                />
                <span className="text-slate-700">Include user notes by default</span>
              </label>
              <label className="flex items-center gap-3">
                <input
                  type="checkbox"
                  checked={!!preferences.include_timestamps_authorship}
                  onChange={(e) => setPref('include_timestamps_authorship', e.target.checked)}
                  className="rounded border-slate-300 text-amber-600 focus:ring-amber-500"
                />
                <span className="text-slate-700">Include timestamps and authorship in reports</span>
              </label>
            </div>
          </div>
        </section>
        )}

        {/* 5. Data & Privacy */}
        {activeTab === 'data' && (
        <section className="pb-6">
          <h2 className="font-heading text-lg font-semibold text-slate-800 mb-2">Data & privacy</h2>
          <div className="space-y-4">
            <div>
              <label htmlFor="acc-retention" className="block text-sm font-medium text-slate-700 mb-1">Data retention (days)</label>
              <input
                id="acc-retention"
                type="number"
                min={30}
                max={3650}
                value={dataRetentionDays}
                onChange={(e) => setDataRetentionDays(e.target.value)}
                className="w-full px-4 py-2 rounded-lg border border-slate-300 focus:ring-2 focus:ring-amber-500 focus:border-amber-500 max-w-[120px]"
              />
              <p className="text-slate-500 text-xs mt-1">How long to keep analyses and reports (30–3650 days).</p>
            </div>
            <div>
              <label className="flex items-center gap-3">
                <input
                  type="checkbox"
                  checked={!!preferences.confidentiality_mode}
                  onChange={(e) => setPref('confidentiality_mode', e.target.checked)}
                  className="rounded border-slate-300 text-amber-600 focus:ring-amber-500"
                />
                <span className="text-slate-700">Confidentiality mode (redact sensitive activity names in reports)</span>
              </label>
            </div>
            <div className="pt-4 space-y-2">
              <p className="text-sm font-medium text-slate-700">Data actions</p>
              <p className="text-slate-500 text-xs">Individual analyses can be removed from the Dashboard.</p>
              {dataAction.message && (
                <p className={`text-sm ${dataAction.message.startsWith('Failed') ? 'text-red-600' : 'text-green-700'}`}>
                  {dataAction.message}
                </p>
              )}
              <div className="flex flex-wrap gap-2">
                <button
                  type="button"
                  onClick={handleExportHistory}
                  disabled={dataAction.loading}
                  className="px-4 py-2 rounded-lg border border-slate-300 text-slate-700 text-sm font-medium hover:bg-slate-50 disabled:opacity-50"
                >
                  {dataAction.loading && dataAction.type === 'export' ? 'Exporting…' : 'Export analysis history'}
                </button>
                <button
                  type="button"
                  onClick={handleDeleteAllData}
                  disabled={dataAction.loading}
                  className="px-4 py-2 rounded-lg border border-red-200 text-red-700 text-sm font-medium hover:bg-red-50 disabled:opacity-50"
                >
                  {dataAction.loading && dataAction.type === 'deleteAll' ? 'Deleting…' : 'Delete all analyses'}
                </button>
              </div>
            </div>
          </div>
        </section>
        )}

        <div className="pt-4">
          <button
            type="submit"
            className="py-3 px-6 rounded-lg bg-amber-500 text-slate-900 font-semibold hover:bg-amber-400 transition-colors"
          >
            Save changes
          </button>
        </div>
      </form>
    </div>
  );
}
