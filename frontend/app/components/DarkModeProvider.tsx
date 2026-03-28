/**
 * Dark Mode Provider - Client Component
 * Applies dark mode class to HTML element based on global UI store
 */
'use client';

import { useEffect } from 'react';
import { useUIStore } from '../store/uiStore';

export default function DarkModeProvider({ children }: { children: React.ReactNode }) {
  const darkMode = useUIStore((state) => state.darkMode);

  useEffect(() => {
    // Apply dark mode class to html element
    if (darkMode) {
      document.documentElement.classList.add('dark');
    } else {
      document.documentElement.classList.remove('dark');
    }
  }, [darkMode]);

  return <>{children}</>;
}
