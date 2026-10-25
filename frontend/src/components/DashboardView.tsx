import React from 'react';
import { ChartRenderer } from './ChartRenderer';
import { BarChart3, TrendingUp, Sparkles, Quote } from 'lucide-react';

interface DashboardViewProps {
  dashboardData: any;
  isLoading: boolean;
  onRefresh: () => void;
}

export const DashboardView: React.FC<DashboardViewProps> = ({
  dashboardData,
  isLoading,
  onRefresh,
}) => {
  if (isLoading) {
    return (
      <div className="flex flex-col items-center justify-center p-12 text-slate-400">
        <div className="h-8 w-8 animate-spin rounded-full border-2 border-sky-500 border-t-transparent" />
        <p className="mt-3 text-xs">Computing deterministic KPIs and charts...</p>
      </div>
    );
  }

  if (!dashboardData) {
    return (
      <div className="flex flex-col items-center justify-center rounded-2xl border border-slate-800 bg-slate-900/40 p-12 text-center">
        <BarChart3 className="h-12 w-12 text-slate-500" />
        <h3 className="mt-3 text-base font-semibold text-white">No Dashboard Computed Yet</h3>
        <p className="mt-1 max-w-sm text-xs text-slate-400">
          Apply cleaning or run profiling to compile the deterministic chart specifications and KPIs.
        </p>
        <button
          onClick={onRefresh}
          className="mt-5 rounded-xl bg-sky-500 px-4 py-2 text-xs font-semibold text-white hover:bg-sky-400 active:scale-95 transition-all"
        >
          Compute Dashboard Now
        </button>
      </div>
    );
  }

  const kpis: any[] = dashboardData.kpis || [];
  const narratives: string[] = dashboardData.narratives_rendered || dashboardData.narratives || [];
  const charts: any[] = dashboardData.charts || [];

  const getChartSpec = (chart: any) => {
    if (chart.vega_spec) return chart.vega_spec;
    const rows = chart.data?.rows || [];
    const keys = rows[0] ? Object.keys(rows[0]) : [];
    const xField = chart.encoding?.x || keys[0] || 'x';
    const yField = chart.encoding?.y || (keys.length > 1 ? keys[1] : keys[0]) || 'y';
    const chartType = chart.type === 'line' ? 'line' : 'bar';

    return {
      $schema: 'https://vega.github.io/schema/vega-lite/v5.json',
      title: chart.title || 'Visualization',
      width: 'container',
      height: 260,
      data: { values: rows },
      mark:
        chartType === 'bar'
          ? { type: 'bar', tooltip: true, cornerRadiusTopLeft: 4, cornerRadiusTopRight: 4, color: '#38bdf8' }
          : { type: 'line', point: true, tooltip: true, color: '#6366f1' },
      encoding: {
        x: { field: xField, type: 'nominal', axis: { labelAngle: -30, title: xField } },
        y: { field: yField, type: 'quantitative', axis: { title: yField } },
      },
    };
  };

  return (
    <div className="space-y-6">
      {/* Top Header */}
      <div className="flex flex-col gap-2 rounded-2xl border border-slate-200/90 bg-white/80 p-5 shadow-sm backdrop-blur-sm dark:border-slate-800 dark:bg-slate-900/60 sm:flex-row sm:items-center sm:justify-between transition-colors duration-200">
        <div>
          <div className="inline-flex items-center gap-1.5 rounded-full border border-sky-500/30 bg-sky-500/10 px-3 py-1 text-xs font-medium text-sky-600 dark:text-sky-400">
            <Sparkles className="h-3.5 w-3.5" />
            <span>Invariant 3: 100% Deterministically Computed Metrics</span>
          </div>
          <h2 className="mt-2 text-xl font-bold tracking-tight text-slate-900 dark:text-white">
            Executive Insights & Analytics
          </h2>
          <p className="mt-0.5 text-xs text-slate-500 dark:text-slate-400">
            Every metric and quantile is computed directly by DuckDB & Polars. Zero fabricated numbers.
          </p>
        </div>

        <button
          onClick={onRefresh}
          className="self-start sm:self-auto rounded-xl border border-slate-200 bg-slate-50 px-3.5 py-2 text-xs font-semibold text-slate-700 hover:bg-slate-100 dark:border-slate-700 dark:bg-slate-800 dark:text-slate-200 dark:hover:bg-slate-700 transition-colors shadow-sm"
        >
          Refresh Metrics
        </button>
      </div>

      {/* KPI Metric Cards */}
      {kpis.length > 0 && (
        <div className="grid grid-cols-2 gap-4 sm:grid-cols-3 lg:grid-cols-4">
          {kpis.map((kpi, idx) => {
            const rawVal = kpi.value !== null && kpi.value !== undefined ? kpi.value : kpi.computed_value;
            const displayVal = rawVal !== null && rawVal !== undefined ? (typeof rawVal === 'number' ? (Number.isInteger(rawVal) ? rawVal.toLocaleString() : rawVal.toFixed(2)) : String(rawVal)) : '—';
            const title = kpi.label || kpi.title || kpi.id;

            return (
              <div
                key={idx}
                className="rounded-2xl border border-slate-200/90 bg-white/80 p-5 shadow-sm backdrop-blur-sm dark:border-slate-800 dark:bg-slate-900/60 dark:shadow-lg"
              >
                <div className="flex items-center justify-between text-slate-500 dark:text-slate-400">
                  <span className="text-xs font-medium truncate" title={title}>{title}</span>
                  <TrendingUp className="h-4 w-4 text-sky-500 dark:text-sky-400 shrink-0" />
                </div>
                <div className="mt-2 text-2xl font-bold text-slate-900 dark:text-white">
                  {displayVal}
                  {kpi.unit && <span className="ml-1 text-sm font-normal text-slate-500 dark:text-slate-400">{kpi.unit}</span>}
                </div>
                {kpi.subtitle && (
                  <div className="mt-1 text-[11px] text-slate-500 dark:text-slate-400">{kpi.subtitle}</div>
                )}
              </div>
            );
          })}
        </div>
      )}

      {/* Invariant 3 Deterministic Narratives */}
      {narratives.length > 0 && (
        <div className="rounded-2xl border border-indigo-200 bg-indigo-50/60 p-5 shadow-sm dark:border-indigo-500/30 dark:bg-indigo-950/20 dark:shadow-xl">
          <div className="flex items-center gap-2 text-xs font-bold uppercase tracking-wider text-indigo-700 dark:text-indigo-400">
            <Quote className="h-4 w-4" />
            <span>Deterministic Executive Narrative</span>
          </div>
          <div className="mt-3 space-y-2 text-sm leading-relaxed text-slate-800 dark:text-slate-200">
            {narratives.map((text, idx) => (
              <p key={idx} className="font-medium bg-white p-3 rounded-xl border border-indigo-100 shadow-sm dark:bg-slate-900/60 dark:border-indigo-500/20">
                {text}
              </p>
            ))}
          </div>
          <div className="mt-2 text-[10px] text-slate-500 dark:text-slate-400">
            Enforced by Invariant 3: Any digit outside strict KPI placeholders causes template rejection.
          </div>
        </div>
      )}

      {/* Vega-Lite Visualizations */}
      {charts.length > 0 ? (
        <div className="grid gap-6 lg:grid-cols-2">
          {charts.map((chart, idx) => (
            <div
              key={idx}
              className="rounded-2xl border border-slate-200/90 bg-white/80 p-5 shadow-sm backdrop-blur-sm dark:border-slate-800 dark:bg-slate-900/60 dark:shadow-xl"
            >
              <div className="mb-4">
                <h3 className="text-sm font-semibold text-slate-900 dark:text-white">{chart.title || `Visualization ${idx + 1}`}</h3>
                {chart.description && (
                  <p className="mt-0.5 text-xs text-slate-500 dark:text-slate-400">{chart.description}</p>
                )}
              </div>
              <div className="w-full flex items-center justify-center p-2 rounded-xl bg-slate-50 border border-slate-200 dark:bg-slate-950/40 dark:border-slate-800/60">
                <ChartRenderer spec={getChartSpec(chart)} chartId={`chart-${idx}`} />
              </div>
            </div>
          ))}
        </div>
      ) : (
        <div className="rounded-2xl border border-dashed border-slate-300 dark:border-slate-800 p-8 text-center text-slate-500 dark:text-slate-400">
          <BarChart3 className="mx-auto h-8 w-8 text-slate-400 dark:text-slate-600" />
          <p className="mt-2 text-xs">No chart specifications generated for this dataset yet.</p>
        </div>
      )}
    </div>
  );
};
