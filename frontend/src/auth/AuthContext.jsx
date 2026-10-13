import { createContext, useCallback, useContext, useEffect, useMemo, useState } from 'react';
import { useQueryClient } from '@tanstack/react-query';
import { api, auth } from '../services/api';

const AuthContext = createContext(null);

export function AuthProvider({ children }) {
  const [session, setSession] = useState(auth.get());
  const queryClient = useQueryClient();

  useEffect(() => auth.subscribe(setSession), []);

  const login = useCallback(async (username, password) => {
    const data = await api.post('auth/login', { username, password });
    auth.set(data);
    return data.user;
  }, []);

  const logout = useCallback(() => {
    const refreshToken = auth.get()?.refresh_token;
    auth.set(null);
    queryClient.clear();
    if (refreshToken) api.post('auth/logout', { refresh_token: refreshToken }).catch(() => {});
  }, [queryClient]);

  const updateUser = useCallback((changes) => {
    const current = auth.get();
    if (current) auth.set({ ...current, user: { ...current.user, ...changes } });
  }, []);

  const value = useMemo(() => {
    const user = session?.user ?? null;
    return { user, login, logout, updateUser, hasRole: (...roles) => Boolean(user) && roles.includes(user.role) };
  }, [session, login, logout, updateUser]);

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth() {
  const context = useContext(AuthContext);
  if (!context) throw new Error('useAuth must be used inside AuthProvider');
  return context;
}