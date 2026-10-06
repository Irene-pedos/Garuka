"use client"

import * as React from "react"
import { Area, AreaChart, CartesianGrid, XAxis } from "recharts"

import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card"
import {
  ChartContainer,
  ChartLegend,
  ChartLegendContent,
  ChartTooltip,
  ChartTooltipContent,
  type ChartConfig,
} from "@/components/ui/chart"
import {
  fetchAttendanceTrends,
  type DailyAttendanceTrendItem,
} from "@/lib/api/client"

export const description = "An interactive area chart showing daily attendance and absence trends"

const chartConfig = {
  present: {
    label: "Present Students",
    color: "var(--chart-1)",
  },
  absent: {
    label: "Absent Students",
    color: "var(--chart-2)",
  },
} satisfies ChartConfig

export type TimelineRange = "7d" | "30d" | "90d"

interface ChartAreaInteractiveProps {
  data?: DailyAttendanceTrendItem[]
  isLoading?: boolean
  onTimeRangeChange?: (range: TimelineRange) => void
}

export function ChartAreaInteractive({
  data = [],
  isLoading = false,
  onTimeRangeChange,
}: ChartAreaInteractiveProps) {
  const [timeRange, setTimeRange] = React.useState<TimelineRange>("90d")
  const [trendData, setTrendData] = React.useState<DailyAttendanceTrendItem[]>(data)
  const [rangeLoading, setRangeLoading] = React.useState(false)

  // Sync with incoming parent prop updates
  React.useEffect(() => {
    if (data && data.length > 0) {
      setTrendData(data)
    }
  }, [data])

  // Handle timeline change: notify parent, fetch fresh data for this window if needed
  const handleTimeRangeSelect = async (newRange: TimelineRange) => {
    setTimeRange(newRange)
    onTimeRangeChange?.(newRange)

    const days = newRange === "7d" ? 7 : newRange === "30d" ? 30 : 90
    setRangeLoading(true)
    try {
      const fetched = await fetchAttendanceTrends(days)
      if (fetched && fetched.length > 0) {
        setTrendData(fetched)
      }
    } catch {
      // Keep existing data on network failure
    } finally {
      setRangeLoading(false)
    }
  }

  // Build the framed timeline data for the chosen window
  const framedData = React.useMemo(() => {
    if (!trendData || trendData.length === 0) return []

    const daysCount = timeRange === "7d" ? 7 : timeRange === "30d" ? 30 : 90

    // Map existing data points by YYYY-MM-DD
    const dataMap = new Map<string, DailyAttendanceTrendItem>()
    for (const item of trendData) {
      dataMap.set(item.date, item)
    }

    // Determine latest reference date (either today or the latest record date)
    const sortedDates = [...trendData.map((d) => d.date)].sort()
    const latestRecordDate = sortedDates[sortedDates.length - 1]
    const todayStr = new Date().toISOString().split("T")[0]
    const anchorStr =
      latestRecordDate && latestRecordDate > todayStr
        ? latestRecordDate
        : latestRecordDate || todayStr

    // Parse date safely avoiding UTC midnight shifting
    const [y, m, d] = anchorStr.split("-").map(Number)
    const anchorDate = new Date(y, m - 1, d)

    const result: DailyAttendanceTrendItem[] = []
    for (let i = daysCount - 1; i >= 0; i--) {
      const curDate = new Date(anchorDate)
      curDate.setDate(curDate.getDate() - i)
      const curYear = curDate.getFullYear()
      const curMonth = String(curDate.getMonth() + 1).padStart(2, "0")
      const curDay = String(curDate.getDate()).padStart(2, "0")
      const dateKey = `${curYear}-${curMonth}-${curDay}`

      if (dataMap.has(dateKey)) {
        result.push(dataMap.get(dateKey)!)
      } else {
        result.push({
          date: dateKey,
          present: 0,
          absent: 0,
          enrolled: 0,
          cases: 0,
        })
      }
    }

    return result
  }, [trendData, timeRange])

  // Summary statistics for the active window
  const stats = React.useMemo(() => {
    const recordedDays = framedData.filter((d) => d.present > 0 || d.absent > 0)
    const totalPresent = recordedDays.reduce((acc, d) => acc + d.present, 0)
    const totalAbsent = recordedDays.reduce((acc, d) => acc + d.absent, 0)
    const totalSubmissions = recordedDays.length
    const avgAttendance =
      totalPresent + totalAbsent > 0
        ? ((totalPresent / (totalPresent + totalAbsent)) * 100).toFixed(1)
        : null

    return {
      totalSubmissions,
      totalPresent,
      totalAbsent,
      avgAttendance,
    }
  }, [framedData])

  return (
    <Card className="pt-0">
      <CardHeader className="flex flex-col gap-4 border-b py-4 sm:flex-row sm:items-center sm:justify-between">
        <div className="grid gap-1">
          <div className="flex items-center gap-2">
            <CardTitle className="text-base font-semibold">Attendance Trends</CardTitle>
            {stats.avgAttendance && (
              <span className="inline-flex items-center px-2 py-0.5 rounded-full text-[11px] font-semibold bg-emerald-500/10 text-emerald-700 dark:text-emerald-400 border border-emerald-500/20">
                {stats.avgAttendance}% Avg Rate
              </span>
            )}
          </div>
          <CardDescription className="text-xs">
            {timeRange === "7d"
              ? "Daily attendance roll-calls for the past 7 days"
              : timeRange === "30d"
              ? "Daily attendance roll-calls for the past 30 days"
              : "Quarterly attendance roll-calls for the past 3 months (90 days)"}
            {stats.totalSubmissions > 0 && ` • ${stats.totalSubmissions} days recorded`}
          </CardDescription>
        </div>

        {/* Timeline Range Selector Pills (Accessible & Visible on all screens) */}
        <div className="flex items-center gap-1 bg-muted/70 p-1 rounded-lg border border-border/60 self-start sm:self-auto shadow-2xs">
          {[
            { id: "7d" as const, label: "Last 7 days", shortLabel: "7D" },
            { id: "30d" as const, label: "Last 30 days", shortLabel: "30D" },
            { id: "90d" as const, label: "Last 3 months", shortLabel: "3M" },
          ].map((tab) => (
            <button
              key={tab.id}
              type="button"
              onClick={() => handleTimeRangeSelect(tab.id)}
              disabled={rangeLoading}
              aria-pressed={timeRange === tab.id}
              className={`px-3 py-1 text-xs font-medium rounded-md transition-all cursor-pointer ${
                timeRange === tab.id
                  ? "bg-background text-foreground shadow-xs font-semibold"
                  : "text-muted-foreground hover:text-foreground hover:bg-background/50"
              }`}
            >
              <span className="hidden sm:inline">{tab.label}</span>
              <span className="sm:hidden">{tab.shortLabel}</span>
            </button>
          ))}
        </div>
      </CardHeader>

      <CardContent className="px-2 pt-4 sm:px-6 sm:pt-6">
        {isLoading ? (
          <div className="flex h-[250px] w-full items-center justify-center text-sm text-muted-foreground animate-pulse">
            Loading attendance trends from database...
          </div>
        ) : framedData.length === 0 ? (
          <div className="flex h-[250px] w-full flex-col items-center justify-center gap-1 text-sm text-muted-foreground">
            <p className="font-medium text-foreground">No attendance records in this window</p>
            <p className="text-xs">Submissions logged via USSD or Web roll-call will plot here automatically.</p>
          </div>
        ) : (
          <ChartContainer
            config={chartConfig}
            className="aspect-auto h-[250px] w-full"
          >
            <AreaChart data={framedData}>
              <defs>
                <linearGradient id="fillPresent" x1="0" y1="0" x2="0" y2="1">
                  <stop
                    offset="5%"
                    stopColor="var(--color-present)"
                    stopOpacity={0.8}
                  />
                  <stop
                    offset="95%"
                    stopColor="var(--color-present)"
                    stopOpacity={0.1}
                  />
                </linearGradient>
                <linearGradient id="fillAbsent" x1="0" y1="0" x2="0" y2="1">
                  <stop
                    offset="5%"
                    stopColor="var(--color-absent)"
                    stopOpacity={0.8}
                  />
                  <stop
                    offset="95%"
                    stopColor="var(--color-absent)"
                    stopOpacity={0.1}
                  />
                </linearGradient>
              </defs>
              <CartesianGrid vertical={false} />
              <XAxis
                dataKey="date"
                tickLine={false}
                axisLine={false}
                tickMargin={8}
                minTickGap={timeRange === "7d" ? 12 : timeRange === "30d" ? 24 : 36}
                tickFormatter={(value) => {
                  const [y, m, d] = String(value).split("-").map(Number)
                  const date = new Date(y, m - 1, d)
                  if (timeRange === "7d") {
                    return date.toLocaleDateString("en-US", {
                      weekday: "short",
                      day: "numeric",
                    })
                  }
                  return date.toLocaleDateString("en-US", {
                    month: "short",
                    day: "numeric",
                  })
                }}
              />
              <ChartTooltip
                cursor={false}
                content={
                  <ChartTooltipContent
                    labelFormatter={(value) => {
                      const [y, m, d] = String(value).split("-").map(Number)
                      const date = new Date(y, m - 1, d)
                      return date.toLocaleDateString("en-US", {
                        weekday: "long",
                        month: "short",
                        day: "numeric",
                        year: "numeric",
                      })
                    }}
                    indicator="dot"
                  />
                }
              />
              <Area
                dataKey="absent"
                type="natural"
                fill="url(#fillAbsent)"
                stroke="var(--color-absent)"
                stackId="a"
                isAnimationActive={true}
              />
              <Area
                dataKey="present"
                type="natural"
                fill="url(#fillPresent)"
                stroke="var(--color-present)"
                stackId="a"
                isAnimationActive={true}
              />
              <ChartLegend content={<ChartLegendContent />} />
            </AreaChart>
          </ChartContainer>
        )}
      </CardContent>
    </Card>
  )
}
