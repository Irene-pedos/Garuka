"use client"

import Link from "next/link"
import { Badge } from "@/components/ui/badge"
import {
  Card,
  CardAction,
  CardDescription,
  CardFooter,
  CardHeader,
  CardTitle,
} from "@/components/ui/card"
import {
  AlertTriangle,
  CalendarX2,
  FolderOpen,
  HelpCircle,
  TrendingDown,
  TrendingUp,
} from "lucide-react"
import type { OverviewKPIs } from "@/lib/api/client"

interface SectionCardsProps {
  kpis?: OverviewKPIs | null
}

export function SectionCards({ kpis }: SectionCardsProps) {
  const openCases = kpis?.open_cases ?? 0
  const missingToday = kpis?.classes_missing_today ?? 0
  const compliancePct = kpis?.attendance_compliance_pct ?? 0
  const overdueVisits = kpis?.visits_overdue ?? 0
  const escalations = kpis?.recent_escalations_count ?? 0
  const helpRequests = kpis?.pending_help_requests_count ?? 0
  const slaBreaches = kpis?.visits_overdue ?? 0

  return (
    <div className="grid grid-cols-1 gap-4 px-4 *:data-[slot=card]:bg-linear-to-t *:data-[slot=card]:from-primary/5 *:data-[slot=card]:to-card *:data-[slot=card]:shadow-xs lg:px-6 @xl/main:grid-cols-2 @5xl/main:grid-cols-4 dark:*:data-[slot=card]:bg-card">
      {/* 1. Open Cases Card */}
      <Link href="/dashboard/cases" className="group">
        <Card className="@container/card transition-all hover:border-primary/50 cursor-pointer">
          <CardHeader>
            <div className="flex items-center justify-between w-full">
              <CardDescription>Open Cases</CardDescription>
              <FolderOpen className="size-4 text-muted-foreground group-hover:text-primary transition-colors" />
            </div>
            <CardTitle className="text-2xl font-semibold tabular-nums @[250px]/card:text-3xl text-foreground">
              {openCases}
            </CardTitle>
            <CardAction>
              <Badge variant={escalations > 0 ? "destructive" : "outline"} className="gap-1 text-xs">
                {escalations > 0 ? (
                  <>
                    <TrendingUp className="size-3" />
                    {escalations} Escalated
                  </>
                ) : (
                  <>
                    <TrendingDown className="size-3" />
                    Active
                  </>
                )}
              </Badge>
            </CardAction>
          </CardHeader>
          <CardFooter className="flex-col items-start gap-1.5 text-sm">
            <div className="line-clamp-1 flex gap-1.5 font-medium text-foreground">
              Active dropout interventions
            </div>
            <div className="text-muted-foreground text-xs">
              {openCases} student cases under active tracking
            </div>
          </CardFooter>
        </Card>
      </Link>

      {/* 2. Attendance Compliance Card */}
      <Link href="/dashboard/attendance" className="group">
        <Card className="@container/card transition-all hover:border-primary/50 cursor-pointer">
          <CardHeader>
            <div className="flex items-center justify-between w-full">
              <CardDescription>Daily Attendance</CardDescription>
              <CalendarX2 className="size-4 text-muted-foreground group-hover:text-primary transition-colors" />
            </div>
            <CardTitle className="text-2xl font-semibold tabular-nums @[250px]/card:text-3xl text-foreground">
              {compliancePct}%
            </CardTitle>
            <CardAction>
              <Badge
                variant={missingToday > 0 ? "outline" : "secondary"}
                className={missingToday > 0 ? "border-amber-500/50 text-amber-600 dark:text-amber-400 gap-1 text-xs" : "gap-1 text-xs"}
              >
                {missingToday > 0 ? `${missingToday} missing` : "100% complete"}
              </Badge>
            </CardAction>
          </CardHeader>
          <CardFooter className="flex-col items-start gap-1.5 text-sm">
            <div className="line-clamp-1 flex gap-1.5 font-medium text-foreground">
              {missingToday > 0 ? `${missingToday} classes need roll call` : "All classes submitted"}
            </div>
            <div className="text-muted-foreground text-xs">
              Kigali business-day submission rate
            </div>
          </CardFooter>
        </Card>
      </Link>

      {/* 3. SLA Breaches & Overdue Visits */}
      <Link href="/dashboard/cases?level=3" className="group">
        <Card className="@container/card transition-all hover:border-primary/50 cursor-pointer">
          <CardHeader>
            <div className="flex items-center justify-between w-full">
              <CardDescription>SLA & Overdue Visits</CardDescription>
              <AlertTriangle className="size-4 text-muted-foreground group-hover:text-destructive transition-colors" />
            </div>
            <CardTitle className="text-2xl font-semibold tabular-nums @[250px]/card:text-3xl text-foreground">
              {overdueVisits}
            </CardTitle>
            <CardAction>
              <Badge
                variant={slaBreaches > 0 ? "destructive" : "outline"}
                className="gap-1 text-xs"
              >
                {slaBreaches > 0 ? `${slaBreaches} SLA breaches` : "On schedule"}
              </Badge>
            </CardAction>
          </CardHeader>
          <CardFooter className="flex-col items-start gap-1.5 text-sm">
            <div className="line-clamp-1 flex gap-1.5 font-medium text-foreground">
              {slaBreaches > 0 ? "Requires urgent follow-up" : "Within 3-day SLA window"}
            </div>
            <div className="text-muted-foreground text-xs">
              {overdueVisits} pending mentor visits
            </div>
          </CardFooter>
        </Card>
      </Link>

      {/* 4. Community Help Requests */}
      <Link href="/dashboard/help-requests" className="group">
        <Card className="@container/card transition-all hover:border-primary/50 cursor-pointer">
          <CardHeader>
            <div className="flex items-center justify-between w-full">
              <CardDescription>Help Requests</CardDescription>
              <HelpCircle className="size-4 text-muted-foreground group-hover:text-primary transition-colors" />
            </div>
            <CardTitle className="text-2xl font-semibold tabular-nums @[250px]/card:text-3xl text-foreground">
              {helpRequests}
            </CardTitle>
            <CardAction>
              <Badge variant="outline" className="gap-1 text-xs">
                {helpRequests} pending triage
              </Badge>
            </CardAction>
          </CardHeader>
          <CardFooter className="flex-col items-start gap-1.5 text-sm">
            <div className="line-clamp-1 flex gap-1.5 font-medium text-foreground">
              Community & parent requests
            </div>
            <div className="text-muted-foreground text-xs">
              Awaiting school / sector action
            </div>
          </CardFooter>
        </Card>
      </Link>
    </div>
  )
}
