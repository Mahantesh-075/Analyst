import React, { useState } from 'react';
import {
  Sparkles,
  CheckCircle2,
  XCircle,
  Play,
  CheckCheck,
  Layers,
  ArrowRight,
  Shield,
} from 'lucide-react';

interface ProposalsViewProps {
  proposals: any[];
  onGenerateProposals: () => void;
  onUpdateProposal: (id: string, status: 'accepted' | 'rejected') => void;
  onBulkAccept: () => void;
  onApplyCleaning: () => void;
  isGenerating: boolean;
  isApplying: boolean;
  datasetStatus: string;
}

export const ProposalsView: React.FC<ProposalsViewProps> = ({
  proposals,
  onGenerateProposals,
  onUpdateProposal,
  onBulkAccept,
  onApplyCleaning,
  isGenerating,
  isApplying,
  datasetStatus,
}) => {
  const [filter, setFilter] = useState<'all' | 'accepted' | 'rejected' | 'pending'>('all');

  const acceptedCount = proposals.filter((p) => p.status === 'accepted').length;
  const pendingCount = proposals.filter((p) => p.status === 'pending').length;

  const filteredProposals = proposals.filter((p) => {
    if (filter === 'all') return true;
    return p.status === filter;
  });

  const getSeverityBadge = (severity: string) => {
    switch (severity?.toLowerCase()) {
      case 'high':
        return (
          <span className="rounded-full border border-rose-500/30 bg-rose-500/10 px-2 py-0.5 text-[10px] font-semibold text-rose-400">
            HIGH PRIORITY
          </span>
        );
      case 'medium':
        return (
          <span className="rounded-full border border-amber-500/30 bg-amber-500/10 px-2 py-0.5 text-[10px] font-semibold text-amber-400">
            MEDIUM
          </span>
        );
      default:
        return (
          <span className="rounded-full border border-sky-500/30 bg-sky-500/10 px-2 py-0.5 text-[10px] font-semibold text-sky-400">
            LOW
          </span>
        );
    }
  };

  return (
    <div className="space-y-6">
      {/* Top Action Bar */}
      <div className="flex flex-col gap-4 rounded-2xl border border-slate-200/90 bg-white/80 p-5 shadow-sm backdrop-blur-sm dark:border-slate-800 dark:bg-slate-900/60 sm:flex-row sm:items-center sm:justify-between transition-colors duration-200">
        <div>
          <h2 className="text-base font-bold text-slate-900 dark:text-white flex items-center gap-2">
            <Layers className="h-5 w-5 text-sky-500 dark:text-sky-400" />
            <span>Closed-Registry Cleaning Proposals (Invariant 1 & 4)</span>
          </h2>
          <p className="mt-0.5 text-xs text-slate-500 dark:text-slate-400">
            Every transformation is vetted and requires human approval before being applied to produce Version 2.
          </p>
        </div>

        <div className="flex flex-wrap items-center gap-2.5">
          {proposals.length === 0 ? (
            <button
              onClick={onGenerateProposals}
              disabled={isGenerating}
              className="inline-flex items-center gap-1.5 rounded-xl bg-gradient-to-r from-sky-500 to-indigo-600 px-4 py-2 text-xs font-semibold text-white shadow-lg shadow-sky-500/20 hover:from-sky-400 hover:to-indigo-500 active:scale-95 transition-all disabled:opacity-50"
            >
              <Sparkles className="h-4 w-4" />
              <span>{isGenerating ? 'Synthesizing Proposals...' : 'Generate Proposals'}</span>
            </button>
          ) : (
            <>
              {pendingCount > 0 && (
                <button
                  onClick={onBulkAccept}
                  className="inline-flex items-center gap-1.5 rounded-xl border border-emerald-500/40 bg-emerald-500/10 px-3.5 py-2 text-xs font-semibold text-emerald-600 hover:bg-emerald-500/20 dark:text-emerald-400 active:scale-95 transition-all"
                >
                  <CheckCheck className="h-4 w-4" />
                  <span>Accept All ({proposals.length})</span>
                </button>
              )}

              <button
                onClick={onApplyCleaning}
                disabled={isApplying || acceptedCount === 0}
                className="inline-flex items-center gap-1.5 rounded-xl bg-gradient-to-r from-emerald-500 to-teal-600 px-4 py-2 text-xs font-semibold text-white shadow-lg shadow-emerald-500/20 hover:from-emerald-400 hover:to-teal-500 active:scale-95 transition-all disabled:opacity-50"
              >
                <Play className="h-4 w-4 fill-white" />
                <span>
                  {isApplying
                    ? 'Executing Pipeline...'
                    : datasetStatus === 'cleaned'
                    ? `Re-apply Plan (${acceptedCount} Accepted)`
                    : `Apply Cleaning Plan (${acceptedCount} Accepted)`}
                </span>
              </button>
            </>
          )}
        </div>
      </div>

      {datasetStatus === 'cleaned' && (
        <div className="flex items-center justify-between rounded-xl border border-emerald-500/30 bg-emerald-500/10 px-4 py-3 text-xs text-emerald-700 dark:text-emerald-300">
          <div className="flex items-center gap-2">
            <CheckCircle2 className="h-4 w-4 text-emerald-500 dark:text-emerald-400 shrink-0" />
            <span>
              <strong>Version 2 (Cleaned) is live!</strong> Transformations have been atomically committed into immutable Parquet storage.
            </span>
          </div>
          <span className="font-semibold text-emerald-600 dark:text-emerald-400">100% Reproducible</span>
        </div>
      )}

      {/* Filter Tabs */}
      {proposals.length > 0 && (
        <div className="flex items-center gap-2 border-b border-slate-200 dark:border-slate-800 pb-2">
          {(['all', 'pending', 'accepted', 'rejected'] as const).map((tab) => (
            <button
              key={tab}
              onClick={() => setFilter(tab)}
              className={`rounded-lg px-3 py-1.5 text-xs font-medium capitalize transition-all ${
                filter === tab
                  ? 'bg-slate-100 text-sky-600 shadow-sm dark:bg-slate-800 dark:text-sky-400'
                  : 'text-slate-500 hover:text-slate-800 dark:text-slate-400 dark:hover:text-slate-200'
              }`}
            >
              {tab} (
              {tab === 'all'
                ? proposals.length
                : proposals.filter((p) => p.status === tab).length}
              )
            </button>
          ))}
        </div>
      )}

      {/* Proposals List */}
      {proposals.length === 0 ? (
        <div className="flex flex-col items-center justify-center rounded-2xl border border-slate-200 bg-white/70 dark:border-slate-800 dark:bg-slate-900/40 p-12 text-center shadow-sm">
          <Sparkles className="h-10 w-10 text-sky-500 dark:text-sky-400 animate-pulse" />
          <h3 className="mt-3 text-base font-semibold text-slate-900 dark:text-white">No Cleaning Proposals Yet</h3>
          <p className="mt-1 max-w-sm text-xs text-slate-500 dark:text-slate-400">
            Click &quot;Generate Proposals&quot; to invoke our deterministic rule engine and safe semantic analysis for automated defect remediation.
          </p>
          <button
            onClick={onGenerateProposals}
            disabled={isGenerating}
            className="mt-5 rounded-xl bg-sky-500 px-4 py-2 text-xs font-semibold text-white hover:bg-sky-400 active:scale-95 transition-all disabled:opacity-50"
          >
            {isGenerating ? 'Synthesizing...' : 'Generate Cleaning Proposals'}
          </button>
        </div>
      ) : (
        <div className="space-y-3">
          {filteredProposals.map((prop) => {
            const isAccepted = prop.status === 'accepted';
            const isRejected = prop.status === 'rejected';

            return (
              <div
                key={prop.id}
                className={`rounded-2xl border p-5 transition-all ${
                  isAccepted
                    ? 'border-emerald-500/40 bg-emerald-500/5 dark:bg-emerald-950/10'
                    : isRejected
                    ? 'border-slate-200 bg-slate-50/50 opacity-60 dark:border-slate-800 dark:bg-slate-900/30'
                    : 'border-slate-200/90 bg-white/80 shadow-sm hover:border-slate-300 dark:border-slate-800 dark:bg-slate-900/60 dark:hover:border-slate-700'
                }`}
              >
                <div className="flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
                  <div className="flex items-start gap-3">
                    <div className="flex h-9 w-9 shrink-0 items-center justify-center rounded-xl bg-slate-100 text-sky-600 dark:bg-slate-800 dark:text-sky-400">
                      <Shield className="h-5 w-5" />
                    </div>
                    <div>
                      <div className="flex flex-wrap items-center gap-2">
                        <span className="font-mono text-xs font-bold text-slate-900 bg-slate-100 dark:text-white dark:bg-slate-800 px-2 py-0.5 rounded-md border border-slate-200 dark:border-transparent">
                          {prop.op}
                        </span>
                        {getSeverityBadge(prop.severity)}
                        <span className="text-[10px] text-slate-500 dark:text-slate-400">
                          Confidence: {Math.round((prop.confidence || 0.95) * 100)}%
                        </span>
                      </div>
                      <p className="mt-1.5 text-xs text-slate-700 dark:text-slate-300 font-medium">{prop.reason || prop.rationale}</p>
                    </div>
                  </div>

                  {/* Accept / Reject Buttons */}
                  <div className="flex items-center gap-2 self-end sm:self-start">
                    <button
                      onClick={() => onUpdateProposal(prop.id, 'accepted')}
                      className={`flex items-center gap-1 rounded-lg px-3 py-1.5 text-xs font-semibold transition-all ${
                        isAccepted
                          ? 'bg-emerald-500 text-white shadow-sm'
                          : 'border border-emerald-500/30 bg-emerald-500/10 text-emerald-600 hover:bg-emerald-500/20 dark:text-emerald-400'
                      }`}
                    >
                      <CheckCircle2 className="h-3.5 w-3.5" />
                      <span>{isAccepted ? 'Accepted' : 'Accept'}</span>
                    </button>

                    <button
                      onClick={() => onUpdateProposal(prop.id, 'rejected')}
                      className={`flex items-center gap-1 rounded-lg px-3 py-1.5 text-xs font-semibold transition-all ${
                        isRejected
                          ? 'bg-slate-600 text-white dark:bg-slate-700'
                          : 'border border-slate-200 bg-slate-100 text-slate-600 hover:bg-slate-200 hover:text-slate-900 dark:border-slate-700 dark:bg-slate-800 dark:text-slate-400 dark:hover:bg-slate-700 dark:hover:text-slate-200'
                      }`}
                    >
                      <XCircle className="h-3.5 w-3.5" />
                      <span>{isRejected ? 'Rejected' : 'Reject'}</span>
                    </button>
                  </div>
                </div>

                {/* Impact Preview */}
                {prop.impact_preview && (
                  <div className="mt-4 rounded-xl border border-slate-200 bg-slate-50 p-3 dark:border-slate-800/80 dark:bg-slate-950/70">
                    <div className="flex flex-wrap items-center justify-between gap-2 text-[11px] text-slate-500 dark:text-slate-400 border-b border-slate-200 dark:border-slate-800/60 pb-2">
                      <div className="flex items-center gap-4">
                        <span>
                          Rows affected:{' '}
                          <strong className="text-slate-800 dark:text-slate-200">
                            {prop.impact_preview.rows_affected ?? prop.impact_preview.rows_changed ?? 0}
                          </strong>
                        </span>
                        <span>
                          Cells changed:{' '}
                          <strong className="text-slate-800 dark:text-slate-200">
                            {prop.impact_preview.cells_changed ?? 0}
                          </strong>
                        </span>
                      </div>
                      <span className="text-[10px] text-slate-400 dark:text-slate-500 uppercase tracking-wider font-semibold">
                        Preview Diff
                      </span>
                    </div>

                    {prop.impact_preview.sample_diff && prop.impact_preview.sample_diff.length > 0 && (
                      <div className="mt-2 space-y-1">
                        {prop.impact_preview.sample_diff.slice(0, 3).map((diff: any, dIdx: number) => (
                          <div key={dIdx} className="flex items-center gap-2 font-mono text-[11px]">
                            <span className="text-rose-600 dark:text-rose-400 line-through">
                              {diff.before !== null ? String(diff.before) : 'null'}
                            </span>
                            <ArrowRight className="h-3 w-3 text-slate-400 dark:text-slate-500 shrink-0" />
                            <span className="text-emerald-600 dark:text-emerald-400 font-semibold">
                              {diff.after !== null ? String(diff.after) : 'null'}
                            </span>
                          </div>
                        ))}
                      </div>
                    )}
                  </div>
                )}
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
};
