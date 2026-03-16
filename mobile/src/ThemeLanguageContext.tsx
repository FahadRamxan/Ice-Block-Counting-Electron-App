import React, { createContext, useCallback, useContext, useEffect, useMemo, useState } from 'react';
import AsyncStorage from '@react-native-async-storage/async-storage';
import type { Locale } from './i18n';
import { translate } from './i18n';

const THEME_KEY = 'ice_app_theme';
const LOCALE_KEY = 'ice_app_locale';

export type ThemeMode = 'dark' | 'light';

export const colors = {
  dark: {
    bg: '#0f172a',
    bgPage: 'rgba(15, 23, 42, 0.92)', // Slightly transparent so floating ice shows through
    card: '#1e293b',
    border: '#334155',
    text: '#f1f5f9',
    muted: '#94a3b8',
    accent: '#0ea5e9',
    error: '#f87171',
    success: '#22c55e',
  },
  light: {
    bg: '#f8fafc',
    bgPage: 'rgba(248, 250, 252, 0.92)',
    card: '#ffffff',
    border: '#e2e8f0',
    text: '#0f172a',
    muted: '#64748b',
    accent: '#0284c7',
    error: '#dc2626',
    success: '#16a34a',
  },
};

type Ctx = {
  theme: ThemeMode;
  setTheme: (m: ThemeMode) => void;
  toggleTheme: () => void;
  locale: Locale;
  setLocale: (l: Locale) => void;
  toggleLocale: () => void;
  t: (key: string, vars?: Record<string, string | number>) => string;
  colors: typeof colors.dark;
  isDark: boolean;
};

const ThemeLanguageContext = createContext<Ctx | null>(null);

export function ThemeLanguageProvider({ children }: { children: React.ReactNode }) {
  const [theme, setThemeState] = useState<ThemeMode>('dark');
  const [locale, setLocaleState] = useState<Locale>('en');
  useEffect(() => {
    (async () => {
      try {
        const [t, l] = await Promise.all([
          AsyncStorage.getItem(THEME_KEY),
          AsyncStorage.getItem(LOCALE_KEY),
        ]);
        if (t === 'light' || t === 'dark') setThemeState(t);
        if (l === 'ur' || l === 'en') setLocaleState(l);
      } catch (_) {}
    })();
  }, []);

  const setTheme = useCallback((m: ThemeMode) => {
    setThemeState(m);
    AsyncStorage.setItem(THEME_KEY, m).catch(() => {});
  }, []);

  const setLocale = useCallback((l: Locale) => {
    setLocaleState(l);
    AsyncStorage.setItem(LOCALE_KEY, l).catch(() => {});
  }, []);

  const toggleTheme = useCallback(() => {
    setThemeState((prev) => {
      const next = prev === 'dark' ? 'light' : 'dark';
      AsyncStorage.setItem(THEME_KEY, next).catch(() => {});
      return next;
    });
  }, []);

  const toggleLocale = useCallback(() => {
    setLocaleState((prev) => {
      const next = prev === 'en' ? 'ur' : 'en';
      AsyncStorage.setItem(LOCALE_KEY, next).catch(() => {});
      return next;
    });
  }, []);

  const t = useCallback(
    (key: string, vars?: Record<string, string | number>) => translate(locale, key, vars),
    [locale]
  );

  const themeColors = colors[theme];
  const value = useMemo<Ctx>(
    () => ({
      theme,
      setTheme,
      toggleTheme,
      locale,
      setLocale,
      toggleLocale,
      t,
      colors: themeColors,
      isDark: theme === 'dark',
    }),
    [theme, locale, t, themeColors, setTheme, setLocale, toggleTheme, toggleLocale]
  );

  return (
    <ThemeLanguageContext.Provider value={value}>
      {children}
    </ThemeLanguageContext.Provider>
  );
}

export function useThemeLanguage(): Ctx {
  const ctx = useContext(ThemeLanguageContext);
  if (!ctx) throw new Error('useThemeLanguage must be used within ThemeLanguageProvider');
  return ctx;
}
