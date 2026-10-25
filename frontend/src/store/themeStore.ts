import { create } from 'zustand';

export type Theme = 'dark' | 'light';

interface ThemeState {
  theme: Theme;
  setTheme: (theme: Theme) => void;
  toggleTheme: () => void;
}

const getInitialTheme = (): Theme => {
  if (typeof window === 'undefined') return 'dark';
  const saved = localStorage.getItem('analyst_theme') as Theme | null;
  if (saved === 'dark' || saved === 'light') return saved;
  // Default to dark theme for professional analyst look
  return 'dark';
};

const applyThemeToDOM = (theme: Theme) => {
  if (typeof document === 'undefined') return;
  const root = document.documentElement;
  if (theme === 'dark') {
    root.classList.add('dark');
    root.classList.remove('light');
    root.style.colorScheme = 'dark';
  } else {
    root.classList.remove('dark');
    root.classList.add('light');
    root.style.colorScheme = 'light';
  }
};

export const useThemeStore = create<ThemeState>((set, get) => {
  const initialTheme = getInitialTheme();
  // Apply initially on store instantiation
  applyThemeToDOM(initialTheme);

  return {
    theme: initialTheme,
    setTheme: (theme: Theme) => {
      localStorage.setItem('analyst_theme', theme);
      applyThemeToDOM(theme);
      set({ theme });
    },
    toggleTheme: () => {
      const nextTheme: Theme = get().theme === 'dark' ? 'light' : 'dark';
      localStorage.setItem('analyst_theme', nextTheme);
      applyThemeToDOM(nextTheme);
      set({ theme: nextTheme });
    },
  };
});
