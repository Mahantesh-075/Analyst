import React, { useEffect, useRef } from 'react';
import embed from 'vega-embed';
import { useThemeStore } from '../store/themeStore';

interface ChartRendererProps {
  spec: any;
  chartId?: string;
  className?: string;
}

export const ChartRenderer: React.FC<ChartRendererProps> = ({ spec, chartId = 'chart', className = '' }) => {
  const containerRef = useRef<HTMLDivElement>(null);
  const { theme } = useThemeStore();
  const isDark = theme === 'dark';

  const isEmpty = !spec || (spec.data?.values && spec.data.values.length === 0);

  useEffect(() => {
    if (!containerRef.current || !spec || isEmpty) return;

    // Apply active theme and responsive dimensions
    const themedSpec = {
      ...spec,
      background: 'transparent',
      config: {
        ...spec.config,
        background: 'transparent',
        view: { stroke: 'transparent' },
        axis: {
          gridColor: isDark ? '#334155' : '#e2e8f0',
          tickColor: isDark ? '#475569' : '#cbd5e1',
          domainColor: isDark ? '#475569' : '#cbd5e1',
          labelColor: isDark ? '#94a3b8' : '#64748b',
          titleColor: isDark ? '#cbd5e1' : '#334155',
          labelFontSize: 11,
          titleFontSize: 12,
        },
        legend: {
          labelColor: isDark ? '#94a3b8' : '#64748b',
          titleColor: isDark ? '#cbd5e1' : '#334155',
        },
        title: {
          color: isDark ? '#f8fafc' : '#0f172a',
          fontSize: 14,
        },
      },
    };

    let viewInstance: any = null;
    embed(containerRef.current, themedSpec, {
      actions: { export: true, source: false, compiled: false, editor: false },
      theme: isDark ? 'dark' : undefined,
      renderer: 'svg',
    })
      .then((res) => {
        viewInstance = res.view;
      })
      .catch((err) => {
        console.warn('Vega embed failed:', err);
      });

    return () => {
      if (viewInstance) {
        viewInstance.finalize();
      }
    };
  }, [spec, isDark, isEmpty]);

  if (isEmpty) {
    return (
      <div className={`w-full flex flex-col items-center justify-center min-h-[260px] text-slate-400 dark:text-slate-500 text-xs ${className}`}>
        <span>No data points available for this visualization</span>
      </div>
    );
  }

  return (
    <div
      id={chartId}
      ref={containerRef}
      className={`w-full overflow-hidden flex items-center justify-center min-h-[300px] ${className}`}
    />
  );
};
