import React, { useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import { useAuthStore } from './store/authStore';
import { useDatasetStore } from './store/datasetStore';
import { api } from './api/client';
import { Navbar } from './components/Navbar';
import { AuthModal } from './components/AuthModal';
import { UploadModal } from './components/UploadModal';
import { DatasetList } from './components/DatasetList';
import { DatasetWorkspace } from './components/DatasetWorkspace';
import { AlertCircle, CheckCircle2, Info, Sparkles } from 'lucide-react';

export const App: React.FC = () => {
  const { isAuthenticated } = useAuthStore();
  const { activeDatasetId, setActiveDatasetId, toastMessage, clearToast } = useDatasetStore();

  const [isAuthOpen, setIsAuthOpen] = useState(false);
  const [isUploadOpen, setIsUploadOpen] = useState(false);

  // Fetch datasets list
  const {
    data: datasets = [],
    isLoading: isDatasetsLoading,
    refetch: refetchDatasets,
  } = useQuery({
    queryKey: ['datasets'],
    queryFn: () => api.getDatasets(),
    enabled: isAuthenticated,
  });

  const activeDataset = datasets.find((d: any) => d.id === activeDatasetId);

  return (
    <div className="min-h-screen bg-slate-50 text-slate-900 dark:bg-[#070b12] dark:text-slate-100 flex flex-col font-sans selection:bg-sky-500/30 selection:text-sky-800 dark:selection:text-sky-200 transition-colors duration-200">
      {/* Toast Alert Notification */}
      {toastMessage && (
        <div className="fixed bottom-6 right-6 z-50 flex items-center gap-3 rounded-2xl border border-slate-200 bg-white/95 dark:border-slate-700 dark:bg-slate-900/95 px-4 py-3 shadow-2xl backdrop-blur-xl animate-in slide-in-from-bottom-5">
          {toastMessage.type === 'success' ? (
            <CheckCircle2 className="h-4 w-4 text-emerald-500 shrink-0" />
          ) : toastMessage.type === 'error' ? (
            <AlertCircle className="h-4 w-4 text-rose-500 shrink-0" />
          ) : (
            <Info className="h-4 w-4 text-sky-500 shrink-0" />
          )}
          <span className="text-xs font-medium text-slate-800 dark:text-slate-200">{toastMessage.text}</span>
          <button
            onClick={clearToast}
            className="ml-2 text-slate-400 hover:text-slate-700 dark:hover:text-white text-xs font-bold"
          >
            ×
          </button>
        </div>
      )}

      {/* Top Navigation */}
      <Navbar
        onOpenAuth={() => setIsAuthOpen(true)}
        onOpenUpload={() => setIsUploadOpen(true)}
        datasetName={activeDataset?.name}
      />

      {/* Main Content Area */}
      <main className="flex-1">
        {!isAuthenticated ? (
          <div className="mx-auto flex min-h-[calc(100vh-4rem)] max-w-4xl flex-col items-center justify-center px-4 py-16 text-center">
            <div className="inline-flex items-center gap-2 rounded-full border border-sky-500/30 bg-sky-500/10 px-4 py-1.5 text-xs font-semibold text-sky-600 dark:text-sky-400">
              <Sparkles className="h-4 w-4" />
              <span>Production Data Preparation & Insights Platform</span>
            </div>

            <h1 className="mt-6 text-4xl font-extrabold tracking-tight text-slate-900 dark:text-white sm:text-6xl">
              Deterministic Analytics for{' '}
              <span className="bg-gradient-to-r from-sky-500 via-indigo-500 to-teal-500 dark:from-sky-400 dark:via-indigo-400 dark:to-teal-400 bg-clip-text text-transparent">
                High-Trust Missions
              </span>
            </h1>

            <p className="mt-4 max-w-2xl text-sm leading-relaxed text-slate-600 dark:text-slate-400 sm:text-base">
              Built with zero silent mutation, closed op registries, formula injection neutralization,
              and 100% Python/SQL reproducibility guarantees.
            </p>

            <div className="mt-8 flex flex-wrap items-center justify-center gap-3">
              <button
                onClick={() => setIsAuthOpen(true)}
                className="inline-flex items-center gap-2 rounded-xl bg-gradient-to-r from-sky-500 to-indigo-600 px-6 py-3 text-sm font-semibold text-white shadow-xl shadow-sky-500/25 hover:from-sky-400 hover:to-indigo-500 active:scale-95 transition-all"
              >
                <Sparkles className="h-4 w-4" />
                <span>Launch Demo Account (Mahant)</span>
              </button>
            </div>

            {/* Invariants Grid */}
            <div className="mt-16 grid grid-cols-1 gap-4 text-left sm:grid-cols-3">
              <div className="rounded-2xl border border-slate-200/90 bg-white/70 p-5 shadow-sm backdrop-blur-sm dark:border-slate-800/80 dark:bg-slate-900/40">
                <div className="text-xs font-bold text-sky-600 dark:text-sky-400">Invariant 1 & 4</div>
                <div className="mt-1 text-sm font-semibold text-slate-900 dark:text-white">No Silent Mutation</div>
                <p className="mt-1 text-xs text-slate-600 dark:text-slate-400">
                  Raw files immutable. Changes only occur through reviewed transform steps in a closed registry.
                </p>
              </div>

              <div className="rounded-2xl border border-slate-200/90 bg-white/70 p-5 shadow-sm backdrop-blur-sm dark:border-slate-800/80 dark:bg-slate-900/40">
                <div className="text-xs font-bold text-indigo-600 dark:text-indigo-400">Invariant 3 & 5</div>
                <div className="mt-1 text-sm font-semibold text-slate-900 dark:text-white">Deterministic Computation</div>
                <p className="mt-1 text-xs text-slate-600 dark:text-slate-400">
                  Every number calculated via Polars & DuckDB. Formulas neutralized against spreadsheet injection.
                </p>
              </div>

              <div className="rounded-2xl border border-slate-200/90 bg-white/70 p-5 shadow-sm backdrop-blur-sm dark:border-slate-800/80 dark:bg-slate-900/40">
                <div className="text-xs font-bold text-emerald-600 dark:text-emerald-400">Invariant 7</div>
                <div className="mt-1 text-sm font-semibold text-slate-900 dark:text-white">100% Reproducibility</div>
                <p className="mt-1 text-xs text-slate-600 dark:text-slate-400">
                  Exported standalone Python & DuckDB SQL scripts reproduce identical Parquet SHA-256 hashes.
                </p>
              </div>
            </div>
          </div>
        ) : activeDatasetId ? (
          <DatasetWorkspace datasetId={activeDatasetId} />
        ) : (
          <DatasetList
            datasets={datasets}
            onSelectDataset={(id) => setActiveDatasetId(id)}
            onOpenUpload={() => setIsUploadOpen(true)}
            isLoading={isDatasetsLoading}
          />
        )}
      </main>

      {/* Footer */}
      <footer className="border-t border-slate-200/80 bg-white/50 dark:border-slate-800/60 dark:bg-slate-950/40 py-6 text-center text-xs text-slate-500 transition-colors duration-200">
        <div className="mx-auto max-w-7xl px-4 flex flex-col items-center justify-between gap-2 sm:flex-row">
          <span>Analyst — Built for Mahant. Production verified.</span>
          <span className="font-mono text-[11px] text-slate-400 dark:text-slate-600">Polars · DuckDB · FastAPI · PostgreSQL</span>
        </div>
      </footer>

      {/* Modals */}
      <AuthModal
        isOpen={isAuthOpen}
        onClose={() => setIsAuthOpen(false)}
        onSuccess={() => refetchDatasets()}
      />

      <UploadModal
        isOpen={isUploadOpen}
        onClose={() => setIsUploadOpen(false)}
        onSuccess={(datasetId) => {
          refetchDatasets();
          setActiveDatasetId(datasetId);
        }}
      />
    </div>
  );
};

export default App;
