"use client";

import { useEffect, useState } from "react";
import { useAuth } from "@/lib/auth-context";
import { fetchAuditLogs, type AuditLogItem } from "@/lib/api/client";
import { ScopeHeader } from "@/components/scope-header";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { AlertTriangle, RefreshCw, ShieldCheck, ChevronRight, ChevronDown } from "lucide-react";

export default function AuditLogsPage() {
  const { user } = useAuth();
  const [logs, setLogs] = useState<AuditLogItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [actionFilter, setActionFilter] = useState<string>("");
  const [entityTypeFilter, setEntityTypeFilter] = useState<string>("");
  const [error, setError] = useState<string | null>(null);
  const [expandedRowId, setExpandedRowId] = useState<string | null>(null);

  const loadLogs = (signal?: AbortSignal) => {
    setLoading(true);
    setError(null);
    fetchAuditLogs(
      {
        action: actionFilter || undefined,
        entity_type: entityTypeFilter || undefined,
        limit: 100,
      },
      signal
    )
      .then((data) => setLogs(data))
      .catch((err) => {
        if (err.name !== "AbortError") {
          setError(err.message || "Failed to load audit logs");
        }
      })
      .finally(() => setLoading(false));
  };

  useEffect(() => {
    const controller = new AbortController();
    loadLogs(controller.signal);
    return () => controller.abort();
  }, [actionFilter, entityTypeFilter]);

  if (!user || user.role !== "admin") {
    return (
      <div className="p-8 text-center">
        <h2 className="text-xl font-bold text-destructive">Access Restricted</h2>
        <p className="text-muted-foreground mt-2">
          Only national system administrators can view security and audit logs.
        </p>
      </div>
    );
  }

  const formatKigaliTime = (isoString: string) => {
    try {
      return new Date(isoString).toLocaleString("en-GB", {
        timeZone: "Africa/Kigali",
        year: "numeric",
        month: "short",
        day: "numeric",
        hour: "2-digit",
        minute: "2-digit",
        second: "2-digit",
      });
    } catch {
      return isoString;
    }
  };

  const toggleRow = (id: string) => {
    setExpandedRowId((prev) => (prev === id ? null : id));
  };

  return (
    <div className="space-y-6 max-w-6xl">
      <ScopeHeader
        title="Audit Trail & Security Logs"
        description="Immutable record of administrative operations, setting updates, case overrides, and access events."
        scope={{ level: "national", name: "Rwanda" }}
      >
        <Button
          variant="outline"
          size="sm"
          onClick={() => loadLogs()}
          disabled={loading}
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
          <Button variant="outline" size="sm" onClick={() => loadLogs()}>
            Retry
          </Button>
        </div>
      )}

      {/* Filter Bar */}
      <div className="flex flex-wrap items-center gap-4">
        <div className="flex items-center gap-2">
          <label htmlFor="actionFilter" className="text-xs font-semibold text-muted-foreground uppercase">
            Action:
          </label>
          <select
            id="actionFilter"
            value={actionFilter}
            onChange={(e) => setActionFilter(e.target.value)}
            className="px-3 py-1.5 border rounded-md bg-background text-sm text-foreground focus:outline-hidden focus:ring-2 focus:ring-primary"
          >
            <option value="">All Actions</option>
            <option value="update_settings">update_settings</option>
            <option value="retry_sms">retry_sms</option>
            <option value="create_user">create_user</option>
            <option value="reset_pin">reset_pin</option>
            <option value="assign_mentor">assign_mentor</option>
            <option value="escalate_case">escalate_case</option>
            <option value="resolve_case">resolve_case</option>
          </select>
        </div>

        <div className="flex items-center gap-2">
          <label htmlFor="entityFilter" className="text-xs font-semibold text-muted-foreground uppercase">
            Entity:
          </label>
          <select
            id="entityFilter"
            value={entityTypeFilter}
            onChange={(e) => setEntityTypeFilter(e.target.value)}
            className="px-3 py-1.5 border rounded-md bg-background text-sm text-foreground focus:outline-hidden focus:ring-2 focus:ring-primary"
          >
            <option value="">All Entities</option>
            <option value="app_settings">app_settings</option>
            <option value="sms_outbox">sms_outbox</option>
            <option value="case">case</option>
            <option value="user">user</option>
            <option value="student">student</option>
          </select>
        </div>

        {(actionFilter || entityTypeFilter) && (
          <Button
            variant="ghost"
            size="sm"
            onClick={() => {
              setActionFilter("");
              setEntityTypeFilter("");
            }}
            className="text-xs h-8"
          >
            Clear Filters
          </Button>
        )}
      </div>

      <Card>
        <CardHeader className="py-4">
          <CardTitle className="text-base font-semibold flex items-center justify-between">
            <span>Audit Entries ({logs.length})</span>
            <span className="text-xs text-muted-foreground font-normal">
              Latest 100 logged events
            </span>
          </CardTitle>
        </CardHeader>
        <CardContent className="p-0">
          {loading ? (
            <div className="p-12 text-center text-sm text-muted-foreground animate-pulse">
              Querying audit logs...
            </div>
          ) : logs.length === 0 ? (
            <div className="p-12 text-center text-sm text-muted-foreground">
              No audit log entries found matching criteria.
            </div>
          ) : (
            <div className="overflow-x-auto">
              <table className="w-full text-left text-sm">
                <thead className="bg-muted/50 border-y text-xs uppercase text-muted-foreground font-semibold">
                  <tr>
                    <th className="px-4 py-3 w-8"></th>
                    <th className="px-4 py-3">Timestamp (Kigali)</th>
                    <th className="px-4 py-3">Actor Role</th>
                    <th className="px-4 py-3">Action</th>
                    <th className="px-4 py-3">Entity Type</th>
                    <th className="px-4 py-3">Entity ID</th>
                  </tr>
                </thead>
                <tbody className="divide-y">
                  {logs.map((log) => {
                    const isExpanded = expandedRowId === log.id;
                    const hasMeta =
                      log.meta &&
                      typeof log.meta === "object" &&
                      Object.keys(log.meta).length > 0;

                    return (
                      <React.Fragment key={log.id}>
                        <tr
                          onClick={() => hasMeta && toggleRow(log.id)}
                          className={`hover:bg-muted/20 ${
                            hasMeta ? "cursor-pointer" : ""
                          }`}
                        >
                          <td className="px-4 py-3 text-muted-foreground">
                            {hasMeta &&
                              (isExpanded ? (
                                <ChevronDown className="h-4 w-4" />
                              ) : (
                                <ChevronRight className="h-4 w-4" />
                              ))}
                          </td>
                          <td className="px-4 py-3 whitespace-nowrap text-xs text-muted-foreground font-mono">
                            {formatKigaliTime(log.created_at)}
                          </td>
                          <td className="px-4 py-3 whitespace-nowrap">
                            <Badge variant="outline" className="capitalize text-xs">
                              {log.actor_role.replace("_", " ")}
                            </Badge>
                          </td>
                          <td className="px-4 py-3 whitespace-nowrap font-mono text-xs font-semibold text-primary">
                            {log.action}
                          </td>
                          <td className="px-4 py-3 whitespace-nowrap font-mono text-xs text-muted-foreground">
                            {log.entity_type}
                          </td>
                          <td className="px-4 py-3 whitespace-nowrap font-mono text-xs text-muted-foreground max-w-xs truncate">
                            {log.entity_id || "—"}
                          </td>
                        </tr>
                        {isExpanded && hasMeta && (
                          <tr className="bg-muted/30">
                            <td colSpan={6} className="px-6 py-4">
                              <div className="text-xs font-semibold text-muted-foreground mb-1 uppercase tracking-wider">
                                Event Payload / Diff:
                              </div>
                              <pre className="p-3 bg-card border rounded-md font-mono text-xs text-foreground overflow-x-auto">
                                {JSON.stringify(log.meta, null, 2)}
                              </pre>
                            </td>
                          </tr>
                        )}
                      </React.Fragment>
                    );
                  })}
                </tbody>
              </table>
            </div>
          )}
        </CardContent>
      </Card>
    </div>
  );
}

import React from "react";
