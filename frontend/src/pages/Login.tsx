import { useState } from "react";
import { api } from "@/api/client";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";

export function Login() {
  const [email, setEmail] = useState("");
  const [token, setToken] = useState("");
  const [stage, setStage] = useState<"email" | "sent" | "done">("email");
  const [err, setErr] = useState<string | null>(null);

  const requestLink = async (e: React.FormEvent) => {
    e.preventDefault();
    setErr(null);
    try {
      const r = await api.post<{ ok: boolean; dev_token?: string }>(
        "/auth/request", { email }
      );
      setStage("sent");
      if (r.dev_token) setToken(r.dev_token);
    } catch (e: any) {
      setErr(e?.body?.detail || e?.message || "Request failed.");
    }
  };

  const verify = async (e: React.FormEvent) => {
    e.preventDefault();
    setErr(null);
    try {
      await api.post("/auth/verify", { email, token });
      window.location.href = "/";
    } catch (e: any) {
      setErr(e?.body?.detail || e?.message || "Verification failed.");
    }
  };

  return (
    <div className="min-h-screen flex items-center justify-center p-6">
      <div className="w-full max-w-sm rounded-lg border border-border bg-card p-6">
        <h1 className="text-xl font-bold mb-1">CELR Procurement</h1>
        <p className="text-sm text-muted mb-6">Sign in to continue</p>

        {stage === "email" && (
          <form onSubmit={requestLink} className="flex flex-col gap-3">
            <label className="text-xs text-muted">Email</label>
            <Input
              type="email" required value={email}
              onChange={e => setEmail(e.target.value)}
              placeholder="you@example.com"
            />
            <Button type="submit">Send magic link</Button>
          </form>
        )}

        {stage === "sent" && (
          <form onSubmit={verify} className="flex flex-col gap-3">
            <p className="text-sm">
              Check <b>{email}</b> for a sign-in link. Or paste the token below.
            </p>
            <label className="text-xs text-muted">Token</label>
            <Input value={token} onChange={e => setToken(e.target.value)} placeholder="token-from-email" />
            <Button type="submit">Sign in</Button>
            <button type="button" className="text-xs text-muted hover:text-fg mt-2" onClick={() => setStage("email")}>
              ← use a different email
            </button>
          </form>
        )}

        {err && <p className="text-sm text-bad mt-3">{err}</p>}

        <p className="text-[11px] text-muted/70 mt-6">
          Magic-link uses one-time, time-limited tokens. Allowlisted addresses only.
        </p>
      </div>
    </div>
  );
}
