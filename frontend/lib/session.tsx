"use client";

import React, {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useRef,
  useState
} from "react";

import { api, onSessionExpired, onSessionRefreshed, setAccessToken } from "@/lib/api";
import type { CurrentUser } from "@/lib/types";
import { PERM } from "@/lib/types";

type SessionState = "loading" | "unauthenticated" | "authenticated";

type SessionContextValue = {
  user: CurrentUser | null;
  state: SessionState;
  login: (username: string, password: string) => Promise<void>;
  logout: () => Promise<void>;
  hasPermission: (perm: string) => boolean;
};

const SessionContext = createContext<SessionContextValue | null>(null);

export function SessionProvider({ children }: { children: React.ReactNode }) {
  const [user, setUser] = useState<CurrentUser | null>(null);
  const [state, setState] = useState<SessionState>("loading");
  const didInit = useRef(false);

  const clearSession = useCallback(() => {
    setAccessToken(null);
    setUser(null);
    setState("unauthenticated");
  }, []);

  useEffect(() => {
    onSessionExpired(clearSession);
    onSessionRefreshed((me) => {
      setUser(me);
      setState("authenticated");
    });
  }, [clearSession]);

  useEffect(() => {
    if (didInit.current) return;
    didInit.current = true;

    api
      .refreshSession()
      .then((me) => {
        if (me) {
          setUser(me);
          setState("authenticated");
        } else {
          setState("unauthenticated");
        }
      })
      .catch(() => setState("unauthenticated"));
  }, []);

  const login = useCallback(async (username: string, password: string) => {
    const resp = await api.login(username, password);
    setAccessToken(resp.access_token);
    setUser(resp.user);
    setState("authenticated");
  }, []);

  const logout = useCallback(async () => {
    try {
      await api.logout();
    } catch {
      // ignore
    } finally {
      clearSession();
    }
  }, [clearSession]);

  const hasPermission = useCallback(
    (perm: string) => {
      if (!user) return false;
      return user.permissions.includes(perm);
    },
    [user]
  );

  return (
    <SessionContext.Provider value={{ user, state, login, logout, hasPermission }}>
      {children}
    </SessionContext.Provider>
  );
}

export function useSession(): SessionContextValue {
  const ctx = useContext(SessionContext);
  if (!ctx) throw new Error("useSession must be used inside SessionProvider");
  return ctx;
}
