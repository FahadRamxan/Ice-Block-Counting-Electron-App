import React, { createContext, useCallback, useContext, useEffect, useState } from 'react';
import AsyncStorage from '@react-native-async-storage/async-storage';

const AUTH_KEY = 'awan_ice_user';

type User = { name: string; email: string };

type Ctx = {
  user: User | null;
  setUser: (u: User | null) => void;
  logout: () => void;
};

const AuthContext = createContext<Ctx | null>(null);

export function AuthProvider({ children }: { children: React.ReactNode }) {
  const [user, setUserState] = useState<User | null>(null);

  useEffect(() => {
    AsyncStorage.getItem(AUTH_KEY).then((s) => {
      if (!s) return;
      try {
        const u = JSON.parse(s) as User;
        if (u?.name && u?.email) setUserState(u);
      } catch (_) {}
    });
  }, []);

  const setUser = useCallback((u: User | null) => {
    setUserState(u);
    if (u) AsyncStorage.setItem(AUTH_KEY, JSON.stringify(u)).catch(() => {});
    else AsyncStorage.removeItem(AUTH_KEY).catch(() => {});
  }, []);

  const logout = useCallback(() => {
    setUserState(null);
    AsyncStorage.removeItem(AUTH_KEY).catch(() => {});
  }, []);

  return (
    <AuthContext.Provider value={{ user, setUser, logout }}>
      {children}
    </AuthContext.Provider>
  );
}

export function useAuth(): Ctx {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error('useAuth must be used within AuthProvider');
  return ctx;
}
