import { createContext, useContext, useState, useEffect, useCallback, type ReactNode } from "react";
import { api } from "../api/client";
import type { User } from "../types";

interface AuthContextType {
  user: User | null;
  isLoading: boolean;
  login: (username: string, password: string) => Promise<void>;
  register: (username: string, email: string, password: string, displayName?: string) => Promise<void>;
  logout: () => void;
}

const AuthContext = createContext<AuthContextType | null>(null);

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<User | null>(null);
  const [isLoading, setIsLoading] = useState(true);

  useEffect(() => {
    const token = localStorage.getItem("cb_token");
    if (token) {
      api
        .authProfile()
        .then(setUser)
        .catch(() => localStorage.removeItem("cb_token"))
        .finally(() => setIsLoading(false));
    } else {
      setIsLoading(false);
    }
  }, []);

  const login = useCallback(async (username: string, password: string) => {
    const res = await api.authLogin({ username, password });
    localStorage.setItem("cb_token", res.token);
    setUser(res.user);
  }, []);

  const register = useCallback(
    async (username: string, email: string, password: string, displayName?: string) => {
      const res = await api.authRegister({ username, email, password, display_name: displayName });
      localStorage.setItem("cb_token", res.token);
      setUser(res.user);
    },
    []
  );

  const logout = useCallback(() => {
    localStorage.removeItem("cb_token");
    setUser(null);
  }, []);

  return (
    <AuthContext.Provider value={{ user, isLoading, login, register, logout }}>
      {children}
    </AuthContext.Provider>
  );
}

export function useAuth() {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error("useAuth must be used within AuthProvider");
  return ctx;
}
