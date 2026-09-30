"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { fetchCases } from "@/lib/api/client";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";

interface CaseItem {
  id: string;
  ref: string;
  student_id: string;
  student_name: string;
  student_gender?: string;
  class_name?: string;
  school_id: string;
  school_name: string;
  sector_name?: string;
  status: string;
  level: number;
  trigger: string;
  risk_score: number;
  mentor_id?: string;
  mentor_name?: string;
  opened_at: string;
  resolved_at?: string;
  sla_breached: boolean;
}

export default function CasesPage() {
  const [cases, setCases] = useState<CaseItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  // Filters
  const [search, setSearch] = useState("");
  const [statusFilter, setStatusFilter] = useState("all");
  const [levelFilter, setLevelFilter] = useState("all");

  const loadCases = async () => {
    setLoading(true);
    setError(null);
    try {
      const params: any = {};
      if (search.trim()) params.q = search.trim();
      if (statusFilter !== "all") params.status = statusFilter;
      if (levelFilter !== "all") params.level = Number(levelFilter);

      const data = await fetchCases(params);
      setCases(data);
    } catch (err: any) {
      setError(err.message || "Failed to load cases");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadCases();
  }, [statusFilter, levelFilter]);

  const handleSearchSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    loadCases();
  };

  const getStatusBadge = (status: string) => {
    switch (status) {
      case "open":
        return <Badge variant="secondary">Open</Badge>;
      case "mentor_assigned":
        return <Badge className="bg-blue-600 hover:bg-blue-700">Mentor Assigned</Badge>;
      case "visited":
        return <Badge className="bg-purple-600 hover:bg-purple-700">Visited</Badge>;
      case "escalated_sector":
        return <Badge variant="destructive">Level 3 (SEO)</Badge>;
      case "escalated_district":
        return <Badge variant="destructive">Level 4 (District)</Badge>;
      case "resolved_returned":
        return <Badge className="bg-emerald-600 hover:bg-emerald-700">Returned</Badge>;
      case "closed_moved":
      case "closed_other":
        return <Badge variant="outline">Closed</Badge>;
      default:
        return <Badge variant="outline">{status}</Badge>;
    }
  };

  const getRiskScoreBadge = (score: number) => {
    if (score >= 70) {
      return <span className="inline-flex items-center px-2 py-0.5 rounded text-xs font-bold bg-red-100 text-red-800 dark:bg-red-950 dark:text-red-300">{score}/100</span>;
    }
    if (score >= 40) {
      return <span className="inline-flex items-center px-2 py-0.5 rounded text-xs font-bold bg-amber-100 text-amber-800 dark:bg-amber-950 dark:text-amber-300">{score}/100</span>;
    }
    return <span className="inline-flex items-center px-2 py-0.5 rounded text-xs font-bold bg-emerald-100 text-emerald-800 dark:bg-emerald-950 dark:text-emerald-300">{score}/100</span>;
  };

  return (
    <div className="space-y-6">
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
        <div>
          <h1 className="text-2xl font-bold tracking-tight">Cases & Intervention</h1>
          <p className="text-sm text-muted-foreground">
            Dropout early-warning alerts, mentor follow-up visits, and escalations.
          </p>
        </div>
      </div>

      {/* Filter and Search Bar */}
      <div className="flex flex-col md:flex-row gap-3 items-stretch md:items-center justify-between bg-card p-4 rounded-lg border">
        <form onSubmit={handleSearchSubmit} className="flex gap-2 flex-1 max-w-md">
          <Input
            placeholder="Search by student name or ref code..."
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            className="flex-1"
          />
          <Button type="submit" variant="secondary">
            Search
          </Button>
        </form>

        <div className="flex flex-wrap items-center gap-3">
          <div className="flex items-center gap-2">
            <span className="text-xs text-muted-foreground font-medium">Status:</span>
            <select
              value={statusFilter}
              onChange={(e) => setStatusFilter(e.target.value)}
              className="text-xs border rounded px-2 py-1.5 bg-background"
            >
              <option value="all">All Statuses</option>
              <option value="open">Open</option>
              <option value="mentor_assigned">Mentor Assigned</option>
              <option value="visited">Visited</option>
              <option value="escalated_sector">Level 3 (SEO)</option>
              <option value="resolved_returned">Returned</option>
            </select>
          </div>

          <div className="flex items-center gap-2">
            <span className="text-xs text-muted-foreground font-medium">Level:</span>
            <select
              value={levelFilter}
              onChange={(e) => setLevelFilter(e.target.value)}
              className="text-xs border rounded px-2 py-1.5 bg-background"
            >
              <option value="all">All Levels</option>
              <option value="2">Level 2 (Mentor)</option>
              <option value="3">Level 3 (Sector Officer)</option>
            </select>
          </div>

          <Button variant="outline" size="sm" onClick={loadCases}>
            Refresh
          </Button>
        </div>
      </div>

      {error && (
        <div className="p-4 rounded-lg bg-destructive/10 border border-destructive/20 text-destructive text-sm">
          {error}
        </div>
      )}

      {/* Cases Table */}
      <div className="rounded-md border bg-card overflow-hidden">
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead>Ref</TableHead>
              <TableHead>Student</TableHead>
              <TableHead>Class / School</TableHead>
              <TableHead>Risk Score</TableHead>
              <TableHead>Level</TableHead>
              <TableHead>Status</TableHead>
              <TableHead>Assigned Mentor</TableHead>
              <TableHead>Opened</TableHead>
              <TableHead className="text-right">Action</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {loading ? (
              <TableRow>
                <TableCell colSpan={9} className="text-center py-8 text-muted-foreground animate-pulse">
                  Loading cases...
                </TableCell>
              </TableRow>
            ) : cases.length === 0 ? (
              <TableRow>
                <TableCell colSpan={9} className="text-center py-8 text-muted-foreground">
                  No cases found matching your filters.
                </TableCell>
              </TableRow>
            ) : (
              cases.map((c) => (
                <TableRow key={c.id}>
                  <TableCell className="font-mono text-xs font-semibold">
                    <Link
                      href={`/dashboard/cases/${c.id}`}
                      className="text-primary hover:underline"
                    >
                      {c.ref}
                    </Link>
                  </TableCell>
                  <TableCell>
                    <div className="font-medium text-sm">{c.student_name}</div>
                    {c.student_gender && (
                      <span className="text-xs text-muted-foreground">{c.student_gender}</span>
                    )}
                  </TableCell>
                  <TableCell>
                    <div className="text-xs font-medium">{c.school_name}</div>
                    <div className="text-xs text-muted-foreground">{c.class_name || "General"}</div>
                  </TableCell>
                  <TableCell>{getRiskScoreBadge(c.risk_score)}</TableCell>
                  <TableCell>
                    <span className="text-xs font-semibold">Level {c.level}</span>
                  </TableCell>
                  <TableCell>
                    <div className="flex flex-col gap-1 items-start">
                      {getStatusBadge(c.status)}
                      {c.sla_breached && (
                        <span className="inline-flex items-center px-1.5 py-0.5 rounded text-[10px] font-bold bg-amber-500/20 text-amber-600">
                          SLA BREACHED
                        </span>
                      )}
                    </div>
                  </TableCell>
                  <TableCell className="text-xs">
                    {c.mentor_name ? (
                      <span className="font-medium">{c.mentor_name}</span>
                    ) : (
                      <span className="text-muted-foreground italic">Unassigned</span>
                    )}
                  </TableCell>
                  <TableCell className="text-xs text-muted-foreground">
                    {new Date(c.opened_at).toLocaleDateString()}
                  </TableCell>
                  <TableCell className="text-right">
                    <Link href={`/dashboard/cases/${c.id}`}>
                      <Button variant="ghost" size="sm">
                        View Details &rarr;
                      </Button>
                    </Link>
                  </TableCell>
                </TableRow>
              ))
            )}
          </TableBody>
        </Table>
      </div>
    </div>
  );
}
