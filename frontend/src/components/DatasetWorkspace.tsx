import React from 'react';
import { useQuery, useMutation } from '@tanstack/react-query';
import { useDatasetStore, WorkspaceTab } from '../store/datasetStore';
import { api } from '../api/client';
import { ProfileView } from './ProfileView';
import { ProposalsView } from './ProposalsView';
import { DashboardView } from './DashboardView';
import { QueryView } from './QueryView';
import { ExportView } from './ExportView';
import {
  FileSpreadsheet,
  BarChart3,
  Terminal,
  Download,
  Layers,
  CheckCircle2,
  AlertCircle,
  RefreshCw,
} from 'lucide-react';

interface DatasetWorkspaceProps {
  datasetId: string;
}

export const DatasetWorkspace: React.FC<DatasetWorkspaceProps> = ({ datasetId }) => {
  const { activeTab, setActiveTab, showToast } = useDatasetStore();

  // Queries
  const { data: dataset, isLoading: isDatasetLoading, refetch: refetchDataset } = useQuery({
    queryKey: ['dataset', datasetId],
    queryFn: () => api.getDataset(datasetId),
  });

  const { data: profile, refetch: refetchProfile } = useQuery({
    queryKey: ['profile', datasetId],
    queryFn: () => api.getProfile(datasetId).catch(() => null),
  });

  const { data: sampleData, refetch: refetchSample } = useQuery({
    queryKey: ['sample', datasetId],
    queryFn: () => api.getSample(datasetId).catch(() => null),
  });

  const { data: proposals = [], refetch: refetchProposals } = useQuery({
    queryKey: ['proposals', datasetId],
    queryFn: () => api.getProposals(datasetId).catch(() => []),
  });

  const { data: dashboardData, isLoading: isDashboardLoading, refetch: refetchDashboard } = useQuery({
    queryKey: ['dashboard', datasetId],
    queryFn: () => api.getDashboard(datasetId).catch(() => null),
  });

  // Mutations
  const ingestMutation = useMutation({
    mutationFn: () => api.triggerIngest(datasetId),
    onSuccess: () => {
      showToast('Ingestion and profiling completed successfully', 'success');
      refetchDataset();
      refetchProfile();
      refetchSample();
    },
    onError: (err: any) => {
      showToast(err.message || 'Ingestion failed', 'error');
    },
  });

  const generateProposalsMutation = useMutation({
    mutationFn: () => api.generateProposals(datasetId),
    onSuccess: (data) => {
      showToast(`Generated ${data.length} cleaning proposals`, 'success');
      refetchProposals();
      refetchDataset();
    },
    onError: (err: any) => {
      showToast(err.message || 'Proposal generation failed', 'error');
    },
  });

  const updateProposalMutation = useMutation({
    mutationFn: ({ id, status }: { id: string; status: 'accepted' | 'rejected' }) =>
      api.updateProposal(datasetId, id, status),
    onSuccess: () => {
      refetchProposals();
    },
    onError: (err: any) => {
      showToast(err.message || 'Failed to update proposal', 'error');
    },
  });

  const bulkAcceptMutation = useMutation({
    mutationFn: (ids: string[]) => api.bulkUpdateProposals(datasetId, ids, 'accepted'),
    onSuccess: () => {
      showToast('All proposals accepted', 'success');
      refetchProposals();
    },
    onError: (err: any) => {
      showToast(err.message || 'Bulk update failed', 'error');
    },
  });

  const applyCleaningMutation = useMutation({
    mutationFn: () => api.applyCleaning(datasetId),
    onSuccess: () => {
      showToast('Cleaning applied successfully! Created Version 2 (Cleaned)', 'success');
      refetchDataset();
      refetchProfile();
      refetchSample();
      refetchDashboard();
      setActiveTab('insights');
    },
    onError: (err: any) => {
      showToast(err.message || 'Apply cleaning failed', 'error');
    },
  });

  if (isDatasetLoading) {
    return (
      <div className="flex min-h-[50vh] flex-col items-center justify-center text-slate-400">
        <div className="h-8 w-8 animate-spin rounded-full border-2 border-sky-500 border-t-transparent" />
        <p className="mt-3 text-xs">Loading dataset workspace...</p>
      </div>
    );
  }

  if (!dataset) {
    return (
      <div className="mx-auto max-w-7xl px-4 py-12 text-center text-slate-400">
        <AlertCircle className="mx-auto h-12 w-12 text-rose-500" />
        <h3 className="mt-4 text-base font-semibold text-white">Dataset Not Found</h3>
        <p className="mt-1 text-xs">The requested dataset could not be retrieved.</p>
      </div>
    );
  }

  const latestVersion = dataset.versions?.[dataset.versions.length - 1];
  const isCleaned = dataset.status === 'cleaned' || latestVersion?.kind === 'cleaned';

  const tabs = [
    { id: 'profile', label: 'Profile & Quality', icon: FileSpreadsheet },
    {
      id: 'proposals',
      label: 'Cleaning Proposals',
      icon: Layers,
      badge: proposals.length > 0 ? proposals.length : undefined,
    },
    { id: 'insights', label: 'Visual Insights & KPIs', icon: BarChart3 },
    { id: 'query', label: 'Safe SQL Explorer', icon: Terminal },
    { id: 'exports', label: 'Exports & Reproducibility', icon: Download },
  ];

  const columnsList: string[] =
    profile?.column_profiles?.map((c: any) => c.name) ||
    sampleData?.columns ||
    [];

  return (
    <div className="mx-auto max-w-7xl px-4 py-8 sm:px-6 lg:px-8">
      {/* Workspace Header */}
      <div className="rounded-2xl border border-slate-200/90 bg-white/80 dark:border-slate-800 dark:bg-slate-900/60 p-6 shadow-sm dark:shadow-xl backdrop-blur-sm transition-colors duration-200">
        <div className="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
          <div>
            <div className="flex flex-wrap items-center gap-2.5">
              <h1 className="text-xl font-bold tracking-tight text-slate-900 dark:text-white sm:text-2xl">
                {dataset.name}
              </h1>
              {isCleaned ? (
                <span className="inline-flex items-center gap-1 rounded-full border border-emerald-500/30 bg-emerald-500/10 px-3 py-1 text-xs font-semibold text-emerald-600 dark:text-emerald-400">
                  <CheckCircle2 className="h-3.5 w-3.5" />
                  <span>Version 2: Cleaned & Normalized</span>
                </span>
              ) : (
                <span className="inline-flex items-center gap-1 rounded-full border border-sky-500/30 bg-sky-500/10 px-3 py-1 text-xs font-semibold text-sky-600 dark:text-sky-400">
                  <span>Version 1: Raw Ingest</span>
                </span>
              )}
            </div>

            <div className="mt-2 flex flex-wrap items-center gap-4 text-xs text-slate-500 dark:text-slate-400">
              <span>
                Source:{' '}
                <strong className="text-slate-700 dark:text-slate-300 font-mono">{dataset.source_filename}</strong>
              </span>
              <span>·</span>
              <span>
                Rows:{' '}
                <strong className="text-slate-700 dark:text-slate-300 font-mono">
                  {latestVersion?.row_count?.toLocaleString() || '—'}
                </strong>
              </span>
              <span>·</span>
              <span>
                Cols:{' '}
                <strong className="text-slate-700 dark:text-slate-300 font-mono">{latestVersion?.col_count || '—'}</strong>
              </span>
              {latestVersion?.sha256 && (
                <>
                  <span>·</span>
                  <span className="truncate max-w-[200px]" title={latestVersion.sha256}>
                    SHA-256:{' '}
                    <strong className="text-slate-600 dark:text-slate-400 font-mono">
                      {latestVersion.sha256.slice(0, 10)}...
                    </strong>
                  </span>
                </>
              )}
            </div>
          </div>

          <div className="flex items-center gap-2">
            <button
              onClick={() => ingestMutation.mutate()}
              disabled={ingestMutation.isPending}
              className="inline-flex items-center gap-1.5 rounded-xl border border-slate-200 bg-slate-50 px-3 py-2 text-xs font-medium text-slate-700 hover:bg-slate-100 dark:border-slate-700 dark:bg-slate-800 dark:text-slate-300 dark:hover:bg-slate-700 transition-colors disabled:opacity-50"
            >
              <RefreshCw className={`h-3.5 w-3.5 ${ingestMutation.isPending ? 'animate-spin' : ''}`} />
              <span>Re-Profile</span>
            </button>
          </div>
        </div>

        {/* Tab Navigation */}
        <div className="mt-6 flex flex-wrap gap-2 border-t border-slate-200 dark:border-slate-800/80 pt-4">
          {tabs.map((tab) => {
            const Icon = tab.icon;
            const isActive = activeTab === tab.id;
            return (
              <button
                key={tab.id}
                onClick={() => setActiveTab(tab.id as WorkspaceTab)}
                className={`flex items-center gap-2 rounded-xl px-4 py-2 text-xs font-semibold transition-all ${
                  isActive
                    ? 'bg-sky-500 text-white shadow-lg shadow-sky-500/20'
                    : 'border border-slate-200/90 bg-white text-slate-600 hover:bg-slate-50 hover:text-slate-900 dark:border-slate-800 dark:bg-slate-950/40 dark:text-slate-400 dark:hover:bg-slate-800/60 dark:hover:text-slate-200'
                }`}
              >
                <Icon className="h-4 w-4" />
                <span>{tab.label}</span>
                {tab.badge !== undefined && (
                  <span
                    className={`rounded-full px-1.5 py-0.2 text-[10px] ${
                      isActive ? 'bg-white/20 text-white' : 'bg-slate-100 text-slate-700 dark:bg-slate-800 dark:text-sky-400'
                    }`}
                  >
                    {tab.badge}
                  </span>
                )}
              </button>
            );
          })}
        </div>
      </div>

      {/* Tab Content */}
      <div className="mt-6">
        {activeTab === 'profile' && (
          <ProfileView
            profile={profile}
            sampleData={sampleData ?? null}
            onRunIngest={() => ingestMutation.mutate()}
            isProcessing={ingestMutation.isPending}
          />
        )}

        {activeTab === 'proposals' && (
          <ProposalsView
            proposals={proposals}
            onGenerateProposals={() => generateProposalsMutation.mutate()}
            onUpdateProposal={(id, status) => updateProposalMutation.mutate({ id, status })}
            onBulkAccept={() =>
              bulkAcceptMutation.mutate(proposals.map((p: any) => p.id))
            }
            onApplyCleaning={() => applyCleaningMutation.mutate()}
            isGenerating={generateProposalsMutation.isPending}
            isApplying={applyCleaningMutation.isPending}
            datasetStatus={dataset.status}
          />
        )}

        {activeTab === 'insights' && (
          <DashboardView
            dashboardData={dashboardData}
            isLoading={isDashboardLoading}
            onRefresh={() => refetchDashboard()}
          />
        )}

        {activeTab === 'query' && (
          <QueryView datasetId={datasetId} columns={columnsList} />
        )}

        {activeTab === 'exports' && (
          <ExportView
            datasetId={datasetId}
            datasetName={dataset.name}
            status={dataset.status}
          />
        )}
      </div>
    </div>
  );
};
