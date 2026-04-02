import { createContext, useContext, useEffect, useMemo, useState } from "react";
import { changeOwnPassword, fetchCurrentUser, login as loginRequest, logout as logoutRequest } from "../../api/accounts";
import {
  clearStoredSession,
  readStoredSession,
  setUnauthorizedHandler,
  writeStoredSession,
} from "../../api/http";
import type { CurrentUser } from "../../api/types";

type AuthStatus = "loading" | "authenticated" | "anonymous";

type AuthContextValue = {
  status: AuthStatus;
  user: CurrentUser | null;
  login: (identifier: string, password: string) => Promise<void>;
  logout: () => Promise<void>;
  refreshUser: () => Promise<void>;
  changePassword: (payload: { current_password: string; new_password: string; confirm_password: string }) => Promise<void>;
};

const AuthContext = createContext<AuthContextValue | null>(null);

export function AuthProvider({ children }: { children: React.ReactNode }) {
  const [status, setStatus] = useState<AuthStatus>("loading");
  const [user, setUser] = useState<CurrentUser | null>(null);

  useEffect(() => {
    setUnauthorizedHandler(() => {
      clearStoredSession();
      setUser(null);
      setStatus("anonymous");
    });

    const bootstrap = async () => {
      const session = readStoredSession();
      if (!session) {
        setStatus("anonymous");
        return;
      }

      try {
        const nextUser = await fetchCurrentUser();
        setUser(nextUser);
        setStatus("authenticated");
      } catch {
        clearStoredSession();
        setUser(null);
        setStatus("anonymous");
      }
    };

    void bootstrap();

    return () => setUnauthorizedHandler(null);
  }, []);

  const login = async (identifier: string, password: string) => {
    const session = await loginRequest(identifier, password);
    writeStoredSession({ access: session.access, refresh: session.refresh });
    setUser(session.user);
    setStatus("authenticated");
  };

  const logout = async () => {
    const session = readStoredSession();
    try {
      if (session?.refresh) {
        await logoutRequest(session.refresh);
      }
    } catch {
      // noop
    } finally {
      clearStoredSession();
      setUser(null);
      setStatus("anonymous");
    }
  };

  const refreshUser = async () => {
    const nextUser = await fetchCurrentUser();
    setUser(nextUser);
    setStatus("authenticated");
  };

  const changePassword = async (payload: { current_password: string; new_password: string; confirm_password: string }) => {
    const nextUser = await changeOwnPassword(payload);
    setUser(nextUser);
    setStatus("authenticated");
  };

  const value = useMemo<AuthContextValue>(
    () => ({ status, user, login, logout, refreshUser, changePassword }),
    [status, user],
  );

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth() {
  const context = useContext(AuthContext);
  if (!context) {
    throw new Error("useAuth debe usarse dentro de AuthProvider.");
  }
  return context;
}
