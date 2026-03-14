import React, { createContext, useCallback, useContext, useEffect, useMemo, useState } from 'react';
import type { Locale } from './i18n';
import { t as translate } from './i18n';

export type ThemeMode = 'dark' | 'light';

const THEME_KEY = 'ice_app_theme';
const LOCALE_KEY = 'ice_app_locale';

type Ctx = {
  theme: ThemeMode;
  setTheme: (m: ThemeMode) => void;
  toggleTheme: () => void;
  locale: Locale;
  setLocale: (l: Locale) => void;
  toggleLocale: () => void;
  t: (key: string, vars?: Record<string, string | number>) => string;
  dir: 'ltr' | 'rtl';
};

const ThemeLanguageContext = createContext<Ctx | null>(null);

function readStoredTheme(): ThemeMode {
  try {
    const v = localStorage.getItem(THEME_KEY);
    if (v === 'light' || v === 'dark') return v;
  } catch (_) {}
  return 'dark';
}

function readStoredLocale(): Locale {
  try {
    const v = localStorage.getItem(LOCALE_KEY);
    if (v === 'ur' || v === 'en') return v;
  } catch (_) {}
  return 'en';
}

export function ThemeLanguageProvider({ children }: { children: React.ReactNode }) {
  const [theme, setThemeState] = useState<ThemeMode>(() => readStoredTheme());
  const [locale, setLocaleState] = useState<Locale>(() => readStoredLocale());

  const setTheme = useCallback((m: ThemeMode) => {
    setThemeState(m);
    try {
      localStorage.setItem(THEME_KEY, m);
    } catch (_) {}
    document.documentElement.setAttribute('data-theme', m);
  }, []);

  const setLocale = useCallback((l: Locale) => {
    setLocaleState(l);
    try {
      localStorage.setItem(LOCALE_KEY, l);
    } catch (_) {}
    document.documentElement.lang = l === 'ur' ? 'ur' : 'en';
    document.documentElement.dir = l === 'ur' ? 'rtl' : 'ltr';
  }, []);

  useEffect(() => {
    document.documentElement.setAttribute('data-theme', theme);
    document.documentElement.lang = locale === 'ur' ? 'ur' : 'en';
    document.documentElement.dir = locale === 'ur' ? 'rtl' : 'ltr';
  }, [theme, locale]);

  const toggleTheme = useCallback(() => {
    setTheme(theme === 'dark' ? 'light' : 'dark');
  }, [theme, setTheme]);

  const toggleLocale = useCallback(() => {
    setLocale(locale === 'en' ? 'ur' : 'en');
  }, [locale, setLocale]);

  const t = useCallback(
    (key: string, vars?: Record<string, string | number>) => translate(locale, key, vars),
    [locale]
  );

  const value = useMemo(
    () => ({
      theme,
      setTheme,
      toggleTheme,
      locale,
      setLocale,
      toggleLocale,
      t,
      dir: locale === 'ur' ? ('rtl' as const) : ('ltr' as const),
    }),
    [theme, setTheme, toggleTheme, locale, setLocale, toggleLocale, t]
  );

  return <ThemeLanguageContext.Provider value={value}>{children}</ThemeLanguageContext.Provider>;
}

export function useThemeLanguage() {
  const ctx = useContext(ThemeLanguageContext);
  if (!ctx) throw new Error('useThemeLanguage outside ThemeLanguageProvider');
  return ctx;
}
