import { useState } from "react";
import { api } from "@/api/client";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";

export function Login() {
  const [username, setUsername] = useState("admin");
  const [password, setPassword] = useState("");
  const [loading, setLoading] = useState(false);
  const [err, setErr] = useState<string | null>(null);

  const submit = async (e: React.FormEvent) => {
    e.preventDefault();
    setErr(null);
    setLoading(true);
    try {
      await api.post("/auth/login", { username, password });
      window.location.href = "/";
    } catch (e: any) {
      setErr(e?.body?.detail || e?.message || "Sign-in failed");
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="min-h-screen flex items-center justify-center p-6">
      <div className="w-full max-w-sm rounded-lg border border-border bg-card p-6">
        <h1 className="text-xl font-bold mb-1">CELR Procurement</h1>
        <p className="text-sm text-muted mb-6">Sign in to continue</p>

        <form onSubmit={submit} className="flex flex-col gap-3">
          <label className="text-xs text-muted">Username
            <Input
              value={username}
              onChange={e => setUsername(e.target.value)}
              autoComplete="username"
              required
              className="mt-1"
            />
          </label>
          <label className="text-xs text-muted">Password
            <Input
              type="password"
              value={password}
              onChange={e => setPassword(e.target.value)}
              autoComplete="current-password"
              required
              className="mt-1"
            />
          </label>
          <Button type="submit" disabled={loading}>
            {loading ? "Signing in…" : "Sign in"}
          </Button>
          {err && <p className="text-sm text-bad mt-1">{err}</p>}
        </form>

        <p className="text-[11px] text-muted/70 mt-6">
          Demo credentials are <code>admin</code> / <code>admin</code> unless
          overridden via <code>AUTH_USERNAME</code> / <code>AUTH_PASSWORD</code>
          env vars in Render.
        </p>
      </div>
    </div>
  );
}
