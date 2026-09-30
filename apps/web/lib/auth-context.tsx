"use client";

import React, { createContext, useContext, useEffect, useState } from "react";
import type { paths } from "@/lib/api/schema";

export type UserMe = paths["/api/v1/auth/me"]["get"]["responses"]["200"]["content"]["application/json"];

interface AuthContextType {
  user: UserMe | null;
  token: string | null;
  login: (email: string, password: string) => Promise<UserMe>;
  logout: () => void;
  isLoading: boolean;
}

const AuthContext = createContext<AuthContextType | undefined>(undefined);

export function AuthProvider({ children }: { children: React.ReactNode }) {
  const [user, setUser] = useState<UserMe | null>(null);
  const [token, setToken] = useState<string | null>(null);
  const [isLoading, setIsLoading] = useState(true);

  const API_BASE_URL = process.env.NEXT_PUBLIC_API_BASE_URL || "http://localhost:8000/api/v1";

  useEffect(() => {
    const savedToken = localStorage.getItem("garuka_token");
    if (savedToken) {
      setToken(savedToken);
      fetch(`${API_BASE_URL}/auth/me`, {
        headers: { Authorization: `Bearer ${savedToken}` },
      })
        .then((res) => {
          if (res.ok) return res.json();
          throw new Error("Invalid session");
        })
        .then((userData) => setUser(userData))
        .catch(() => {
          localStorage.removeItem("garuka_token");
          setToken(null);
          setUser(null);
        })
        .finally(() => setIsLoading(false));
    } else {
      setIsLoading(false);
    }
  }, [API_BASE_URL]);

  const login = async (email: string, password: string): Promise<UserMe> => {
    const res = await fetch(`${API_BASE_URL}/auth/login`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ email, password }),
    });

    if (!res.ok) {
      const err = await res.json().catch(() => ({ detail: "Login failed" }));
      throw new Error(err.detail || "Incorrect email or password");
    }

    const data = await res.json();
    setToken(data.access_token);
    setUser(data.user);
    localStorage.setItem("garuka_token", data.access_token);
    return data.user;
  };

  const logout = () => {
    localStorage.removeItem("garuka_token");
    setToken(null);
    setUser(null);
  };

  return (
    <AuthContext.Provider value={{ user, token, login, logout, isLoading }}>
      {children}
    </AuthContext.Provider>
  );
}

export function useAuth() {
  const context = useContext(AuthContext);
  if (!context) {
    throw new Error("useAuth must be used within an AuthProvider");
  }
  return context;
}
