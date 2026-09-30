"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { useAuth } from "@/lib/auth-context";
import { Button } from "@/components/ui/button";

export default function LoginPage() {
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const { login } = useAuth();
  const router = useRouter();

  const handleLogin = async (e?: React.FormEvent) => {
    if (e) e.preventDefault();
    setError(null);
    setLoading(true);
    try {
      await login(email, password);
      router.push("/dashboard");
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : "Authentication failed");
    } finally {
      setLoading(false);
    }
  };

  const quickLogin = (presetEmail: string) => {
    setEmail(presetEmail);
    setPassword("ChangeMe123!");
    setError(null);
    setLoading(true);
    login(presetEmail, "ChangeMe123!")
      .then(() => router.push("/dashboard"))
      .catch((err) => setError(err.message))
      .finally(() => setLoading(false));
  };

  return (
    <div className="min-h-screen flex items-center justify-center bg-muted/40 p-4">
      <div className="w-full max-w-md bg-card border rounded-xl p-8 shadow-sm space-y-6">
        <div className="space-y-1 text-center">
          <h1 className="text-2xl font-bold tracking-tight text-primary">Garuka Dashboard</h1>
          <p className="text-sm text-muted-foreground">Sign in to manage dropout early-warning system</p>
        </div>

        {error && (
          <div className="p-3 text-xs bg-destructive/15 border border-destructive/30 text-destructive rounded-lg font-medium">
            {error}
          </div>
        )}

        <form onSubmit={handleLogin} className="space-y-4">
          <div className="space-y-1">
            <label className="text-xs font-semibold uppercase text-muted-foreground">Email</label>
            <input
              type="email"
              required
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              placeholder="user@garuka.rw"
              className="w-full px-3 py-2 border rounded-md text-sm bg-background focus:outline-none focus:ring-2 focus:ring-primary"
            />
          </div>

          <div className="space-y-1">
            <label className="text-xs font-semibold uppercase text-muted-foreground">Password</label>
            <input
              type="password"
              required
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              placeholder="••••••••••••"
              className="w-full px-3 py-2 border rounded-md text-sm bg-background focus:outline-none focus:ring-2 focus:ring-primary"
            />
          </div>

          <Button type="submit" disabled={loading} className="w-full">
            {loading ? "Signing in..." : "Sign In"}
          </Button>
        </form>

        <div className="pt-4 border-t space-y-2">
          <p className="text-xs text-muted-foreground text-center font-medium">Demo Quick Sign-In</p>
          <div className="grid grid-cols-2 gap-2">
            <Button variant="outline" size="sm" onClick={() => quickLogin("admin@garuka.rw")}>
              Admin
            </Button>
            <Button variant="outline" size="sm" onClick={() => quickLogin("head@gsdemo1.rw")}>
              Head Teacher
            </Button>
            <Button variant="outline" size="sm" onClick={() => quickLogin("seo@tumba.gov.rw")}>
              Sector Officer
            </Button>
            <Button variant="outline" size="sm" onClick={() => quickLogin("director@huye.gov.rw")}>
              District Director
            </Button>
          </div>
        </div>
      </div>
    </div>
  );
}
