import { create } from 'zustand';

export type WorkspaceTab = 'profile' | 'proposals' | 'insights' | 'query' | 'exports';

interface DatasetState {
  activeDatasetId: string | null;
  activeTab: WorkspaceTab;
  setActiveDatasetId: (id: string | null) => void;
  setActiveTab: (tab: WorkspaceTab) => void;
  toastMessage: { text: string; type: 'success' | 'error' | 'info' } | null;
  showToast: (text: string, type?: 'success' | 'error' | 'info') => void;
  clearToast: () => void;
}

export const useDatasetStore = create<DatasetState>((set) => ({
  activeDatasetId: null,
  activeTab: 'profile',
  setActiveDatasetId: (id) => set({ activeDatasetId: id, activeTab: 'profile' }),
  setActiveTab: (tab) => set({ activeTab: tab }),
  toastMessage: null,
  showToast: (text, type = 'info') => {
    set({ toastMessage: { text, type } });
    setTimeout(() => {
      set({ toastMessage: null });
    }, 4000);
  },
  clearToast: () => set({ toastMessage: null }),
}));
