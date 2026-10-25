import React from 'react';
import { Sun, Moon } from 'lucide-react';
import { useThemeStore } from '../store/themeStore';

interface ThemeToggleProps {
  className?: string;
}

export const ThemeToggle: React.FC<ThemeToggleProps> = ({ className = '' }) => {
  const { theme, toggleTheme } = useThemeStore();
  const isDark = theme === 'dark';

  return (
    <button
      type="button"
      onClick={toggleTheme}
      aria-label={`Switch to ${isDark ? 'light' : 'dark'} mode`}
      title={`Switch to ${isDark ? 'light' : 'dark'} mode`}
      className={`group relative flex h-9 w-9 items-center justify-center rounded-xl border transition-all duration-200 active:scale-95 ${
        isDark
          ? 'border-slate-800 bg-slate-900/80 text-amber-400 hover:border-amber-500/40 hover:bg-slate-800 hover:text-amber-300 shadow-sm'
          : 'border-slate-300/80 bg-white text-indigo-600 hover:border-indigo-400 hover:bg-slate-50 hover:text-indigo-700 shadow-sm shadow-slate-200/50'
      } ${className}`}
    >
      <div className="relative flex items-center justify-center">
        {isDark ? (
          <Sun className="h-4 w-4 transition-transform duration-300 group-hover:rotate-45" />
        ) : (
          <Moon className="h-4 w-4 transition-transform duration-300 group-hover:-rotate-12" />
        )}
      </div>
    </button>
  );
};
