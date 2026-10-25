import { createContext, useCallback, useContext, useEffect, useState } from "react";
import { api } from "./api";

const AuthContext = createContext(null);

export function AuthProvider({ children }) {
  const [user, setUser] = useState(null);
  const [loading, setLoading] = useState(true);

  const reload = useCallback(async () => {
    try {
      setUser(await api("/users/me/"));
    } catch {
      setUser(null);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    fetch("/api/auth/csrf/", { credentials: "include" }).finally(reload);
  }, [reload]);

  const login = async (email, password) => {
    const profile = await api("/auth/login/", { method: "POST", body: { email, password } });
    setUser(profile);
    return profile;
  };
  const logout = async () => {
    await api("/auth/logout/", { method: "POST" }).catch(() => {});
    setUser(null);
  };

  return (
    <AuthContext.Provider value={{ user, loading, login, logout, reload, setUser }}>
      {children}
    </AuthContext.Provider>
  );
}

export const useAuth = () => useContext(AuthContext);
