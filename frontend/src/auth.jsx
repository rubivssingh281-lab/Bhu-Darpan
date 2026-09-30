import { createContext, useContext, useEffect, useState } from "react";
import api from "./api.js";

const AuthContext = createContext(null);

export function AuthProvider({ children }) {
  const [user, setUser] = useState(null);
  const [ready, setReady] = useState(false);

  useEffect(() => {
    const token = localStorage.getItem("bd_token");
    if (!token) {
      setReady(true);
      return;
    }
    api
      .get("/api/auth/me")
      .then((r) => setUser(r.data))
      .catch(() => localStorage.removeItem("bd_token"))
      .finally(() => setReady(true));
  }, []);

  async function login(email, password) {
    const r = await api.post("/api/auth/login", { email, password });
    localStorage.setItem("bd_token", r.data.token);
    setUser(r.data.user);
    return r.data.user;
  }

  async function register(name, email, password) {
    const r = await api.post("/api/auth/register", { name, email, password });
    localStorage.setItem("bd_token", r.data.token);
    setUser(r.data.user);
    return r.data.user;
  }

  function logout() {
    localStorage.removeItem("bd_token");
    setUser(null);
  }

  return (
    <AuthContext.Provider value={{ user, ready, login, register, logout }}>
      {children}
    </AuthContext.Provider>
  );
}

export function useAuth() {
  return useContext(AuthContext);
}
