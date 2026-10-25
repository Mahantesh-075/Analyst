import React, { useState } from 'react';
import { ShieldAlert, AlertTriangle, Hash, FileSpreadsheet, CheckCircle2, Eye, EyeOff } from 'lucide-react';

interface ProfileViewProps {
  profile: any;
  sampleData: { columns: string[]; sample: any[] } | null;
  onRunIngest: () => void;
  isProcessing: boolean;
}

export const ProfileView: React.FC<ProfileViewProps> = ({
  profile,
  sampleData,
  onRunIngest,
  isProcessing,
}) => {
  const [showSample, setShowSample] = useState(true);

  if (!profile) {
    return (
      <div className="flex flex-col items-center justify-center rounded-2xl border border-slate-800 bg-slate-900/40 p-12 text-center">
        <FileSpreadsheet className="h-12 w-12 text-slate-500" />
        <h3 className="mt-3 text-base font-semibold text-white">No Profile Available</h3>
        <p className="mt-1 max-w-sm text-xs text-slate-400">
          Run ingestion and profiling to deterministically compute column statistics, quantiles, and detect anomalies.
        </p>
        <button
          onClick={onRunIngest}
          disabled={isProcessing}
          className="mt-5 rounded-xl bg-sky-500 px-4 py-2 text-xs font-semibold text-white hover:bg-sky-400 active:scale-95 transition-all disabled:opacity-50"
        >
          {isProcessing ? 'Processing Profile...' : 'Run Ingest & Profile Now'}
        </button>
      </div>
    );
  }

  const summary = profile.summary || {};
  const columns: any[] = profile.column_profiles || [];

  const totalPii = columns.filter((c) => c.pii_flag).length;
  const totalOutliers = columns.reduce((acc, c) => acc + (c.outlier_count || 0), 0);

  return (
    <div className="space-y-6">
      {/* KPI Overview Cards */}
      <div className="grid grid-cols-2 gap-3 sm:grid-cols-3 lg:grid-cols-5">
        <div className="rounded-2xl border border-slate-200/90 bg-white/80 p-4 shadow-sm dark:border-slate-800 dark:bg-slate-900/60">
          <div className="flex items-center justify-between text-slate-500 dark:text-slate-400">
            <span className="text-xs font-medium">Total Rows</span>
            <Hash className="h-4 w-4 text-sky-500 dark:text-sky-400" />
          </div>
          <div className="mt-2 text-xl font-bold text-slate-900 dark:text-white">
            {summary.total_rows?.toLocaleString() || 0}
          </div>
          <div className="mt-1 text-[10px] text-slate-400 dark:text-slate-500">Deterministic Polars count</div>
        </div>

        <div className="rounded-2xl border border-slate-200/90 bg-white/80 p-4 shadow-sm dark:border-slate-800 dark:bg-slate-900/60">
          <div className="flex items-center justify-between text-slate-500 dark:text-slate-400">
            <span className="text-xs font-medium">Total Columns</span>
            <FileSpreadsheet className="h-4 w-4 text-sky-500 dark:text-sky-400" />
          </div>
          <div className="mt-2 text-xl font-bold text-slate-900 dark:text-white">{summary.total_columns || 0}</div>
          <div className="mt-1 text-[10px] text-slate-400 dark:text-slate-500">Inferred types typed</div>
        </div>

        <div className="rounded-2xl border border-slate-200/90 bg-white/80 p-4 shadow-sm dark:border-slate-800 dark:bg-slate-900/60">
          <div className="flex items-center justify-between text-slate-500 dark:text-slate-400">
            <span className="text-xs font-medium">Missing Rate</span>
            <AlertTriangle className="h-4 w-4 text-amber-500 dark:text-amber-400" />
          </div>
          <div className="mt-2 text-xl font-bold text-amber-600 dark:text-amber-300">
            {summary.missing_cell_pct !== undefined ? `${summary.missing_cell_pct}%` : '0%'}
          </div>
          <div className="mt-1 text-[10px] text-slate-400 dark:text-slate-500">Includes tokens like N/A, -</div>
        </div>

        <div className="rounded-2xl border border-slate-200/90 bg-white/80 p-4 shadow-sm dark:border-slate-800 dark:bg-slate-900/60">
          <div className="flex items-center justify-between text-slate-500 dark:text-slate-400">
            <span className="text-xs font-medium">Outliers Flagged</span>
            <AlertTriangle className="h-4 w-4 text-orange-500 dark:text-orange-400" />
          </div>
          <div className="mt-2 text-xl font-bold text-orange-600 dark:text-orange-300">{totalOutliers}</div>
          <div className="mt-1 text-[10px] text-slate-400 dark:text-slate-500">IQR & robust z-score</div>
        </div>

        <div className="rounded-2xl border border-slate-200/90 bg-white/80 p-4 shadow-sm dark:border-slate-800 dark:bg-slate-900/60">
          <div className="flex items-center justify-between text-slate-500 dark:text-slate-400">
            <span className="text-xs font-medium">PII Columns</span>
            <ShieldAlert className="h-4 w-4 text-rose-500 dark:text-rose-400" />
          </div>
          <div className="mt-2 text-xl font-bold text-rose-600 dark:text-rose-400">{totalPii}</div>
          <div className="mt-1 text-[10px] text-slate-400 dark:text-slate-500">Invariant 6 masked</div>
        </div>
      </div>

      {/* Column Profiles Table */}
      <div className="overflow-hidden rounded-2xl border border-slate-200/90 bg-white/80 shadow-sm backdrop-blur-sm dark:border-slate-800 dark:bg-slate-900/60 dark:shadow-xl">
        <div className="border-b border-slate-100 dark:border-slate-800 px-6 py-4 flex items-center justify-between">
          <div>
            <h3 className="text-sm font-semibold text-slate-900 dark:text-white">Deterministic Column Profiles</h3>
            <p className="mt-0.5 text-xs text-slate-500 dark:text-slate-400">
              Computed directly via Polars in-memory engine. No LLM estimation.
            </p>
          </div>
          <div className="flex items-center gap-2">
            <span className="rounded-full border border-sky-500/20 bg-sky-500/5 px-2.5 py-0.5 text-[10px] font-medium text-sky-600 dark:text-sky-400">
              {columns.length} Columns
            </span>
          </div>
        </div>

        <div className="overflow-x-auto">
          <table className="w-full text-left text-xs">
            <thead className="bg-slate-50 text-slate-600 border-b border-slate-200 dark:bg-slate-950/70 dark:text-slate-400 dark:border-slate-800">
              <tr>
                <th className="px-4 py-3 font-medium">Column Name</th>
                <th className="px-4 py-3 font-medium">Inferred Type</th>
                <th className="px-4 py-3 font-medium">Null %</th>
                <th className="px-4 py-3 font-medium">Distinct</th>
                <th className="px-4 py-3 font-medium">Stats (Min / Median / Max)</th>
                <th className="px-4 py-3 font-medium">Outliers</th>
                <th className="px-4 py-3 font-medium">PII Status</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-100 text-slate-700 dark:divide-slate-800/60 dark:text-slate-300">
              {columns.map((col, idx) => {
                const nullPct = col.null_pct !== undefined ? col.null_pct : 0;
                return (
                  <tr key={idx} className="hover:bg-slate-50 dark:hover:bg-slate-800/30 transition-colors">
                    <td className="px-4 py-3 font-semibold text-slate-900 dark:text-white">{col.name}</td>
                    <td className="px-4 py-3">
                      <span className="rounded-md border border-slate-200 bg-slate-100 text-slate-700 dark:border-slate-700 dark:bg-slate-800 dark:text-slate-300 px-2 py-0.5 text-[10px] font-mono">
                        {col.inferred_dtype || 'string'}
                      </span>
                    </td>
                    <td className="px-4 py-3">
                      <div className="flex items-center gap-2">
                        <div className="h-1.5 w-16 rounded-full bg-slate-100 dark:bg-slate-800 overflow-hidden">
                          <div
                            className={`h-full ${nullPct > 20 ? 'bg-rose-500' : nullPct > 5 ? 'bg-amber-500' : 'bg-emerald-500'}`}
                            style={{ width: `${Math.min(100, nullPct)}%` }}
                          />
                        </div>
                        <span className="text-[11px] font-medium">{nullPct}%</span>
                      </div>
                    </td>
                    <td className="px-4 py-3 font-mono text-slate-500 dark:text-slate-400">{col.distinct_count ?? '—'}</td>
                    <td className="px-4 py-3 font-mono text-[11px] text-slate-500 dark:text-slate-400">
                      {col.stats?.min !== undefined && col.stats?.max !== undefined
                        ? `${col.stats.min} / ${col.stats.median ?? col.stats.mean ?? '—'} / ${col.stats.max}`
                        : '—'}
                    </td>
                    <td className="px-4 py-3">
                      {col.outlier_count && col.outlier_count > 0 ? (
                        <span className="inline-flex items-center gap-1 text-orange-600 dark:text-orange-400 font-medium">
                          <AlertTriangle className="h-3 w-3" />
                          <span>{col.outlier_count}</span>
                        </span>
                      ) : (
                        <span className="text-slate-400 dark:text-slate-500">0</span>
                      )}
                    </td>
                    <td className="px-4 py-3">
                      {col.pii_flag ? (
                        <span className="inline-flex items-center gap-1 rounded-full border border-rose-500/30 bg-rose-500/10 px-2 py-0.5 text-[10px] font-semibold text-rose-600 dark:text-rose-400">
                          <ShieldAlert className="h-3 w-3" />
                          <span>{col.pii_type || 'PII'}</span>
                        </span>
                      ) : (
                        <span className="inline-flex items-center gap-1 text-[10px] text-slate-400 dark:text-slate-500">
                          <CheckCircle2 className="h-3 w-3 text-emerald-500" />
                          <span>Clear</span>
                        </span>
                      )}
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      </div>

      {/* 20-Row Masked Sample View */}
      {sampleData && sampleData.sample && sampleData.sample.length > 0 && (
        <div className="overflow-hidden rounded-2xl border border-slate-200/90 bg-white/80 shadow-sm backdrop-blur-sm dark:border-slate-800 dark:bg-slate-900/60 dark:shadow-xl">
          <div className="border-b border-slate-100 dark:border-slate-800 px-6 py-4 flex items-center justify-between">
            <div className="flex items-center gap-3">
              <div className="flex h-8 w-8 items-center justify-center rounded-lg bg-sky-500/10 text-sky-500 dark:text-sky-400">
                <FileSpreadsheet className="h-4 w-4" />
              </div>
              <div>
                <h3 className="text-sm font-semibold text-slate-900 dark:text-white">Masked Sample Preview (20 Rows)</h3>
                <p className="mt-0.5 text-xs text-slate-500 dark:text-slate-400">
                  Invariant 6: Only non-PII and irreversibly masked rows are exposed outside storage.
                </p>
              </div>
            </div>
            <button
              onClick={() => setShowSample(!showSample)}
              className="flex items-center gap-1.5 rounded-lg border border-slate-200 bg-slate-50 px-3 py-1.5 text-xs font-medium text-slate-600 hover:text-slate-900 dark:border-slate-800 dark:bg-slate-950/60 dark:text-slate-400 dark:hover:text-slate-200 transition-colors"
            >
              {showSample ? <EyeOff className="h-3.5 w-3.5" /> : <Eye className="h-3.5 w-3.5" />}
              <span>{showSample ? 'Hide Table' : 'Show Table'}</span>
            </button>
          </div>

          {showSample && (
            <div className="overflow-x-auto max-h-96">
              <table className="w-full text-left text-xs font-mono">
                <thead className="sticky top-0 bg-slate-100 text-slate-600 border-b border-slate-200 dark:bg-slate-950 dark:text-slate-400 dark:border-slate-800">
                  <tr>
                    <th className="px-4 py-2.5 text-slate-400 dark:text-slate-500">#</th>
                    {sampleData.columns.map((col, i) => (
                      <th key={i} className="px-4 py-2.5 font-medium text-slate-700 dark:text-slate-300 whitespace-nowrap">
                        {col}
                      </th>
                    ))}
                  </tr>
                </thead>
                <tbody className="divide-y divide-slate-100 text-slate-700 dark:divide-slate-800/40 dark:text-slate-300">
                  {sampleData.sample.map((row, rIdx) => (
                    <tr key={rIdx} className="hover:bg-slate-50 dark:hover:bg-slate-800/30">
                      <td className="px-4 py-2 text-slate-400 dark:text-slate-500">{rIdx + 1}</td>
                      {sampleData.columns.map((col, cIdx) => (
                        <td key={cIdx} className="px-4 py-2 whitespace-nowrap text-slate-800 dark:text-slate-300">
                          {row[col] !== null && row[col] !== undefined ? String(row[col]) : (
                            <span className="text-slate-400 dark:text-slate-600 italic">null</span>
                          )}
                        </td>
                      ))}
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </div>
      )}
    </div>
  );
};
