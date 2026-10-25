import { create } from 'zustand';

interface User {
  id: string;
  email: string;
  full_name?: string;
}

interface AuthState {
  token: string | null;
  user: User | null;
  isAuthenticated: boolean;
  setAuth: (token: string, user: User) => void;
  logout: () => void;
}

export const useAuthStore = create<AuthState>((set) => {
  const savedToken = localStorage.getItem('analyst_token');
  const savedUser = localStorage.getItem('analyst_user');
  let user: User | null = null;
  if (savedUser) {
    try {
      user = JSON.parse(savedUser);
    } catch {
      user = null;
    }
  }

  return {
    token: savedToken,
    user,
    isAuthenticated: !!savedToken,
    setAuth: (token, user) => {
      localStorage.setItem('analyst_token', token);
      localStorage.setItem('analyst_user', JSON.stringify(user));
      set({ token, user, isAuthenticated: true });
    },
    logout: () => {
      localStorage.removeItem('analyst_token');
      localStorage.removeItem('analyst_user');
      set({ token: null, user: null, isAuthenticated: false });
    },
  };
});
