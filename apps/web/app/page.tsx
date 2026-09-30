"use client";

import { useEffect, useState } from "react";
import { Button } from "@/components/ui/button";
import { fetchHealth } from "@/lib/api/client";

interface HealthState {
  status: string;
  db: string;
  version: string;
}

export default function Page() {
  const [health, setHealth] = useState<HealthState | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const checkStatus = async () => {
    setLoading(true);
    setError(null);
    try {
      const data = await fetchHealth();
      setHealth(data);
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : "Connection failed");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    checkStatus();
  }, []);

  return (
    <main className="flex min-h-svh flex-col items-center justify-center p-6 bg-background text-foreground">
      <div className="w-full max-w-lg border rounded-xl p-8 shadow-sm space-y-6 bg-card text-card-foreground">
        <div className="space-y-2">
          <div className="flex items-center justify-between">
            <h1 className="text-2xl font-bold tracking-tight">Garuka</h1>
            <span className="text-xs px-2.5 py-0.5 rounded-full bg-primary/10 text-primary font-medium">
              v0.1.0 (M0)
            </span>
          </div>
          <p className="text-sm text-muted-foreground">
            USSD-based school dropout early-warning and follow-up system for Rwanda.
          </p>
        </div>

        <div className="border rounded-lg p-4 bg-muted/30 space-y-3">
          <div className="flex items-center justify-between text-sm">
            <span className="font-medium text-muted-foreground">Backend API</span>
            <span className="font-mono text-xs">
              {loading ? (
                <span className="text-muted-foreground">checking...</span>
              ) : health?.status === "ok" ? (
                <span className="text-emerald-600 font-semibold">● Online ({health.version})</span>
              ) : error ? (
                <span className="text-destructive font-semibold">● Offline</span>
              ) : (
                <span className="text-muted-foreground">connecting...</span>
              )}
            </span>
          </div>

          <div className="flex items-center justify-between text-sm">
            <span className="font-medium text-muted-foreground">PostgreSQL 16</span>
            <span className="font-mono text-xs">
              {health?.db === "ok" ? (
                <span className="text-emerald-600 font-semibold">● Connected</span>
              ) : (
                <span className="text-muted-foreground">
                  {health?.db || "unreachable"}
                </span>
              )}
            </span>
          </div>

          <div className="flex items-center justify-between text-sm">
            <span className="font-medium text-muted-foreground">USSD Gateway</span>
            <span className="font-mono text-xs text-primary font-semibold">
              *384*1234# (Sandbox)
            </span>
          </div>
        </div>

        <div className="flex items-center gap-3 pt-2">
          <Button onClick={checkStatus} disabled={loading} className="w-full">
            {loading ? "Testing Connection..." : "Re-check Health"}
          </Button>
        </div>
      </div>
    </main>
  );
}
