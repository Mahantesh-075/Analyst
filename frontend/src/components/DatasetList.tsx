import React from 'react';
import { Database, FileSpreadsheet, Plus, Sparkles, CheckCircle, Clock } from 'lucide-react';

interface DatasetListProps {
  datasets: any[];
  onSelectDataset: (id: string) => void;
  onOpenUpload: () => void;
  isLoading: boolean;
}

export const DatasetList: React.FC<DatasetListProps> = ({
  datasets,
  onSelectDataset,
  onOpenUpload,
  isLoading,
}) => {
  const getStatusBadge = (status: string) => {
    switch (status) {
      case 'cleaned':
        return (
          <span className="inline-flex items-center gap-1 rounded-full border border-emerald-500/30 bg-emerald-500/10 px-2.5 py-0.5 text-[10px] font-semibold text-emerald-400">
            <CheckCircle className="h-3 w-3" />
            <span>Cleaned (V2)</span>
          </span>
        );
      case 'profiled':
        return (
          <span className="inline-flex items-center gap-1 rounded-full border border-sky-500/30 bg-sky-500/10 px-2.5 py-0.5 text-[10px] font-semibold text-sky-400">
            <Sparkles className="h-3 w-3" />
            <span>Profiled</span>
          </span>
        );
      case 'review':
        return (
          <span className="inline-flex items-center gap-1 rounded-full border border-amber-500/30 bg-amber-500/10 px-2.5 py-0.5 text-[10px] font-semibold text-amber-400">
            <Clock className="h-3 w-3" />
            <span>In Review</span>
          </span>
        );
      default:
        return (
          <span className="inline-flex items-center gap-1 rounded-full border border-slate-200 bg-slate-100 dark:border-slate-700 dark:bg-slate-800 px-2.5 py-0.5 text-[10px] font-medium text-slate-700 dark:text-slate-300">
            <span>{status}</span>
          </span>
        );
    }
  };

  return (
    <div className="mx-auto max-w-7xl px-4 py-8 sm:px-6 lg:px-8">
      <div className="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
        <div>
          <h1 className="text-2xl font-bold tracking-tight text-slate-900 dark:text-white sm:text-3xl">
            Datasets & Data Pipelines
          </h1>
          <p className="mt-1 text-xs text-slate-500 dark:text-slate-400">
            Deterministic data profiling, closed-registry cleaning proposals, and zero-PII analytics.
          </p>
        </div>

        <button
          onClick={onOpenUpload}
          className="inline-flex items-center justify-center gap-2 rounded-xl bg-gradient-to-r from-sky-500 to-indigo-600 px-4 py-2.5 text-xs font-semibold text-white shadow-lg shadow-sky-500/20 hover:from-sky-400 hover:to-indigo-500 active:scale-95 transition-all"
        >
          <Plus className="h-4 w-4" />
          <span>Upload New Dataset</span>
        </button>
      </div>

      {isLoading ? (
        <div className="mt-12 flex flex-col items-center justify-center text-slate-500 dark:text-slate-400">
          <div className="h-8 w-8 animate-spin rounded-full border-2 border-sky-500 border-t-transparent" />
          <p className="mt-3 text-xs">Loading datasets...</p>
        </div>
      ) : datasets.length === 0 ? (
        <div className="mt-12 flex flex-col items-center justify-center rounded-2xl border border-dashed border-slate-300 bg-white/60 dark:border-slate-800 dark:bg-slate-900/40 p-12 text-center shadow-sm">
          <div className="flex h-14 w-14 items-center justify-center rounded-2xl bg-sky-500/10 text-sky-500 dark:text-sky-400 border border-sky-500/20">
            <FileSpreadsheet className="h-7 w-7" />
          </div>
          <h3 className="mt-4 text-base font-semibold text-slate-900 dark:text-white">No datasets uploaded yet</h3>
          <p className="mt-1.5 max-w-sm text-xs text-slate-500 dark:text-slate-400">
            Upload a CSV, XLSX, or Parquet file to trigger magic-byte inspection, deterministic profiling, and automated proposals.
          </p>
          <button
            onClick={onOpenUpload}
            className="mt-6 inline-flex items-center gap-2 rounded-xl bg-sky-500 px-4 py-2 text-xs font-semibold text-white hover:bg-sky-400 active:scale-95 transition-all shadow-md shadow-sky-500/20"
          >
            <Plus className="h-3.5 w-3.5" />
            <span>Upload Your First Dataset</span>
          </button>
        </div>
      ) : (
        <div className="mt-8 grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
          {datasets.map((ds) => {
            const latestVersion = ds.versions?.[ds.versions.length - 1];
            return (
              <div
                key={ds.id}
                onClick={() => onSelectDataset(ds.id)}
                className="group relative flex flex-col justify-between rounded-2xl border border-slate-200/90 bg-white/80 dark:border-slate-800 dark:bg-slate-900/60 p-5 shadow-sm backdrop-blur-sm transition-all hover:border-sky-500/50 hover:shadow-xl hover:shadow-sky-500/10 dark:hover:bg-slate-900/90 cursor-pointer"
              >
                <div>
                  <div className="flex items-start justify-between gap-3">
                    <div className="flex h-10 w-10 shrink-0 items-center justify-center rounded-xl bg-slate-100 text-sky-600 dark:bg-slate-800 dark:text-sky-400 group-hover:bg-sky-500/15 group-hover:text-sky-500 transition-colors">
                      <Database className="h-5 w-5" />
                    </div>
                    <div>{getStatusBadge(ds.status)}</div>
                  </div>

                  <h3 className="mt-4 text-base font-semibold text-slate-900 dark:text-white group-hover:text-sky-600 dark:group-hover:text-sky-300 transition-colors">
                    {ds.name}
                  </h3>
                  <p className="mt-1 text-xs text-slate-500 dark:text-slate-400 line-clamp-2">
                    {ds.description || ds.source_filename}
                  </p>
                </div>

                <div className="mt-6 border-t border-slate-100 dark:border-slate-800/80 pt-4">
                  <div className="grid grid-cols-3 gap-2 text-center">
                    <div className="rounded-lg bg-slate-50 dark:bg-slate-950/60 p-2 border border-slate-100 dark:border-transparent">
                      <div className="text-[10px] text-slate-400 dark:text-slate-500 uppercase font-medium">Rows</div>
                      <div className="mt-0.5 text-xs font-semibold text-slate-800 dark:text-slate-200">
                        {latestVersion?.row_count?.toLocaleString() || '—'}
                      </div>
                    </div>
                    <div className="rounded-lg bg-slate-50 dark:bg-slate-950/60 p-2 border border-slate-100 dark:border-transparent">
                      <div className="text-[10px] text-slate-400 dark:text-slate-500 uppercase font-medium">Cols</div>
                      <div className="mt-0.5 text-xs font-semibold text-slate-800 dark:text-slate-200">
                        {latestVersion?.col_count || '—'}
                      </div>
                    </div>
                    <div className="rounded-lg bg-slate-50 dark:bg-slate-950/60 p-2 border border-slate-100 dark:border-transparent">
                      <div className="text-[10px] text-slate-400 dark:text-slate-500 uppercase font-medium">Versions</div>
                      <div className="mt-0.5 text-xs font-semibold text-slate-800 dark:text-slate-200">
                        {ds.versions?.length || 1}
                      </div>
                    </div>
                  </div>

                  <div className="mt-3 flex items-center justify-between text-[11px] text-slate-500 dark:text-slate-400">
                    <span>{new Date(ds.created_at).toLocaleDateString()}</span>
                    <span className="text-sky-600 dark:text-sky-400 font-medium group-hover:underline">Open Workspace &rarr;</span>
                  </div>
                </div>
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
};
