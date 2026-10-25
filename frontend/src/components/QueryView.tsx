import React, { useState } from 'react';
import { api } from '../api/client';
import { Play, AlertCircle, Clock, ShieldCheck, Terminal } from 'lucide-react';

interface QueryViewProps {
  datasetId: string;
  columns: string[];
}

export const QueryView: React.FC<QueryViewProps> = ({ datasetId, columns }) => {
  const [selectedColumn, setSelectedColumn] = useState<string>(columns[0] || '*');
  const [aggregation, setAggregation] = useState<string>('count');
  const [groupByColumn, setGroupByColumn] = useState<string>('none');
  const [limit, setLimit] = useState<number>(50);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [result, setResult] = useState<{ columns: string[]; records: any[]; count: number } | null>(null);
  const [executionTime, setExecutionTime] = useState<number | null>(null);

  const handleExecuteQuery = async () => {
    setError(null);
    setLoading(true);
    const start = performance.now();

    try {
      const payload: any = {
        limit,
        dimensions: [],
        measures: [],
      };

      if (groupByColumn && groupByColumn !== 'none') {
        payload.dimensions.push({ field: groupByColumn });
      }

      if (aggregation && aggregation !== 'none') {
        const cleanCol = selectedColumn === '*' ? 'all' : selectedColumn.replace(/[^a-zA-Z0-9_]/g, '_').toLowerCase();
        payload.measures.push({
          field: selectedColumn === '*' ? '*' : selectedColumn,
          agg: aggregation,
          as: `${aggregation}_${cleanCol}`.slice(0, 35),
        });
      } else {
        payload.dimensions.push({
          field: selectedColumn === '*' ? (columns[0] || '*') : selectedColumn,
        });
      }

      const res = await api.executeSafeQuery(datasetId, payload);
      const records = res.rows || res.records || [];
      const count = res.row_count !== undefined ? res.row_count : (res.count !== undefined ? res.count : records.length);
      setResult({
        columns: res.columns || [],
        records,
        count,
      });
      setExecutionTime(Math.round(performance.now() - start));
    } catch (err: any) {
      setError(err.message || 'Safe query execution failed');
      setResult(null);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="space-y-6">
      {/* Top Banner */}
      <div className="flex flex-col gap-2 rounded-2xl border border-slate-200/90 bg-white/80 p-5 shadow-sm backdrop-blur-sm dark:border-slate-800 dark:bg-slate-900/60 sm:flex-row sm:items-center sm:justify-between transition-colors duration-200">
        <div>
          <div className="inline-flex items-center gap-1.5 rounded-full border border-sky-500/30 bg-sky-500/10 px-3 py-1 text-xs font-medium text-sky-600 dark:text-sky-400">
            <ShieldCheck className="h-3.5 w-3.5" />
            <span>Invariant 5: Safe DuckDB Parameterized Query Builder</span>
          </div>
          <h2 className="mt-2 text-xl font-bold tracking-tight text-slate-900 dark:text-white">
            Safe In-Memory SQL Query Engine
          </h2>
          <p className="mt-0.5 text-xs text-slate-500 dark:text-slate-400">
            Memory capped at 512MB · 2 threads · Column identifier allow-listing · Bounded parameter execution
          </p>
        </div>

        <div className="flex items-center gap-2">
          <span className="rounded-lg border border-slate-200 bg-slate-50 dark:border-slate-800 dark:bg-slate-950/80 px-3 py-1.5 font-mono text-[11px] text-slate-600 dark:text-slate-400">
            DuckDB 1.2+ Native
          </span>
        </div>
      </div>

      {/* Query Builder Controls */}
      <div className="rounded-2xl border border-slate-200/90 bg-white/80 p-6 shadow-sm dark:border-slate-800 dark:bg-slate-900/60 dark:shadow-xl backdrop-blur-sm">
        <h3 className="text-sm font-semibold text-slate-900 dark:text-white flex items-center gap-2">
          <Terminal className="h-4 w-4 text-sky-500 dark:text-sky-400" />
          <span>Interactive Query Builder</span>
        </h3>

        <div className="mt-4 grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
          <div>
            <label className="block text-xs font-medium text-slate-700 dark:text-slate-300">Target Column</label>
            <select
              value={selectedColumn}
              onChange={(e) => setSelectedColumn(e.target.value)}
              className="mt-1 w-full rounded-xl border border-slate-300 bg-slate-50 px-3 py-2 text-xs text-slate-900 focus:bg-white focus:border-sky-500 focus:outline-none dark:border-slate-800 dark:bg-slate-950 dark:text-slate-100"
            >
              <option value="*">* (All / Primary)</option>
              {columns.map((col) => (
                <option key={col} value={col}>
                  {col}
                </option>
              ))}
            </select>
          </div>

          <div>
            <label className="block text-xs font-medium text-slate-700 dark:text-slate-300">Aggregation Operator</label>
            <select
              value={aggregation}
              onChange={(e) => setAggregation(e.target.value)}
              className="mt-1 w-full rounded-xl border border-slate-300 bg-slate-50 px-3 py-2 text-xs text-slate-900 focus:bg-white focus:border-sky-500 focus:outline-none dark:border-slate-800 dark:bg-slate-950 dark:text-slate-100"
            >
              <option value="count">COUNT()</option>
              <option value="sum">SUM()</option>
              <option value="avg">AVG()</option>
              <option value="min">MIN()</option>
              <option value="max">MAX()</option>
              <option value="none">NONE (Raw Scan)</option>
            </select>
          </div>

          <div>
            <label className="block text-xs font-medium text-slate-700 dark:text-slate-300">Group By Column</label>
            <select
              value={groupByColumn}
              onChange={(e) => setGroupByColumn(e.target.value)}
              className="mt-1 w-full rounded-xl border border-slate-300 bg-slate-50 px-3 py-2 text-xs text-slate-900 focus:bg-white focus:border-sky-500 focus:outline-none dark:border-slate-800 dark:bg-slate-950 dark:text-slate-100"
            >
              <option value="none">None (Overall Aggregation)</option>
              {columns.map((col) => (
                <option key={col} value={col}>
                  {col}
                </option>
              ))}
            </select>
          </div>

          <div>
            <label className="block text-xs font-medium text-slate-700 dark:text-slate-300">Row Limit (Max 1000)</label>
            <input
              type="number"
              min={1}
              max={1000}
              value={limit}
              onChange={(e) => setLimit(Number(e.target.value))}
              className="mt-1 w-full rounded-xl border border-slate-300 bg-slate-50 px-3 py-2 text-xs text-slate-900 focus:bg-white focus:border-sky-500 focus:outline-none dark:border-slate-800 dark:bg-slate-950 dark:text-slate-100"
            />
          </div>
        </div>

        <div className="mt-5 flex items-center justify-between border-t border-slate-200 dark:border-slate-800/80 pt-4">
          <div className="flex items-center gap-2 text-xs text-slate-500 dark:text-slate-400">
            {executionTime !== null && (
              <span className="flex items-center gap-1 text-emerald-600 dark:text-emerald-400 font-medium">
                <Clock className="h-3.5 w-3.5" />
                <span>Executed in {executionTime}ms</span>
              </span>
            )}
          </div>

          <button
            onClick={handleExecuteQuery}
            disabled={loading}
            className="inline-flex items-center gap-2 rounded-xl bg-gradient-to-r from-sky-500 to-indigo-600 px-5 py-2.5 text-xs font-semibold text-white shadow-lg shadow-sky-500/20 hover:from-sky-400 hover:to-indigo-500 active:scale-95 transition-all disabled:opacity-50"
          >
            <Play className="h-4 w-4 fill-white" />
            <span>{loading ? 'Executing Query...' : 'Run Safe DuckDB Query'}</span>
          </button>
        </div>
      </div>

      {error && (
        <div className="flex items-center gap-2 rounded-xl border border-rose-500/30 bg-rose-500/10 p-4 text-xs text-rose-600 dark:text-rose-400">
          <AlertCircle className="h-4 w-4 shrink-0" />
          <span>{error}</span>
        </div>
      )}

      {/* Query Results Table */}
      {result && (
        <div className="overflow-hidden rounded-2xl border border-slate-200/90 bg-white/80 shadow-sm dark:border-slate-800 dark:bg-slate-900/60 dark:shadow-xl backdrop-blur-sm">
          <div className="border-b border-slate-200 dark:border-slate-800 px-6 py-4 flex items-center justify-between">
            <h4 className="text-sm font-semibold text-slate-900 dark:text-white">
              Query Results ({result.count} rows)
            </h4>
            <span className="text-[11px] font-mono text-slate-500 dark:text-slate-400">
              Columns: {result.columns.join(', ')}
            </span>
          </div>

          <div className="overflow-x-auto max-h-96">
            <table className="w-full text-left text-xs font-mono">
              <thead className="sticky top-0 bg-slate-100 text-slate-600 border-b border-slate-200 dark:bg-slate-950 dark:text-slate-400 dark:border-slate-800">
                <tr>
                  <th className="px-4 py-2.5 text-slate-400 dark:text-slate-500">#</th>
                  {result.columns.map((c, i) => (
                    <th key={i} className="px-4 py-2.5 font-medium text-slate-700 dark:text-slate-300">
                      {c}
                    </th>
                  ))}
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-100 text-slate-700 dark:divide-slate-800/40 dark:text-slate-300">
                {result.records.map((row, rIdx) => (
                  <tr key={rIdx} className="hover:bg-slate-50 dark:hover:bg-slate-800/30">
                    <td className="px-4 py-2 text-slate-400 dark:text-slate-500">{rIdx + 1}</td>
                    {result.columns.map((c, cIdx) => (
                      <td key={cIdx} className="px-4 py-2 text-slate-800 dark:text-slate-200">
                        {row[c] !== null && row[c] !== undefined ? String(row[c]) : (
                          <span className="text-slate-400 dark:text-slate-600 italic">null</span>
                        )}
                      </td>
                    ))}
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}
    </div>
  );
};
