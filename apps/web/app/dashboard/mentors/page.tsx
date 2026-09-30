"use client";

import { useEffect, useState } from "react";
import { fetchMentors, fetchSectors } from "@/lib/api/client";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";

interface MentorItem {
  id: string;
  name: string;
  email?: string;
  phone_e164: string;
  sector_id?: string;
  sector_name?: string;
  active_cases: number;
  visits_30d: number;
  verified_rate: number;
  is_active: boolean;
}

export default function MentorsPage() {
  const [mentors, setMentors] = useState<MentorItem[]>([]);
  const [sectors, setSectors] = useState<any[]>([]);
  const [selectedSector, setSelectedSector] = useState("all");
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const loadData = async () => {
    setLoading(true);
    setError(null);
    try {
      const [mentorList, sectorList] = await Promise.all([
        fetchMentors(selectedSector !== "all" ? selectedSector : undefined),
        fetchSectors().catch(() => []),
      ]);
      setMentors(mentorList);
      setSectors(sectorList);
    } catch (err: any) {
      setError(err.message || "Failed to load mentors");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadData();
  }, [selectedSector]);

  // Aggregate stats
  const totalActiveCases = mentors.reduce((acc, m) => acc + m.active_cases, 0);
  const totalVisits = mentors.reduce((acc, m) => acc + m.visits_30d, 0);
  const avgVerificationRate =
    mentors.length > 0
      ? Math.round(
          mentors.reduce((acc, m) => acc + m.verified_rate, 0) / mentors.length
        )
      : 0;

  return (
    <div className="space-y-6">
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
        <div>
          <h1 className="text-2xl font-bold tracking-tight">Community Mentors</h1>
          <p className="text-sm text-muted-foreground">
            Manage community mentors, track home visits, case workloads, and verification rates.
          </p>
        </div>
      </div>

      {/* Aggregate Overview Cards */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
        <Card>
          <CardHeader className="pb-2">
            <CardTitle className="text-xs font-medium text-muted-foreground">
              Total Mentors
            </CardTitle>
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold">{mentors.length}</div>
          </CardContent>
        </Card>

        <Card>
          <CardHeader className="pb-2">
            <CardTitle className="text-xs font-medium text-muted-foreground">
              Active Cases Assigned
            </CardTitle>
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold text-primary">{totalActiveCases}</div>
          </CardContent>
        </Card>

        <Card>
          <CardHeader className="pb-2">
            <CardTitle className="text-xs font-medium text-muted-foreground">
              Visits in Last 30 Days
            </CardTitle>
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold">{totalVisits}</div>
          </CardContent>
        </Card>

        <Card>
          <CardHeader className="pb-2">
            <CardTitle className="text-xs font-medium text-muted-foreground">
              Avg. Verification Rate
            </CardTitle>
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold text-emerald-600">
              {avgVerificationRate}%
            </div>
          </CardContent>
        </Card>
      </div>

      {/* Filter Bar */}
      <div className="flex items-center justify-between bg-card p-4 rounded-lg border">
        <div className="flex items-center gap-3">
          <span className="text-xs font-medium text-muted-foreground">Sector:</span>
          <select
            value={selectedSector}
            onChange={(e) => setSelectedSector(e.target.value)}
            className="text-xs border rounded px-2 py-1.5 bg-background"
          >
            <option value="all">All Sectors</option>
            {sectors.map((s) => (
              <option key={s.id} value={s.id}>
                {s.name}
              </option>
            ))}
          </select>
        </div>
        <Button variant="outline" size="sm" onClick={loadData}>
          Refresh
        </Button>
      </div>

      {error && (
        <div className="p-4 rounded-lg bg-destructive/10 border border-destructive/20 text-destructive text-sm">
          {error}
        </div>
      )}

      {/* Mentors Table */}
      <div className="rounded-md border bg-card overflow-hidden">
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead>Mentor Name</TableHead>
              <TableHead>Sector</TableHead>
              <TableHead>Active Cases</TableHead>
              <TableHead>Visits (30d)</TableHead>
              <TableHead>OTP Verification Rate</TableHead>
              <TableHead>Status</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {loading ? (
              <TableRow>
                <TableCell colSpan={6} className="text-center py-8 text-muted-foreground animate-pulse">
                  Loading mentors...
                </TableCell>
              </TableRow>
            ) : mentors.length === 0 ? (
              <TableRow>
                <TableCell colSpan={6} className="text-center py-8 text-muted-foreground">
                  No mentors registered in this sector.
                </TableCell>
              </TableRow>
            ) : (
              mentors.map((m) => (
                <TableRow key={m.id}>
                  <TableCell>
                    <div className="font-semibold text-sm">{m.name}</div>
                    <div className="text-xs text-muted-foreground">{m.email || m.phone_e164}</div>
                  </TableCell>
                  <TableCell className="text-xs">{m.sector_name || "Unassigned"}</TableCell>
                  <TableCell>
                    <span className="text-xs font-bold px-2 py-0.5 rounded bg-muted">
                      {m.active_cases} / 15
                    </span>
                  </TableCell>
                  <TableCell className="text-xs font-semibold">{m.visits_30d}</TableCell>
                  <TableCell>
                    <div className="flex items-center gap-2">
                      <span
                        className={`text-xs font-bold ${
                          m.verified_rate >= 70
                            ? "text-emerald-600"
                            : m.verified_rate >= 40
                            ? "text-amber-600"
                            : "text-muted-foreground"
                        }`}
                      >
                        {m.verified_rate}%
                      </span>
                    </div>
                  </TableCell>
                  <TableCell>
                    {m.is_active ? (
                      <Badge className="bg-emerald-600">Active</Badge>
                    ) : (
                      <Badge variant="outline">Inactive</Badge>
                    )}
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
