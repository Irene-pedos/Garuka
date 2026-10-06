"use client"

import * as React from "react"
import Link from "next/link"
import { usePathname } from "next/navigation"
import { useAuth } from "@/lib/auth-context"
import { NavUser } from "@/components/nav-user"
import {
  Sidebar,
  SidebarContent,
  SidebarFooter,
  SidebarGroup,
  SidebarGroupContent,
  SidebarGroupLabel,
  SidebarHeader,
  SidebarMenu,
  SidebarMenuButton,
  SidebarMenuItem,
  SidebarRail,
  useSidebar,
} from "@/components/ui/sidebar"
import {
  LayoutDashboard,
  FolderOpen,
  CalendarCheck,
  GraduationCap,
  UserCheck,
  BarChart3,
  HelpCircle,
  Users,
  Building2,
  Sliders,
  Mail,
  ShieldCheck,
  School,
} from "lucide-react"

interface NavItem {
  title: string
  url: string
  icon: React.ComponentType<{ className?: string }>
  roles?: string[]
}

const OPERATIONS_NAV: NavItem[] = [
  { title: "Overview", url: "/dashboard", icon: LayoutDashboard },
  { title: "Cases & Actions", url: "/dashboard/cases", icon: FolderOpen },
  {
    title: "Attendance",
    url: "/dashboard/attendance",
    icon: CalendarCheck,
    roles: ["admin", "head_teacher", "teacher"],
  },
  {
    title: "Students",
    url: "/dashboard/students",
    icon: GraduationCap,
    roles: ["admin", "head_teacher"],
  },
  {
    title: "Mentors",
    url: "/dashboard/mentors",
    icon: UserCheck,
    roles: ["admin", "sector_officer"],
  },
  {
    title: "Schools Compare",
    url: "/dashboard/schools-compare",
    icon: BarChart3,
    roles: ["admin", "sector_officer", "district_director"],
  },
  {
    title: "Help Requests",
    url: "/dashboard/help-requests",
    icon: HelpCircle,
    roles: ["admin", "head_teacher", "sector_officer"],
  },
]

const ADMIN_NAV: NavItem[] = [
  {
    title: "Users & Roles",
    url: "/dashboard/users",
    icon: Users,
    roles: ["admin", "sector_officer", "head_teacher"],
  },
  {
    title: "Schools",
    url: "/dashboard/schools",
    icon: Building2,
    roles: ["admin"],
  },
  {
    title: "SMS Outbox",
    url: "/dashboard/sms-outbox",
    icon: Mail,
    roles: ["admin"],
  },
  {
    title: "Audit Trail",
    url: "/dashboard/audit",
    icon: ShieldCheck,
    roles: ["admin"],
  },
  {
    title: "System Settings",
    url: "/dashboard/settings",
    icon: Sliders,
    roles: ["admin"],
  },
]

export function AppSidebar({ ...props }: React.ComponentProps<typeof Sidebar>) {
  const { user } = useAuth()
  const pathname = usePathname()
  const { isMobile, setOpenMobile } = useSidebar()

  if (!user) return null

  const userRole = user.role
  const visibleOperations = OPERATIONS_NAV.filter(
    (item) => !item.roles || item.roles.includes(userRole)
  )
  const visibleAdmin = ADMIN_NAV.filter(
    (item) => !item.roles || item.roles.includes(userRole)
  )

  const handleNavClick = () => {
    if (isMobile) {
      setOpenMobile(false)
    }
  }

  return (
    <Sidebar collapsible="icon" {...props}>
      <SidebarHeader>
        <SidebarMenu>
          <SidebarMenuItem>
            <SidebarMenuButton
              size="default"
              className="h-10"
              render={<Link href="/dashboard" onClick={handleNavClick} />}
            >
              <div className="flex aspect-square size-7 items-center justify-center rounded-md bg-primary text-primary-foreground font-bold shadow-xs shrink-0">
                <School className="size-3.5" />
              </div>
              <div className="grid flex-1 text-left leading-tight truncate">
                <span className="truncate font-bold tracking-tight text-primary text-sm">
                  Garuka
                </span>
                <span className="truncate text-[10px] text-muted-foreground capitalize">
                  {userRole.replace("_", " ")}
                </span>
              </div>
            </SidebarMenuButton>
          </SidebarMenuItem>
        </SidebarMenu>
      </SidebarHeader>

      <SidebarContent>
        {/* Operations Section */}
        <SidebarGroup>
          <SidebarGroupLabel className="text-[11px] font-semibold text-muted-foreground/80 tracking-wider">
            Operations
          </SidebarGroupLabel>
          <SidebarGroupContent>
            <SidebarMenu>
              {visibleOperations.map((item) => {
                const isActive =
                  item.url === "/dashboard"
                    ? pathname === "/dashboard"
                    : pathname.startsWith(item.url)
                const Icon = item.icon
                return (
                  <SidebarMenuItem key={item.title}>
                    <SidebarMenuButton
                      render={<Link href={item.url} onClick={handleNavClick} />}
                      isActive={isActive}
                      tooltip={item.title}
                      className="text-xs"
                    >
                      <Icon className="size-4 shrink-0" />
                      <span className="truncate">{item.title}</span>
                    </SidebarMenuButton>
                  </SidebarMenuItem>
                )
              })}
            </SidebarMenu>
          </SidebarGroupContent>
        </SidebarGroup>

        {/* Administration Section (if permitted) */}
        {visibleAdmin.length > 0 && (
          <SidebarGroup>
            <SidebarGroupLabel className="text-[11px] font-semibold text-muted-foreground/80 tracking-wider">
              Administration
            </SidebarGroupLabel>
            <SidebarGroupContent>
              <SidebarMenu>
                {visibleAdmin.map((item) => {
                  const isActive = pathname.startsWith(item.url)
                  const Icon = item.icon
                  return (
                    <SidebarMenuItem key={item.title}>
                      <SidebarMenuButton
                        render={<Link href={item.url} onClick={handleNavClick} />}
                        isActive={isActive}
                        tooltip={item.title}
                        className="text-xs"
                      >
                        <Icon className="size-4 shrink-0" />
                        <span className="truncate">{item.title}</span>
                      </SidebarMenuButton>
                    </SidebarMenuItem>
                  )
                })}
              </SidebarMenu>
            </SidebarGroupContent>
          </SidebarGroup>
        )}
      </SidebarContent>

      <SidebarFooter>
        <NavUser
          user={{
            name: user.full_name,
            email: user.email || "",
            role: user.role,
            avatar: user.avatar_url,
          }}
        />
      </SidebarFooter>
      <SidebarRail />
    </Sidebar>
  )
}
