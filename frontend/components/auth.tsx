"use client";

import { LogIn, LogOut, Shield, User } from "lucide-react";
import { useState } from "react";

import { useSession } from "@/lib/session";
import { Button } from "@/components/ui";

// ── Login View ─────────────────────────────────────────────────────────────

export function LoginView() {
  const { login } = useSession();
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setError(null);
    setLoading(true);
    try {
      await login(username, password);
    } catch {
      setError("Invalid credentials");
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="flex min-h-screen items-center justify-center p-4">
      <div className="w-full max-w-sm rounded border border-warm bg-canvas/95 p-6 shadow-sm">
        <div className="mb-6 flex items-center gap-3">
          <Shield className="h-5 w-5 text-accent" />
          <div>
            <p className="font-mono text-[11px] uppercase text-muted">Star Pulse</p>
            <h1 className="text-lg font-semibold">Sign in</h1>
          </div>
        </div>

        <form onSubmit={(e) => void handleSubmit(e)} className="space-y-4">
          <div>
            <label className="mb-1 block font-mono text-[11px] uppercase text-muted">
              Username
            </label>
            <input
              type="text"
              autoComplete="username"
              value={username}
              onChange={(e) => setUsername(e.target.value)}
              required
              className="w-full rounded border border-warm bg-paper px-3 py-2 text-sm text-ink focus:outline-none focus:ring-1 focus:ring-accent/50"
            />
          </div>
          <div>
            <label className="mb-1 block font-mono text-[11px] uppercase text-muted">
              Password
            </label>
            <input
              type="password"
              autoComplete="current-password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              required
              className="w-full rounded border border-warm bg-paper px-3 py-2 text-sm text-ink focus:outline-none focus:ring-1 focus:ring-accent/50"
            />
          </div>
          {error ? (
            <p className="text-sm text-error">{error}</p>
          ) : null}
          <Button type="submit" busy={loading} className="w-full justify-center">
            <LogIn className="h-4 w-4" aria-hidden="true" />
            Sign in
          </Button>
        </form>
      </div>
    </div>
  );
}

// ── Session Header ─────────────────────────────────────────────────────────

export function SessionHeader() {
  const { user, logout } = useSession();
  const [busy, setBusy] = useState(false);

  if (!user) return null;

  async function handleLogout() {
    setBusy(true);
    try {
      await logout();
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="flex items-center gap-3">
      <div className="flex items-center gap-2 text-xs text-muted">
        <User className="h-3.5 w-3.5" aria-hidden="true" />
        <span className="font-medium text-ink">{user.display_name}</span>
        <span className="hidden sm:inline">
          ({user.roles.join(", ") || "no role"})
        </span>
      </div>
      <Button
        onClick={() => void handleLogout()}
        busy={busy}
        className="h-8 px-2 text-xs"
        title="Sign out"
        aria-label="Sign out"
      >
        <LogOut className="h-3.5 w-3.5" aria-hidden="true" />
        <span className="hidden sm:inline">Sign out</span>
      </Button>
    </div>
  );
}
