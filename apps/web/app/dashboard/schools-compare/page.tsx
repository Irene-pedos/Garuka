"use client";

import { useEffect, useState } from "react";
import { useAuth } from "@/lib/auth-context";
import { fetchSchoolsCompare } from "@/lib/api/client";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { ScopeHeader } from "@/components/scope-header";

interface SchoolCompareItem {
  school_id: string;
  school_name: string;
  sector_name: string;
  students_active: number;
  absent_today: number;
  absence_rate_pct: number;
  open_cases: number;
  returned_30d: number;
  attendance_compliance_pct: number;
}

export default function SchoolsComparePage() {
  const { user } = useAuth();
  const [schools, setSchools] = useState<SchoolCompareItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [search, setSearch] = useState("");
  const [sortField, setSortField] = useState<keyof SchoolCompareItem>("attendance_compliance_pct");
  const [sortAsc, setSortAsc] = useState(false);

  const loadData = () => {
    setLoading(true);
    setError(null);
    fetchSchoolsCompare()
      .then((data) => setSchools(data as SchoolCompareItem[]))
      .catch((err) => {
        console.error(err);
        setError("Failed to load school comparison data.");
      })
      .finally(() => setLoading(false));
  };

  useEffect(() => {
    loadData();
  }, []);

  const handleSort = (field: keyof SchoolCompareItem) => {
    if (sortField === field) {
      setSortAsc(!sortAsc);
    } else {
      setSortField(field);
      setSortAsc(false);
    }
  };

  const filtered = schools.filter((s) => {
    if (!search.trim()) return true;
    const q = search.toLowerCase();
    return s.school_name.toLowerCase().includes(q) || s.sector_name.toLowerCase().includes(q);
  });

  const sorted = [...filtered].sort((a, b) => {
    const valA = a[sortField];
    const valB = b[sortField];
    if (typeof valA === "number" && typeof valB === "number") {
      return sortAsc ? valA - valB : valB - valA;
    }
    return sortAsc
      ? String(valA).localeCompare(String(valB))
      : String(valB).localeCompare(String(valA));
  });

  const totalStudents = schools.reduce((acc, s) => acc + s.students_active, 0);
  const totalOpenCases = schools.reduce((acc, s) => acc + s.open_cases, 0);
  const avgCompliance =
    schools.length > 0
      ? Math.round(
          (schools.reduce((acc, s) => acc + s.attendance_compliance_pct, 0) / schools.length) * 10
        ) / 10
      : 0;

  return (
    <div className="space-y-6 max-w-6xl">
      <ScopeHeader
        title="Schools Comparison & Compliance"
        description="Attendance compliance, daily absence rates, and open dropout cases across institutions."
        scope={
          user
            ? {
                level:
                  user.role === "admin"
                    ? "national"
                    : user.role === "district_director"
                    ? "district"
                    : user.role === "sector_officer"
                    ? "sector"
                    : "school",
                name: user.full_name,
              }
            : undefined
        }
      >
        <Button variant="outline" size="sm" onClick={loadData} disabled={loading}>
          Refresh
        </Button>
      </ScopeHeader>

      {error && (
        <div className="p-3 text-sm bg-destructive/15 text-destructive rounded-md">
          {error}
        </div>
      )}

      {/* Aggregate KPI Cards */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
        <Card>
          <CardHeader className="pb-2">
            <CardTitle className="text-xs font-semibold uppercase text-muted-foreground">
              Total Schools
            </CardTitle>
          </CardHeader>
          <CardContent>
            <div className="text-3xl font-bold text-foreground">{schools.length}</div>
            <p className="text-xs text-muted-foreground mt-1">Within current administrative scope</p>
          </CardContent>
        </Card>

        <Card>
          <CardHeader className="pb-2">
            <CardTitle className="text-xs font-semibold uppercase text-muted-foreground">
              Enrolled Students
            </CardTitle>
          </CardHeader>
          <CardContent>
            <div className="text-3xl font-bold text-foreground">
              {totalStudents.toLocaleString()}
            </div>
            <p className="text-xs text-muted-foreground mt-1">Across all schools</p>
          </CardContent>
        </Card>

        <Card>
          <CardHeader className="pb-2">
            <CardTitle className="text-xs font-semibold uppercase text-muted-foreground">
              Active Cases
            </CardTitle>
          </CardHeader>
          <CardContent>
            <div className="text-3xl font-bold text-foreground">{totalOpenCases}</div>
            <p className="text-xs text-muted-foreground mt-1">Dropout risk cases requiring action</p>
          </CardContent>
        </Card>

        <Card>
          <CardHeader className="pb-2">
            <CardTitle className="text-xs font-semibold uppercase text-muted-foreground">
              Average Compliance
            </CardTitle>
          </CardHeader>
          <CardContent>
            <div className="text-3xl font-bold text-emerald-600">{avgCompliance}%</div>
            <p className="text-xs text-muted-foreground mt-1">Recent school days submission rate</p>
          </CardContent>
        </Card>
      </div>

      <div className="flex items-center gap-3">
        <Input
          placeholder="Filter by school or sector..."
          value={search}
          onChange={(e) => setSearch(e.target.value)}
          className="max-w-xs"
        />
      </div>

      {/* Schools Comparison Table */}
      <Card>
        <CardHeader className="py-4">
          <CardTitle className="text-base font-medium">
            Schools ({sorted.length})
          </CardTitle>
        </CardHeader>
        <CardContent className="p-0">
          {loading ? (
            <div className="p-8 text-center text-sm text-muted-foreground animate-pulse">
              Loading school comparison data...
            </div>
          ) : sorted.length === 0 ? (
            <div className="p-8 text-center text-sm text-muted-foreground">
              No schools found.
            </div>
          ) : (
            <div className="overflow-x-auto">
              <table className="w-full text-left text-sm">
                <thead className="bg-muted/50 border-b text-xs uppercase text-muted-foreground">
                  <tr>
                    <th
                      className="px-4 py-3 font-medium cursor-pointer hover:text-foreground"
                      onClick={() => handleSort("school_name")}
                    >
                      School Name {sortField === "school_name" && (sortAsc ? "▲" : "▼")}
                    </th>
                    <th
                      className="px-4 py-3 font-medium cursor-pointer hover:text-foreground"
                      onClick={() => handleSort("sector_name")}
                    >
                      Sector {sortField === "sector_name" && (sortAsc ? "▲" : "▼")}
                    </th>
                    <th
                      className="px-4 py-3 font-medium cursor-pointer hover:text-foreground text-right"
                      onClick={() => handleSort("students_active")}
                    >
                      Students {sortField === "students_active" && (sortAsc ? "▲" : "▼")}
                    </th>
                    <th
                      className="px-4 py-3 font-medium cursor-pointer hover:text-foreground text-right"
                      onClick={() => handleSort("absent_today")}
                    >
                      Absent Today {sortField === "absent_today" && (sortAsc ? "▲" : "▼")}
                    </th>
                    <th
                      className="px-4 py-3 font-medium cursor-pointer hover:text-foreground text-right"
                      onClick={() => handleSort("absence_rate_pct")}
                    >
                      Absence Rate {sortField === "absence_rate_pct" && (sortAsc ? "▲" : "▼")}
                    </th>
                    <th
                      className="px-4 py-3 font-medium cursor-pointer hover:text-foreground text-right"
                      onClick={() => handleSort("open_cases")}
                    >
                      Open Cases {sortField === "open_cases" && (sortAsc ? "▲" : "▼")}
                    </th>
                    <th
                      className="px-4 py-3 font-medium cursor-pointer hover:text-foreground text-right"
                      onClick={() => handleSort("returned_30d")}
                    >
                      Returned (30d) {sortField === "returned_30d" && (sortAsc ? "▲" : "▼")}
                    </th>
                    <th
                      className="px-4 py-3 font-medium cursor-pointer hover:text-foreground text-right"
                      onClick={() => handleSort("attendance_compliance_pct")}
                    >
                      Compliance {sortField === "attendance_compliance_pct" && (sortAsc ? "▲" : "▼")}
                    </th>
                  </tr>
                </thead>
                <tbody className="divide-y">
                  {sorted.map((s) => (
                    <tr key={s.school_id} className="hover:bg-muted/20">
                      <td className="px-4 py-3 font-medium text-foreground">
                        {s.school_name}
                      </td>
                      <td className="px-4 py-3 text-muted-foreground">{s.sector_name}</td>
                      <td className="px-4 py-3 text-right">{s.students_active.toLocaleString()}</td>
                      <td className="px-4 py-3 text-right">{s.absent_today}</td>
                      <td className="px-4 py-3 text-right">
                        <span
                          className={`font-medium ${
                            s.absence_rate_pct > 10
                              ? "text-destructive"
                              : s.absence_rate_pct > 5
                              ? "text-amber-600"
                              : "text-foreground"
                          }`}
                        >
                          {s.absence_rate_pct}%
                        </span>
                      </td>
                      <td className="px-4 py-3 text-right">
                        {s.open_cases > 0 ? (
                          <Badge variant={s.open_cases >= 5 ? "destructive" : "secondary"}>
                            {s.open_cases}
                          </Badge>
                        ) : (
                          <span className="text-muted-foreground">0</span>
                        )}
                      </td>
                      <td className="px-4 py-3 text-right text-emerald-600 font-medium">
                        {s.returned_30d}
                      </td>
                      <td className="px-4 py-3 text-right">
                        <span
                          className={`font-semibold ${
                            s.attendance_compliance_pct >= 90
                              ? "text-emerald-600"
                              : s.attendance_compliance_pct >= 75
                              ? "text-amber-600"
                              : "text-destructive"
                          }`}
                        >
                          {s.attendance_compliance_pct}%
                        </span>
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
