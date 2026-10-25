import React from 'react';
import { useAuthStore } from '../store/authStore';
import { useDatasetStore } from '../store/datasetStore';
import { ThemeToggle } from './ThemeToggle';
import { Database, ShieldCheck, LogIn, LogOut, ArrowLeft, User } from 'lucide-react';

interface NavbarProps {
  onOpenAuth: () => void;
  onOpenUpload: () => void;
  datasetName?: string;
}

export const Navbar: React.FC<NavbarProps> = ({ onOpenAuth, onOpenUpload, datasetName }) => {
  const { user, isAuthenticated, logout } = useAuthStore();
  const { activeDatasetId, setActiveDatasetId } = useDatasetStore();

  return (
    <header className="sticky top-0 z-40 border-b border-slate-200/80 bg-white/80 dark:border-slate-800/80 dark:bg-slate-950/80 backdrop-blur-xl transition-colors duration-200">
      <div className="mx-auto flex h-16 max-w-7xl items-center justify-between px-4 sm:px-6 lg:px-8">
        <div className="flex items-center gap-4">
          <div
            onClick={() => setActiveDatasetId(null)}
            className="flex cursor-pointer items-center gap-2.5 transition-opacity hover:opacity-90"
          >
            <div className="flex h-10 w-10 items-center justify-center rounded-xl bg-gradient-to-tr from-sky-500 to-indigo-600 shadow-lg shadow-sky-500/20">
              <Database className="h-5 w-5 text-white" />
            </div>
            <div>
              <span className="text-lg font-bold tracking-tight text-slate-900 dark:text-white">Analyst</span>
              <span className="ml-2 rounded-full border border-sky-500/30 bg-sky-500/10 px-2 py-0.5 text-[10px] font-semibold text-sky-600 dark:text-sky-400">
                PROD
              </span>
            </div>
          </div>

          {activeDatasetId && (
            <div className="hidden items-center gap-2 border-l border-slate-200 dark:border-slate-800 pl-4 sm:flex">
              <button
                onClick={() => setActiveDatasetId(null)}
                className="flex items-center gap-1 text-xs font-medium text-slate-500 hover:text-slate-900 dark:text-slate-400 dark:hover:text-slate-200 transition-colors"
              >
                <ArrowLeft className="h-3.5 w-3.5" />
                <span>Datasets</span>
              </button>
              <span className="text-slate-400 dark:text-slate-600">/</span>
              <span className="text-xs font-semibold text-slate-800 dark:text-slate-200 max-w-[200px] truncate">
                {datasetName || 'Dataset Workspace'}
              </span>
            </div>
          )}
        </div>

        <div className="flex items-center gap-3">
          <div className="hidden md:flex items-center gap-2 rounded-full border border-emerald-500/20 bg-emerald-500/5 px-3 py-1 text-xs font-medium text-emerald-600 dark:text-emerald-400">
            <ShieldCheck className="h-3.5 w-3.5" />
            <span>Invariant 1–7 Enforced</span>
          </div>

          {/* Theme Toggle Button */}
          <ThemeToggle />

          {isAuthenticated ? (
            <div className="flex items-center gap-3">
              <button
                onClick={onOpenUpload}
                className="inline-flex items-center gap-1.5 rounded-lg bg-sky-500 px-3.5 py-1.5 text-xs font-semibold text-white shadow-sm hover:bg-sky-400 active:scale-95 transition-all"
              >
                <span>+ Upload Data</span>
              </button>

              <div className="flex items-center gap-2 border-l border-slate-200 dark:border-slate-800 pl-3">
                <div className="flex h-8 w-8 items-center justify-center rounded-full bg-slate-100 text-slate-600 dark:bg-slate-800 dark:text-slate-300">
                  <User className="h-4 w-4" />
                </div>
                <div className="hidden text-left lg:block">
                  <div className="text-xs font-medium text-slate-800 dark:text-slate-200">{user?.full_name || user?.email}</div>
                  <div className="text-[10px] text-slate-500 dark:text-slate-400">{user?.email}</div>
                </div>
                <button
                  onClick={logout}
                  title="Sign out"
                  className="rounded-lg p-1.5 text-slate-500 hover:bg-slate-100 hover:text-slate-700 dark:text-slate-400 dark:hover:bg-slate-800 dark:hover:text-slate-200 transition-colors"
                >
                  <LogOut className="h-4 w-4" />
                </button>
              </div>
            </div>
          ) : (
            <button
              onClick={onOpenAuth}
              className="inline-flex items-center gap-1.5 rounded-lg border border-sky-500/40 bg-sky-500/10 px-4 py-1.5 text-xs font-semibold text-sky-600 hover:bg-sky-500/20 dark:text-sky-400 active:scale-95 transition-all"
            >
              <LogIn className="h-3.5 w-3.5" />
              <span>Sign In / Demo</span>
            </button>
          )}
        </div>
      </div>
    </header>
  );
};

