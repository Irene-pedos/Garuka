"use client"

import * as React from "react"
import Link from "next/link"
import { useAuth } from "@/lib/auth-context"
import {
  fetchAnalyticsOverview,
  fetchCases,
  type AnalyticsOverview,
} from "@/lib/api/client"
import { SectionCards } from "@/components/section-cards"
import { ChartAreaInteractive } from "@/components/chart-area-interactive"
import { ScopeHeader } from "@/components/scope-header"
import { DataAlert } from "@/components/ui/data-state"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs"
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card"
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table"
import {
  AlertTriangle,
  ArrowRight,
  CalendarCheck2,
  CheckCircle2,
  Clock,
  ExternalLink,
  FolderOpen,
  HelpCircle,
  ListTodo,
  RefreshCw,
  Search,
  Sparkles,
  Users,
} from "lucide-react"

export default function DashboardOverviewPage() {
  const { user } = useAuth()
  const [overview, setOverview] = React.useState<AnalyticsOverview | null>(null)
  const [cases, setCases] = React.useState<any[]>([])
  const [loading, setLoading] = React.useState(true)
  const [error, setError] = React.useState<string | null>(null)

  // Minimalist Tab Navigation
  const [activeTab, setActiveTab] = React.useState("overview")
  const [caseSearch, setCaseSearch] = React.useState("")
  const [levelFilter, setLevelFilter] = React.useState<number | null>(null)

  const loadData = React.useCallback(async (signal?: AbortSignal) => {
    setLoading(true)
    setError(null)
    try {
      const [ovData, casesData] = await Promise.all([
        fetchAnalyticsOverview(signal),
        fetchCases({ status: "open" as any }, signal).catch(() => []),
      ])
      setOverview(ovData)
      setCases(casesData)
    } catch (err: any) {
      if (err.name !== "AbortError") {
        setError(err.message || "Failed to load dashboard overview data")
      }
    } finally {
      setLoading(false)
    }
  }, [])

  React.useEffect(() => {
    const controller = new AbortController()
    loadData(controller.signal)
    return () => controller.abort()
  }, [loadData])

  if (!user) return null

  const overdueCount = overview?.overdue_cases?.length ?? 0
  const missingCount = overview?.classes_missing_today?.length ?? 0
  const urgentCount = overdueCount + missingCount

  const filteredCases = cases.filter((c) => {
    const matchesSearch =
      !caseSearch ||
      c.student_name?.toLowerCase().includes(caseSearch.toLowerCase()) ||
      c.ref?.toLowerCase().includes(caseSearch.toLowerCase()) ||
      c.school_name?.toLowerCase().includes(caseSearch.toLowerCase())
    const matchesLevel = levelFilter === null || c.level === levelFilter
    return matchesSearch && matchesLevel
  })

  const getStatusBadge = (status: string) => {
    switch (status) {
      case "open":
        return <Badge variant="secondary" className="text-xs">Open</Badge>
      case "mentor_assigned":
        return <Badge variant="default" className="text-xs">Mentor Assigned</Badge>
      case "escalated_sector":
        return <Badge variant="destructive" className="text-xs">Sector Escalated</Badge>
      case "resolved_returned":
        return <Badge variant="secondary" className="bg-emerald-100 text-emerald-800 dark:bg-emerald-950 dark:text-emerald-300 text-xs">Returned</Badge>
      default:
        return <Badge variant="outline" className="text-xs">{status}</Badge>
    }
  }

  const getRiskScoreBadge = (score: number) => {
    if (score >= 70) {
      return <span className="inline-flex items-center px-2 py-0.5 rounded text-xs font-bold bg-red-100 text-red-800 dark:bg-red-950 dark:text-red-300">{score}/100</span>
    }
    if (score >= 40) {
      return <span className="inline-flex items-center px-2 py-0.5 rounded text-xs font-bold bg-amber-100 text-amber-800 dark:bg-amber-950 dark:text-amber-300">{score}/100</span>
    }
    return <span className="inline-flex items-center px-2 py-0.5 rounded text-xs font-bold bg-emerald-100 text-emerald-800 dark:bg-emerald-950 dark:text-emerald-300">{score}/100</span>
  }

  return (
    <div className="flex flex-1 flex-col gap-6">
      {/* 1. Scope, Date & Refresh Header */}
      <ScopeHeader
        title="Dashboard"
        description={`Logged in as ${user.full_name}. Early-warning attendance monitoring and dropout intervention.`}
        scope={overview?.scope}
        dateInfo={overview ? `School Date: ${overview.kigali_today}` : undefined}
      >
        {overview?.active_term && (
          <Badge variant="outline" className="px-2.5 py-1 text-xs font-semibold">
            {overview.active_term.name}
          </Badge>
        )}
        <Button
          variant="outline"
          size="sm"
          onClick={() => loadData()}
          disabled={loading}
          className="h-8 gap-1.5"
        >
          <RefreshCw className={`h-3.5 w-3.5 ${loading ? "animate-spin" : ""}`} />
          <span>Refresh</span>
        </Button>
      </ScopeHeader>

      {/* 2. Error Alert with Retry */}
      <DataAlert error={error} onRetry={() => loadData()} />

      {/* 3. Section KPI Cards (Clear numbers, no guesswork) */}
      <SectionCards kpis={overview?.kpis} />

      {/* 4. Priority Action Strip (Tells the user EXACTLY what needs attention) */}
      <div className="px-4 lg:px-6">
        {urgentCount > 0 ? (
          <div className="flex flex-col sm:flex-row items-start sm:items-center justify-between gap-3 p-4 rounded-xl border border-amber-500/30 bg-amber-500/5 text-foreground transition-all">
            <div className="flex items-center gap-3">
              <div className="flex size-9 shrink-0 items-center justify-center rounded-lg bg-amber-500/15 text-amber-600 dark:text-amber-400">
                <AlertTriangle className="size-5" />
              </div>
              <div>
                <div className="font-semibold text-sm">
                  {urgentCount} Priority Item{urgentCount > 1 ? "s" : ""} Require Attention
                </div>
                <div className="text-xs text-muted-foreground">
                  {overdueCount > 0 && `${overdueCount} overdue home visit${overdueCount > 1 ? "s" : ""}`}
                  {overdueCount > 0 && missingCount > 0 && " • "}
                  {missingCount > 0 && `${missingCount} class${missingCount > 1 ? "es" : ""} missing roll-call today`}
                </div>
              </div>
            </div>
            <div className="flex items-center gap-2">
              <Button
                size="sm"
                variant="default"
                className="h-8 text-xs font-medium gap-1.5"
                onClick={() => setActiveTab("queue")}
              >
                <span>Open Action Queue</span>
                <ArrowRight className="size-3.5" />
              </Button>
            </div>
          </div>
        ) : (
          <div className="flex items-center justify-between p-3 px-4 rounded-xl border border-emerald-500/20 bg-emerald-500/5 text-foreground text-xs">
            <div className="flex items-center gap-2.5">
              <CheckCircle2 className="size-4 text-emerald-600 dark:text-emerald-400 shrink-0" />
              <span className="font-medium text-emerald-800 dark:text-emerald-300">
                All systems healthy: 100% attendance submissions recorded & zero overdue visits.
              </span>
            </div>
            <Badge variant="outline" className="text-[11px] font-medium border-emerald-500/30 text-emerald-700 dark:text-emerald-300">
              Up to date
            </Badge>
          </div>
        )}
      </div>

      {/* 5. Minimalist Tabbed Content (Zero Clutter) */}
      <div className="px-4 lg:px-6">
        <Tabs value={activeTab} onValueChange={(val) => setActiveTab(val as string)} className="gap-4">
          <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 border-b pb-3">
            <TabsList className="bg-muted/70 p-1">
              <TabsTrigger value="overview" className="px-3.5 py-1.5 text-xs font-medium">
                Overview & Trends
              </TabsTrigger>
              <TabsTrigger value="queue" className="px-3.5 py-1.5 text-xs font-medium gap-1.5">
                <span>Action Queue</span>
                {urgentCount > 0 && (
                  <Badge variant="destructive" className="h-4 px-1.5 text-[10px] font-semibold">
                    {urgentCount}
                  </Badge>
                )}
              </TabsTrigger>
              <TabsTrigger value="cases" className="px-3.5 py-1.5 text-xs font-medium gap-1.5">
                <span>Active Cases</span>
                <Badge variant="secondary" className="h-4 px-1.5 text-[10px]">
                  {cases.length}
                </Badge>
              </TabsTrigger>
            </TabsList>

            <div className="text-xs text-muted-foreground hidden sm:block">
              {activeTab === "overview" && "Daily school roll-calls and attendance volume"}
              {activeTab === "queue" && "SLA breaches & pending class submissions"}
              {activeTab === "cases" && `${filteredCases.length} student intervention cases`}
            </div>
          </div>

          {/* TAB 1: OVERVIEW & TRENDS */}
          <TabsContent value="overview" className="space-y-6 pt-2">
            {/* Interactive Real Data Attendance Trend Chart */}
            <ChartAreaInteractive data={overview?.attendance_trend} isLoading={loading} />

            {/* Quick 2-Column Summary Cards */}
            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              {/* Quick High-Risk Student Snapshot */}
              <Card>
                <CardHeader className="flex flex-row items-center justify-between pb-3">
                  <div>
                    <CardTitle className="text-sm font-semibold">High-Risk Students</CardTitle>
                    <CardDescription className="text-xs">
                      Priority cases with elevated absence or dropout risk
                    </CardDescription>
                  </div>
                  <Button
                    variant="ghost"
                    size="sm"
                    className="h-7 text-xs text-primary gap-1"
                    onClick={() => setActiveTab("cases")}
                  >
                    <span>View all</span>
                    <ArrowRight className="size-3" />
                  </Button>
                </CardHeader>
                <CardContent className="p-0">
                  {loading ? (
                    <div className="p-6 text-center text-xs text-muted-foreground animate-pulse">
                      Loading cases...
                    </div>
                  ) : cases.length === 0 ? (
                    <div className="p-6 text-center text-xs text-muted-foreground">
                      No active cases flagged. Attendance is stable.
                    </div>
                  ) : (
                    <ul className="divide-y text-xs">
                      {cases.slice(0, 3).map((c) => (
                        <li key={c.id} className="p-3 hover:bg-muted/20 flex items-center justify-between gap-2">
                          <div>
                            <div className="font-medium text-foreground text-xs">{c.student_name}</div>
                            <div className="text-[11px] text-muted-foreground">
                              {c.ref} • {c.school_name}
                            </div>
                          </div>
                          <div className="flex items-center gap-2">
                            {getRiskScoreBadge(c.risk_score)}
                            <Link href={`/dashboard/cases/${c.id}`}>
                              <Button size="sm" variant="ghost" className="h-6 text-[11px] px-2 text-primary">
                                Review
                              </Button>
                            </Link>
                          </div>
                        </li>
                      ))}
                    </ul>
                  )}
                </CardContent>
              </Card>

              {/* Quick Operational Status */}
              <Card>
                <CardHeader className="flex flex-row items-center justify-between pb-3">
                  <div>
                    <CardTitle className="text-sm font-semibold">Today's Quick Checklist</CardTitle>
                    <CardDescription className="text-xs">
                      Key operational milestones for Rwanda basic education
                    </CardDescription>
                  </div>
                  <Button
                    variant="ghost"
                    size="sm"
                    className="h-7 text-xs text-primary gap-1"
                    onClick={() => setActiveTab("queue")}
                  >
                    <span>Action queue</span>
                    <ArrowRight className="size-3" />
                  </Button>
                </CardHeader>
                <CardContent className="space-y-3 pt-1">
                  <div className="flex items-center justify-between p-2.5 rounded-lg border bg-muted/20 text-xs">
                    <div className="flex items-center gap-2">
                      <CalendarCheck2 className="size-4 text-primary" />
                      <span className="font-medium">Roll-Call Rate</span>
                    </div>
                    <Badge variant={missingCount > 0 ? "outline" : "secondary"} className="text-xs">
                      {overview?.kpis?.attendance_compliance_pct ?? 0}% ({missingCount} missing)
                    </Badge>
                  </div>

                  <div className="flex items-center justify-between p-2.5 rounded-lg border bg-muted/20 text-xs">
                    <div className="flex items-center gap-2">
                      <Clock className="size-4 text-amber-500" />
                      <span className="font-medium">Home Visits (5-Day SLA)</span>
                    </div>
                    <Badge variant={overdueCount > 0 ? "destructive" : "outline"} className="text-xs">
                      {overdueCount > 0 ? `${overdueCount} Overdue` : "On schedule"}
                    </Badge>
                  </div>

                  <div className="flex items-center justify-between p-2.5 rounded-lg border bg-muted/20 text-xs">
                    <div className="flex items-center gap-2">
                      <HelpCircle className="size-4 text-muted-foreground" />
                      <span className="font-medium">Community Help Requests</span>
                    </div>
                    <Link href="/dashboard/help-requests">
                      <Badge variant="outline" className="text-xs hover:border-primary cursor-pointer">
                        {overview?.kpis?.pending_help_requests_count ?? 0} Pending →
                      </Badge>
                    </Link>
                  </div>
                </CardContent>
              </Card>
            </div>
          </TabsContent>

          {/* TAB 2: ACTION QUEUE (Zero Guesswork) */}
          <TabsContent value="queue" className="space-y-4 pt-2">
            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              {/* Overdue Mentor Visits */}
              <Card>
                <CardHeader className="pb-3">
                  <div className="flex items-center justify-between">
                    <CardTitle className="text-sm font-semibold">Overdue Home Visits</CardTitle>
                    {overdueCount > 0 && (
                      <Badge variant="destructive" className="text-xs">
                        {overdueCount} Overdue
                      </Badge>
                    )}
                  </div>
                  <CardDescription className="text-xs">
                    Student cases pending mentor OTP home-visit verification past 5 days
                  </CardDescription>
                </CardHeader>
                <CardContent className="p-0">
                  {loading ? (
                    <div className="p-6 text-center text-xs text-muted-foreground animate-pulse">
                      Checking overdue visits...
                    </div>
                  ) : overdueCount === 0 ? (
                    <div className="p-6 text-center text-xs text-muted-foreground flex flex-col items-center gap-1.5">
                      <CheckCircle2 className="size-6 text-emerald-500 mb-1" />
                      <p className="font-medium text-foreground">All visits up to date</p>
                      <p className="text-xs">No cases have breached the 5-day home visit SLA.</p>
                    </div>
                  ) : (
                    <ul className="divide-y text-xs">
                      {overview?.overdue_cases.map((c) => (
                        <li key={c.id} className="p-3.5 hover:bg-muted/20 flex items-center justify-between gap-2">
                          <div>
                            <div className="font-medium text-foreground text-xs">{c.student_name}</div>
                            <div className="text-[11px] text-muted-foreground">
                              {c.ref} • {c.school_name} • Level {c.level}
                            </div>
                          </div>
                          <div className="flex items-center gap-2">
                            <span className="text-[11px] font-semibold text-destructive whitespace-nowrap">
                              {c.days_open}d open
                            </span>
                            <Link href={`/dashboard/cases/${c.id}`}>
                              <Button size="sm" variant="default" className="h-7 text-xs px-2.5">
                                Review Case
                              </Button>
                            </Link>
                          </div>
                        </li>
                      ))}
                    </ul>
                  )}
                </CardContent>
              </Card>

              {/* Missing Today's Roll Call */}
              <Card>
                <CardHeader className="pb-3">
                  <div className="flex items-center justify-between">
                    <CardTitle className="text-sm font-semibold">Missing Roll-Call Today</CardTitle>
                    {missingCount > 0 && (
                      <Badge variant="outline" className="border-amber-500/50 text-amber-600 dark:text-amber-400 text-xs">
                        {missingCount} Missing
                      </Badge>
                    )}
                  </div>
                  <CardDescription className="text-xs">
                    Classes that have not recorded attendance for today's school date
                  </CardDescription>
                </CardHeader>
                <CardContent className="p-0">
                  {loading ? (
                    <div className="p-6 text-center text-xs text-muted-foreground animate-pulse">
                      Checking class submissions...
                    </div>
                  ) : missingCount === 0 ? (
                    <div className="p-6 text-center text-xs text-muted-foreground flex flex-col items-center gap-1.5">
                      <CheckCircle2 className="size-6 text-emerald-500 mb-1" />
                      <p className="font-medium text-foreground">100% Roll-Call Submitted</p>
                      <p className="text-xs">All classes have submitted today's attendance.</p>
                    </div>
                  ) : (
                    <ul className="divide-y text-xs">
                      {overview?.classes_missing_today.map((cls) => (
                        <li key={cls.class_id} className="p-3.5 hover:bg-muted/20 flex items-center justify-between gap-2">
                          <div>
                            <div className="font-medium text-foreground text-xs">{cls.class_name}</div>
                            <div className="text-[11px] text-muted-foreground">{cls.school_name}</div>
                          </div>
                          <Link href="/dashboard/attendance">
                            <Button size="sm" variant="outline" className="h-7 text-xs px-2.5 border-primary/30 text-primary hover:bg-primary/5">
                              Record Attendance
                            </Button>
                          </Link>
                        </li>
                      ))}
                    </ul>
                  )}
                </CardContent>
              </Card>
            </div>
          </TabsContent>

          {/* TAB 3: ACTIVE CASES (Clean Table with Quick Search) */}
          <TabsContent value="cases" className="space-y-4 pt-2">
            <Card>
              <CardHeader className="pb-3">
                <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3">
                  <div>
                    <CardTitle className="text-sm font-semibold">Active Early-Warning Cases</CardTitle>
                    <CardDescription className="text-xs">
                      Students flagged by consecutive absence or term-total escalation rules
                    </CardDescription>
                  </div>
                  <Link href="/dashboard/cases">
                    <Button variant="ghost" size="sm" className="h-7 text-xs gap-1 text-primary">
                      <span>Full Directory</span>
                      <ArrowRight className="size-3.5" />
                    </Button>
                  </Link>
                </div>

                {/* Filter and Search Bar */}
                <div className="flex flex-col sm:flex-row items-center gap-2 pt-2">
                  <div className="relative flex-1 w-full">
                    <Search className="absolute left-2.5 top-2.5 size-3.5 text-muted-foreground" />
                    <Input
                      placeholder="Search student by name, school, or ref..."
                      value={caseSearch}
                      onChange={(e) => setCaseSearch(e.target.value)}
                      className="h-8 pl-8 text-xs"
                    />
                  </div>
                  <div className="flex items-center gap-1.5 w-full sm:w-auto">
                    <Button
                      size="sm"
                      variant={levelFilter === null ? "secondary" : "outline"}
                      onClick={() => setLevelFilter(null)}
                      className="h-8 text-xs px-2.5"
                    >
                      All
                    </Button>
                    <Button
                      size="sm"
                      variant={levelFilter === 2 ? "secondary" : "outline"}
                      onClick={() => setLevelFilter(2)}
                      className="h-8 text-xs px-2.5"
                    >
                      Level 2
                    </Button>
                    <Button
                      size="sm"
                      variant={levelFilter === 3 ? "secondary" : "outline"}
                      onClick={() => setLevelFilter(3)}
                      className="h-8 text-xs px-2.5"
                    >
                      Level 3
                    </Button>
                    <Button
                      size="sm"
                      variant={levelFilter === 4 ? "secondary" : "outline"}
                      onClick={() => setLevelFilter(4)}
                      className="h-8 text-xs px-2.5"
                    >
                      Level 4
                    </Button>
                  </div>
                </div>
              </CardHeader>
              <CardContent className="p-0">
                <Table>
                  <TableHeader>
                    <TableRow>
                      <TableHead className="w-28 text-xs">Ref</TableHead>
                      <TableHead className="text-xs">Student</TableHead>
                      <TableHead className="hidden md:table-cell text-xs">School / Class</TableHead>
                      <TableHead className="text-xs">Risk Score</TableHead>
                      <TableHead className="text-xs">Level</TableHead>
                      <TableHead className="text-xs">Status</TableHead>
                      <TableHead className="hidden lg:table-cell text-xs">Assigned Mentor</TableHead>
                      <TableHead className="text-right text-xs">Action</TableHead>
                    </TableRow>
                  </TableHeader>
                  <TableBody>
                    {loading ? (
                      <TableRow>
                        <TableCell colSpan={8} className="text-center py-8 text-xs text-muted-foreground animate-pulse">
                          Loading cases...
                        </TableCell>
                      </TableRow>
                    ) : filteredCases.length === 0 ? (
                      <TableRow>
                        <TableCell colSpan={8} className="text-center py-8 text-xs text-muted-foreground">
                          {caseSearch || levelFilter !== null
                            ? "No cases match the selected filter."
                            : "No active cases flagged."}
                        </TableCell>
                      </TableRow>
                    ) : (
                      filteredCases.slice(0, 10).map((c) => (
                        <TableRow key={c.id} className="hover:bg-muted/20">
                          <TableCell className="font-mono text-xs font-semibold">
                            <Link href={`/dashboard/cases/${c.id}`} className="text-primary hover:underline">
                              {c.ref}
                            </Link>
                          </TableCell>
                          <TableCell>
                            <div className="font-medium text-xs text-foreground">{c.student_name}</div>
                            {c.student_gender && (
                              <span className="text-[11px] text-muted-foreground">{c.student_gender}</span>
                            )}
                          </TableCell>
                          <TableCell className="hidden md:table-cell text-xs text-muted-foreground">
                            {c.school_name} {c.class_name ? `• ${c.class_name}` : ""}
                          </TableCell>
                          <TableCell>{getRiskScoreBadge(c.risk_score)}</TableCell>
                          <TableCell>
                            <Badge variant="outline" className="text-[11px] font-medium">
                              Level {c.level}
                            </Badge>
                          </TableCell>
                          <TableCell>{getStatusBadge(c.status)}</TableCell>
                          <TableCell className="hidden lg:table-cell text-xs text-muted-foreground">
                            {c.mentor_name || <span className="italic text-muted-foreground/70">Unassigned</span>}
                          </TableCell>
                          <TableCell className="text-right">
                            <Link href={`/dashboard/cases/${c.id}`}>
                              <Button variant="ghost" size="sm" className="h-7 text-xs px-2 text-primary font-medium">
                                Review
                              </Button>
                            </Link>
                          </TableCell>
                        </TableRow>
                      ))
                    )}
                  </TableBody>
                </Table>
              </CardContent>
            </Card>
          </TabsContent>
        </Tabs>
      </div>
    </div>
  )
}
