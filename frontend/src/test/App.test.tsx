import { describe, it, expect } from 'vitest';
import { render, screen, fireEvent } from '@testing-library/react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import App from '../App';
import { ThemeToggle } from '../components/ThemeToggle';
import { useThemeStore } from '../store/themeStore';

function renderWithClient(ui: React.ReactElement) {
  const queryClient = new QueryClient({
    defaultOptions: {
      queries: {
        retry: false,
      },
    },
  });
  return render(
    <QueryClientProvider client={queryClient}>
      {ui}
    </QueryClientProvider>
  );
}

describe('App', () => {
  it('renders the platform title and tagline', () => {
    renderWithClient(<App />);
    expect(screen.getByRole('heading', { level: 1 })).toHaveTextContent(/Deterministic Analytics for High-Trust Missions/i);
    expect(screen.getByText(/Production Data Preparation & Insights Platform/i)).toBeInTheDocument();
  });
});

describe('ThemeToggle', () => {
  it('toggles theme between dark and light', () => {
    // Initial state check
    const currentTheme = useThemeStore.getState().theme;
    render(<ThemeToggle />);
    const button = screen.getByRole('button', { name: /switch to/i });
    expect(button).toBeInTheDocument();

    // Click toggle
    fireEvent.click(button);
    const newTheme = useThemeStore.getState().theme;
    expect(newTheme).not.toBe(currentTheme);

    // Toggle back
    fireEvent.click(button);
    expect(useThemeStore.getState().theme).toBe(currentTheme);
  });
});
