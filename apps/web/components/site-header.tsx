"use client"

import Link from "next/link"
import { usePathname } from "next/navigation"
import { useAuth } from "@/lib/auth-context"
import { Separator } from "@/components/ui/separator"
import { SidebarTrigger } from "@/components/ui/sidebar"
import {
  Breadcrumb,
  BreadcrumbItem,
  BreadcrumbLink,
  BreadcrumbList,
  BreadcrumbPage,
  BreadcrumbSeparator,
} from "@/components/ui/breadcrumb"
import { Badge } from "@/components/ui/badge"
import { Clock } from "lucide-react"
import { ModeToggle } from "@/components/mode-toggle"

const ROUTE_LABELS: Record<string, string> = {
  "/dashboard": "Overview",
  "/dashboard/cases": "Cases & Interventions",
  "/dashboard/attendance": "Attendance Compliance",
  "/dashboard/students": "Students Directory",
  "/dashboard/mentors": "Community Mentors",
  "/dashboard/schools-compare": "Schools Comparison",
  "/dashboard/help-requests": "Help Requests",
  "/dashboard/users": "User Management",
  "/dashboard/schools": "Schools Management",
  "/dashboard/settings": "System Settings",
  "/dashboard/sms-outbox": "SMS Outbox",
  "/dashboard/audit": "Audit Logs",
  "/dashboard/account": "Account Settings",
}

export function SiteHeader() {
  const pathname = usePathname()
  const { user } = useAuth()

  const currentLabel = ROUTE_LABELS[pathname] || (
    pathname.startsWith("/dashboard/cases/") ? "Case Details" : "Dashboard"
  )

  const isRoot = pathname === "/dashboard"

  return (
    <header className="flex h-(--header-height) shrink-0 items-center justify-between gap-2 border-b bg-card/60 backdrop-blur-xs px-4 lg:px-6 transition-[width,height] ease-linear group-has-data-[collapsible=icon]/sidebar-wrapper:h-(--header-height)">
      <div className="flex items-center gap-2">
        <SidebarTrigger className="-ml-1" />
        <Separator
          orientation="vertical"
          className="mx-1 h-4 data-vertical:self-auto"
        />
        <Breadcrumb>
          <BreadcrumbList>
            <BreadcrumbItem>
              {isRoot ? (
                <BreadcrumbPage className="font-semibold text-foreground">Overview</BreadcrumbPage>
              ) : (
                <BreadcrumbLink render={<Link href="/dashboard" />}>
                  Garuka
                </BreadcrumbLink>
              )}
            </BreadcrumbItem>
            {!isRoot && (
              <>
                <BreadcrumbSeparator />
                <BreadcrumbItem>
                  <BreadcrumbPage className="font-semibold text-foreground">
                    {currentLabel}
                  </BreadcrumbPage>
                </BreadcrumbItem>
              </>
            )}
          </BreadcrumbList>
        </Breadcrumb>
      </div>

      <div className="flex items-center gap-2.5">
        <div className="hidden sm:flex items-center gap-1.5 text-xs text-muted-foreground bg-muted/60 px-2.5 py-1 rounded-md border">
          <Clock className="w-3.5 h-3.5 text-primary" />
          <span>Africa/Kigali (UTC+2)</span>
        </div>
        {user && (
          <Badge variant="outline" className="text-xs uppercase tracking-wider font-semibold py-0.5 px-2 bg-primary/5 text-primary border-primary/20">
            {user.role.replace("_", " ")}
          </Badge>
        )}
        <ModeToggle />
      </div>
    </header>
  )
}
