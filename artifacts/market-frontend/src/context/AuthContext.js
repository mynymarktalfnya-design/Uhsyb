import React, { createContext, useContext, useState, useEffect } from 'react';
import api, { formatApiError } from '../lib/api';
import { clearSession, getAccessToken, setSession } from '../lib/session';

const AuthContext = createContext();

export const useAuth = () => {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error('useAuth must be used within AuthProvider');
  return ctx;
};

export const AuthProvider = ({ children }) => {
  const [user, setUser] = useState(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const token = getAccessToken();
    if (!token) {
      setLoading(false);
      return;
    }
    api.get('/auth/me')
      .then((r) => setUser(r.data))
      .catch((err) => {
        const status = err?.response?.status;
        if (status === 401 || status === 403) {
          // Server explicitly rejected the token — clear auth state
          clearSession();
        } else {
          // Access tokens are memory-only; a network failure must not create a disk backup.
        }
      })
      .finally(() => setLoading(false));
  }, []);

  const login = async (identifier, password) => {
    try {
      const { data } = await api.post('/auth/login', {
        email_or_username: identifier,
        password,
      });
      setSession(data.access_token, data.user);
      setUser(data.user);
      return { success: true, user: data.user };
    } catch (err) {
      return { success: false, message: formatApiError(err) };
    }
  };

  const logout = async () => {
    try { await api.post('/auth/logout'); } catch (_) { /* ignore */ }
    clearSession();
    setUser(null);
  };

  const can = (...roles) => {
    if (!user) return false;
    if (user.role === 'admin') return true;
    return roles.includes(user.role);
  };

  const value = {
    user,
    isAuthenticated: !!user,
    loading,
    login,
    logout,
    can,
  };
  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
};
