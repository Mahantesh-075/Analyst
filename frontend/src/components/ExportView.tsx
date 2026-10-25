import React, { useState } from 'react';
import { api } from '../api/client';
import {
  Download,
  FileSpreadsheet,
  FileCode,
  Database,
  ShieldCheck,
  Copy,
  Check,
} from 'lucide-react';

interface ExportViewProps {
  datasetId: string;
  datasetName: string;
  status: string;
}

export const ExportView: React.FC<ExportViewProps> = ({ datasetId, datasetName, status }) => {
  const [downloading, setDownloading] = useState<string | null>(null);
  const [previewContent, setPreviewContent] = useState<{ type: 'python' | 'sql' | 'csv'; code: string } | null>(null);
  const [copied, setCopied] = useState(false);

  const cleanName = datasetName.replace(/\s+/g, '_').toLowerCase();

  const handleDownload = async (format: 'csv' | 'parquet' | 'python' | 'sql', ext: string) => {
    setDownloading(format);
    try {
      const filename = `${cleanName}_clean.${ext}`;
      await api.downloadExport(datasetId, format, filename);
    } catch (err: any) {
      alert(`Download failed: ${err.message || 'Error'}`);
    } finally {
      setDownloading(null);
    }
  };

  const handlePreview = async (format: 'python' | 'sql' | 'csv') => {
    try {
      const text = await api.getExportText(datasetId, format);
      setPreviewContent({ type: format, code: text });
    } catch (err: any) {
      alert(`Could not load code preview: ${err.message || 'Error'}`);
    }
  };

  const handleCopy = () => {
    if (previewContent?.code) {
      navigator.clipboard.writeText(previewContent.code);
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    }
  };

  return (
    <div className="space-y-6">
      {/* Header Banner */}
      <div className="flex flex-col gap-2 rounded-2xl border border-slate-200/90 bg-white/80 p-5 shadow-sm backdrop-blur-sm dark:border-slate-800 dark:bg-slate-900/60 sm:flex-row sm:items-center sm:justify-between transition-colors duration-200">
        <div>
          <div className="inline-flex items-center gap-1.5 rounded-full border border-emerald-500/30 bg-emerald-500/10 px-3 py-1 text-xs font-medium text-emerald-600 dark:text-emerald-400">
            <ShieldCheck className="h-3.5 w-3.5" />
            <span>Invariant 7: 100% Reproducibility Guarantee</span>
          </div>
          <h2 className="mt-2 text-xl font-bold tracking-tight text-slate-900 dark:text-white">
            Export Datasets & Reproduction Scripts
          </h2>
          <p className="mt-0.5 text-xs text-slate-500 dark:text-slate-400">
            Running either exported Python script or DuckDB SQL on the raw file produces identical canonical Parquet SHA-256 hashes.
          </p>
        </div>

        <div className="flex items-center gap-2">
          <span className="rounded-lg border border-slate-200 bg-slate-50 dark:border-slate-800 dark:bg-slate-950/80 px-3 py-1.5 font-mono text-[11px] text-slate-600 dark:text-slate-400">
            Format: {status === 'cleaned' ? 'Cleaned (V2)' : 'Raw (V1)'}
          </span>
        </div>
      </div>

      {/* 4 Export Cards Grid */}
      <div className="grid gap-4 sm:grid-cols-2">
        {/* Card 1: Formula-Safe CSV */}
        <div className="flex flex-col justify-between rounded-2xl border border-slate-200/90 bg-white/80 p-5 shadow-sm backdrop-blur-sm hover:border-slate-300 dark:border-slate-800 dark:bg-slate-900/60 dark:shadow-xl dark:hover:border-slate-700 transition-all">
          <div>
            <div className="flex items-center justify-between">
              <div className="flex h-10 w-10 items-center justify-center rounded-xl bg-sky-500/10 text-sky-500 dark:text-sky-400">
                <FileSpreadsheet className="h-5 w-5" />
              </div>
              <span className="rounded-full border border-sky-500/30 bg-sky-500/10 px-2.5 py-0.5 text-[10px] font-semibold text-sky-600 dark:text-sky-400">
                CWE-1236 SAFE
              </span>
            </div>
            <h3 className="mt-3 text-base font-semibold text-slate-900 dark:text-white">Formula-Safe CSV</h3>
            <p className="mt-1 text-xs text-slate-500 dark:text-slate-400 leading-relaxed">
              Spreadsheet formula injection neutralized. Characters (=, +, -, @, \t, \r) prefixed with safe single quotes.
            </p>
          </div>

          <div className="mt-6 flex items-center gap-2 border-t border-slate-100 dark:border-slate-800/80 pt-4">
            <button
              onClick={() => handleDownload('csv', 'csv')}
              disabled={downloading === 'csv'}
              className="flex-1 inline-flex items-center justify-center gap-1.5 rounded-xl bg-sky-500 py-2 text-xs font-semibold text-white hover:bg-sky-400 active:scale-95 transition-all disabled:opacity-50"
            >
              <Download className="h-3.5 w-3.5" />
              <span>{downloading === 'csv' ? 'Downloading...' : 'Download CSV'}</span>
            </button>
            <button
              onClick={() => handlePreview('csv')}
              className="rounded-xl border border-slate-200 bg-slate-50 px-3 py-2 text-xs font-medium text-slate-700 hover:bg-slate-100 dark:border-slate-700 dark:bg-slate-800 dark:text-slate-300 dark:hover:bg-slate-700 transition-colors"
            >
              Preview
            </button>
          </div>
        </div>

        {/* Card 2: Canonical Parquet */}
        <div className="flex flex-col justify-between rounded-2xl border border-slate-200/90 bg-white/80 p-5 shadow-sm backdrop-blur-sm hover:border-slate-300 dark:border-slate-800 dark:bg-slate-900/60 dark:shadow-xl dark:hover:border-slate-700 transition-all">
          <div>
            <div className="flex items-center justify-between">
              <div className="flex h-10 w-10 items-center justify-center rounded-xl bg-emerald-500/10 text-emerald-500 dark:text-emerald-400">
                <Database className="h-5 w-5" />
              </div>
              <span className="rounded-full border border-emerald-500/30 bg-emerald-500/10 px-2.5 py-0.5 text-[10px] font-semibold text-emerald-600 dark:text-emerald-400">
                PARQUET 2.0
              </span>
            </div>
            <h3 className="mt-3 text-base font-semibold text-slate-900 dark:text-white">Canonical Parquet</h3>
            <p className="mt-1 text-xs text-slate-500 dark:text-slate-400 leading-relaxed">
              High-performance columnar storage with typed schemas, dictionary encoding, and compressed storage.
            </p>
          </div>

          <div className="mt-6 flex items-center gap-2 border-t border-slate-100 dark:border-slate-800/80 pt-4">
            <button
              onClick={() => handleDownload('parquet', 'parquet')}
              disabled={downloading === 'parquet'}
              className="w-full inline-flex items-center justify-center gap-1.5 rounded-xl bg-emerald-500 py-2 text-xs font-semibold text-white hover:bg-emerald-400 active:scale-95 transition-all disabled:opacity-50"
            >
              <Download className="h-3.5 w-3.5" />
              <span>{downloading === 'parquet' ? 'Downloading...' : 'Download Parquet'}</span>
            </button>
          </div>
        </div>

        {/* Card 3: Standalone Python Script */}
        <div className="flex flex-col justify-between rounded-2xl border border-slate-200/90 bg-white/80 p-5 shadow-sm backdrop-blur-sm hover:border-slate-300 dark:border-slate-800 dark:bg-slate-900/60 dark:shadow-xl dark:hover:border-slate-700 transition-all">
          <div>
            <div className="flex items-center justify-between">
              <div className="flex h-10 w-10 items-center justify-center rounded-xl bg-indigo-500/10 text-indigo-500 dark:text-indigo-400">
                <FileCode className="h-5 w-5" />
              </div>
              <span className="rounded-full border border-indigo-500/30 bg-indigo-500/10 px-2.5 py-0.5 text-[10px] font-semibold text-indigo-600 dark:text-indigo-400">
                POLARS SCRIPT
              </span>
            </div>
            <h3 className="mt-3 text-base font-semibold text-slate-900 dark:text-white">Standalone Python Pipeline</h3>
            <p className="mt-1 text-xs text-slate-500 dark:text-slate-400 leading-relaxed">
              Self-contained Python code running pure Polars expressions. Zero platform lock-in. Reproduces identical cleaned rows.
            </p>
          </div>

          <div className="mt-6 flex items-center gap-2 border-t border-slate-100 dark:border-slate-800/80 pt-4">
            <button
              onClick={() => handleDownload('python', 'py')}
              disabled={downloading === 'python'}
              className="flex-1 inline-flex items-center justify-center gap-1.5 rounded-xl bg-indigo-500 py-2 text-xs font-semibold text-white hover:bg-indigo-400 active:scale-95 transition-all disabled:opacity-50"
            >
              <Download className="h-3.5 w-3.5" />
              <span>{downloading === 'python' ? 'Downloading...' : 'Download .py'}</span>
            </button>
            <button
              onClick={() => handlePreview('python')}
              className="rounded-xl border border-slate-200 bg-slate-50 px-3 py-2 text-xs font-medium text-slate-700 hover:bg-slate-100 dark:border-slate-700 dark:bg-slate-800 dark:text-slate-300 dark:hover:bg-slate-700 transition-colors"
            >
              View Code
            </button>
          </div>
        </div>

        {/* Card 4: DuckDB SQL Pipeline */}
        <div className="flex flex-col justify-between rounded-2xl border border-slate-200/90 bg-white/80 p-5 shadow-sm backdrop-blur-sm hover:border-slate-300 dark:border-slate-800 dark:bg-slate-900/60 dark:shadow-xl dark:hover:border-slate-700 transition-all">
          <div>
            <div className="flex items-center justify-between">
              <div className="flex h-10 w-10 items-center justify-center rounded-xl bg-amber-500/10 text-amber-500 dark:text-amber-400">
                <Database className="h-5 w-5" />
              </div>
              <span className="rounded-full border border-amber-500/30 bg-amber-500/10 px-2.5 py-0.5 text-[10px] font-semibold text-amber-600 dark:text-amber-400">
                DUCKDB SQL CTE
              </span>
            </div>
            <h3 className="mt-3 text-base font-semibold text-slate-900 dark:text-white">DuckDB SQL Script</h3>
            <p className="mt-1 text-xs text-slate-500 dark:text-slate-400 leading-relaxed">
              Step-by-step SQL Common Table Expressions (CTEs) matching every transform operation with 100% equivalence.
            </p>
          </div>

          <div className="mt-6 flex items-center gap-2 border-t border-slate-100 dark:border-slate-800/80 pt-4">
            <button
              onClick={() => handleDownload('sql', 'sql')}
              disabled={downloading === 'sql'}
              className="flex-1 inline-flex items-center justify-center gap-1.5 rounded-xl bg-amber-500 py-2 text-xs font-semibold text-white hover:bg-amber-400 active:scale-95 transition-all disabled:opacity-50"
            >
              <Download className="h-3.5 w-3.5" />
              <span>{downloading === 'sql' ? 'Downloading...' : 'Download .sql'}</span>
            </button>
            <button
              onClick={() => handlePreview('sql')}
              className="rounded-xl border border-slate-200 bg-slate-50 px-3 py-2 text-xs font-medium text-slate-700 hover:bg-slate-100 dark:border-slate-700 dark:bg-slate-800 dark:text-slate-300 dark:hover:bg-slate-700 transition-colors"
            >
              View SQL
            </button>
          </div>
        </div>
      </div>

      {/* Code / Text Preview Drawer */}
      {previewContent && (
        <div className="overflow-hidden rounded-2xl border border-slate-200 bg-white dark:border-slate-800 dark:bg-slate-950 p-6 shadow-2xl">
          <div className="flex items-center justify-between border-b border-slate-100 dark:border-slate-800 pb-3">
            <div className="flex items-center gap-2 font-mono text-xs font-semibold text-slate-800 dark:text-slate-200 uppercase">
              <FileCode className="h-4 w-4 text-sky-500 dark:text-sky-400" />
              <span>
                {previewContent.type === 'python'
                  ? 'Python Polars Pipeline Code'
                  : previewContent.type === 'sql'
                  ? 'DuckDB SQL CTE Query'
                  : 'CSV Data Preview'}
              </span>
            </div>

            <div className="flex items-center gap-2">
              <button
                onClick={handleCopy}
                className="flex items-center gap-1 rounded-lg border border-slate-200 bg-slate-50 px-2.5 py-1 text-xs font-medium text-slate-700 hover:bg-slate-100 dark:border-slate-800 dark:bg-slate-900 dark:text-slate-300 dark:hover:bg-slate-800 transition-colors"
              >
                {copied ? <Check className="h-3.5 w-3.5 text-emerald-500" /> : <Copy className="h-3.5 w-3.5" />}
                <span>{copied ? 'Copied!' : 'Copy Code'}</span>
              </button>
              <button
                onClick={() => setPreviewContent(null)}
                className="rounded-lg p-1 text-slate-400 hover:bg-slate-100 hover:text-slate-700 dark:hover:bg-slate-900 dark:hover:text-white"
              >
                Close
              </button>
            </div>
          </div>

          <pre className="mt-4 max-h-96 overflow-auto rounded-xl bg-slate-50 p-4 font-mono text-xs text-slate-800 border border-slate-200 dark:bg-slate-900/80 dark:text-slate-300 dark:border-slate-800">
            <code>{previewContent.code}</code>
          </pre>
        </div>
      )}
    </div>
  );
};
