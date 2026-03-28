/**
 * Global UI State Store using Zustand
 * Manages client-side UI preferences like dark mode, demo mode, and campus selection
 */
import { create } from 'zustand';
import { persist } from 'zustand/middleware';

interface UIState {
  darkMode: boolean;
  demoMode: boolean;
  campus: string;
  toggleDarkMode: () => void;
  toggleDemoMode: () => void;
  setCampus: (campus: string) => void;
}

export const useUIStore = create<UIState>()(
  persist(
    (set) => ({
      darkMode: true, // Default to dark mode for energy monitoring aesthetic
      demoMode: false,
      campus: 'Main Campus',
      
      toggleDarkMode: () => set((state) => ({ darkMode: !state.darkMode })),
      toggleDemoMode: () => set((state) => ({ demoMode: !state.demoMode })),
      setCampus: (campus: string) => set({ campus }),
    }),
    {
      name: 'watt-watch-ui-storage', // LocalStorage key
    }
  )
);
