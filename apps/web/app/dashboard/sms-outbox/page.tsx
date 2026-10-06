"use client";

import { useEffect, useState } from "react";
import { useAuth } from "@/lib/auth-context";
import { fetchSmsOutbox, retrySms, type SmsOutboxItem } from "@/lib/api/client";
import { ScopeHeader } from "@/components/scope-header";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { AlertTriangle, RefreshCw, Send, RotateCw, CheckCircle2 } from "lucide-react";

export default function SmsOutboxPage() {
  const { user } = useAuth();
  const [items, setItems] = useState<SmsOutboxItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [statusFilter, setStatusFilter] = useState<string>("all");
  const [error, setError] = useState<string | null>(null);
  const [actionSuccess, setActionSuccess] = useState<string | null>(null);
  const [retryingId, setRetryingId] = useState<string | null>(null);

  const loadOutbox = (signal?: AbortSignal) => {
    setLoading(true);
    setError(null);
    fetchSmsOutbox(
      {
        status: statusFilter === "all" ? undefined : statusFilter,
        limit: 100,
      },
      signal
    )
      .then((data) => setItems(data))
      .catch((err) => {
        if (err.name !== "AbortError") {
          setError(err.message || "Failed to load SMS outbox");
        }
      })
      .finally(() => setLoading(false));
  };

  useEffect(() => {
    const controller = new AbortController();
    loadOutbox(controller.signal);
    return () => controller.abort();
  }, [statusFilter]);

  if (!user || user.role !== "admin") {
    return (
      <div className="p-8 text-center">
        <h2 className="text-xl font-bold text-destructive">Access Restricted</h2>
        <p className="text-muted-foreground mt-2">
          Only national system administrators can view the SMS outbox.
        </p>
      </div>
    );
  }

  const handleRetry = async (id: string) => {
    setRetryingId(id);
    setError(null);
    setActionSuccess(null);
    try {
      const updated = await retrySms(id);
      setItems((prev) => prev.map((item) => (item.id === id ? updated : item)));
      setActionSuccess("SMS message re-queued for dispatch.");
    } catch (err: any) {
      setError(err.message || "Failed to retry SMS message");
    } finally {
      setRetryingId(null);
    }
  };

  const getStatusBadge = (status: SmsOutboxItem["status"]) => {
    switch (status) {
      case "delivered":
        return <Badge className="bg-emerald-500/15 text-emerald-700 dark:text-emerald-400">Delivered</Badge>;
      case "sent":
        return <Badge className="bg-blue-500/15 text-blue-700 dark:text-blue-400">Sent</Badge>;
      case "pending":
        return <Badge className="bg-amber-500/15 text-amber-700 dark:text-amber-400">Pending</Badge>;
      case "failed":
        return <Badge variant="destructive">Failed</Badge>;
      case "skipped":
        return <Badge variant="outline">Skipped (Quiet Hours)</Badge>;
      default:
        return <Badge variant="secondary">{status}</Badge>;
    }
  };

  const formatKigaliTime = (isoString: string) => {
    try {
      return new Date(isoString).toLocaleString("en-GB", {
        timeZone: "Africa/Kigali",
        month: "short",
        day: "numeric",
        hour: "2-digit",
        minute: "2-digit",
      });
    } catch {
      return isoString;
    }
  };

  return (
    <div className="space-y-6 max-w-6xl">
      <ScopeHeader
        title="SMS Outbox & Delivery Monitoring"
        description="Monitor automated parent absence alerts, OTP verification codes, and provider delivery status."
        scope={{ level: "national", name: "Rwanda" }}
      >
        <Button
          variant="outline"
          size="sm"
          onClick={() => loadOutbox()}
          disabled={loading || !!retryingId}
        >
          <RefreshCw className={`h-4 w-4 mr-1.5 ${loading ? "animate-spin" : ""}`} />
          Refresh
        </Button>
      </ScopeHeader>

      {error && (
        <div
          role="alert"
          className="p-4 bg-destructive/15 border border-destructive/20 text-destructive rounded-lg flex items-center justify-between"
        >
          <div className="flex items-center gap-2 text-sm font-medium">
            <AlertTriangle className="h-4 w-4 shrink-0" />
            <span>{error}</span>
          </div>
          <Button variant="outline" size="sm" onClick={() => loadOutbox()}>
            Retry
          </Button>
        </div>
      )}

      {actionSuccess && (
        <div
          role="status"
          className="p-4 bg-emerald-500/15 border border-emerald-500/20 text-emerald-700 dark:text-emerald-400 rounded-lg flex items-center gap-2 text-sm font-medium"
        >
          <CheckCircle2 className="h-4 w-4 shrink-0" />
          <span>{actionSuccess}</span>
        </div>
      )}

      {/* Filter Tabs */}
      <div className="flex flex-wrap items-center gap-2">
        {["all", "failed", "pending", "sent", "delivered", "skipped"].map((st) => (
          <Button
            key={st}
            variant={statusFilter === st ? "default" : "outline"}
            size="sm"
            onClick={() => setStatusFilter(st)}
            className="capitalize text-xs h-8"
          >
            {st}
          </Button>
        ))}
      </div>

      <Card>
        <CardHeader className="py-4">
          <CardTitle className="text-base font-semibold flex items-center justify-between">
            <span>Outbox Messages ({items.length})</span>
            <span className="text-xs text-muted-foreground font-normal">
              Showing latest up to 100 messages
            </span>
          </CardTitle>
        </CardHeader>
        <CardContent className="p-0">
          {loading ? (
            <div className="p-12 text-center text-sm text-muted-foreground animate-pulse">
              Loading SMS outbox records...
            </div>
          ) : items.length === 0 ? (
            <div className="p-12 text-center text-sm text-muted-foreground">
              No SMS messages found matching filter "{statusFilter}".
            </div>
          ) : (
            <div className="overflow-x-auto">
              <table className="w-full text-left text-sm">
                <thead className="bg-muted/50 border-y text-xs uppercase text-muted-foreground font-semibold">
                  <tr>
                    <th className="px-4 py-3">Scheduled (Kigali)</th>
                    <th className="px-4 py-3">Recipient</th>
                    <th className="px-4 py-3">Template</th>
                    <th className="px-4 py-3">Message Body</th>
                    <th className="px-4 py-3">Status</th>
                    <th className="px-4 py-3 text-right">Actions</th>
                  </tr>
                </thead>
                <tbody className="divide-y">
                  {items.map((msg) => (
                    <tr key={msg.id} className="hover:bg-muted/20">
                      <td className="px-4 py-3 whitespace-nowrap text-xs text-muted-foreground">
                        {formatKigaliTime(msg.scheduled_at)}
                      </td>
                      <td className="px-4 py-3 font-mono text-xs text-foreground whitespace-nowrap">
                        {msg.to_e164}
                      </td>
                      <td className="px-4 py-3 whitespace-nowrap">
                        <span className="text-xs font-medium text-foreground bg-muted px-2 py-0.5 rounded">
                          {msg.template_key}
                        </span>
                      </td>
                      <td className="px-4 py-3 max-w-xs md:max-w-md">
                        <p className="text-xs text-foreground truncate" title={msg.body}>
                          {msg.body}
                        </p>
                        {msg.last_error && (
                          <p className="text-xs text-destructive mt-0.5 truncate" title={msg.last_error}>
                            Error: {msg.last_error}
                          </p>
                        )}
                      </td>
                      <td className="px-4 py-3 whitespace-nowrap">
                        <div className="flex items-center gap-1.5">
                          {getStatusBadge(msg.status)}
                          {msg.attempts > 1 && (
                            <span className="text-[10px] text-muted-foreground">
                              ({msg.attempts} tries)
                            </span>
                          )}
                        </div>
                      </td>
                      <td className="px-4 py-3 text-right whitespace-nowrap">
                        {msg.status === "failed" && (
                          <Button
                            variant="outline"
                            size="sm"
                            onClick={() => handleRetry(msg.id)}
                            disabled={retryingId === msg.id}
                            className="h-7 text-xs px-2.5"
                          >
                            <RotateCw
                              className={`h-3 w-3 mr-1 ${
                                retryingId === msg.id ? "animate-spin" : ""
                              }`}
                            />
                            {retryingId === msg.id ? "Queuing..." : "Retry"}
                          </Button>
                        )}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </CardContent>
      </Card>
    </div>
  );
}
