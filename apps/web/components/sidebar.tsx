"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { useAuth } from "@/lib/auth-context";
import { Button } from "@/components/ui/button";
import {
  LayoutDashboard,
  FolderOpen,
  GraduationCap,
  CalendarCheck,
  UserCheck,
  BarChart3,
  HelpCircle,
  Users,
  Building2,
  Sliders,
  Mail,
  ShieldCheck,
  LogOut,
  X,
} from "lucide-react";

interface NavItem {
  label: string;
  href: string;
  icon: React.ComponentType<{ className?: string }>;
  roles?: string[];
}

const NAV_ITEMS: NavItem[] = [
  { label: "Overview", href: "/dashboard", icon: LayoutDashboard },
  { label: "Cases", href: "/dashboard/cases", icon: FolderOpen },
  {
    label: "Students",
    href: "/dashboard/students",
    icon: GraduationCap,
    roles: ["admin", "head_teacher"],
  },
  {
    label: "Attendance",
    href: "/dashboard/attendance",
    icon: CalendarCheck,
    roles: ["admin", "head_teacher", "teacher"],
  },
  {
    label: "Mentors",
    href: "/dashboard/mentors",
    icon: UserCheck,
    roles: ["admin", "sector_officer"],
  },
  {
    label: "Schools Compare",
    href: "/dashboard/schools-compare",
    icon: BarChart3,
    roles: ["admin", "sector_officer", "district_director"],
  },
  {
    label: "Help Requests",
    href: "/dashboard/help-requests",
    icon: HelpCircle,
    roles: ["admin", "head_teacher", "sector_officer"],
  },
  {
    label: "Users",
    href: "/dashboard/users",
    icon: Users,
    roles: ["admin", "sector_officer", "head_teacher"],
  },
  {
    label: "Schools",
    href: "/dashboard/schools",
    icon: Building2,
    roles: ["admin"],
  },
  {
    label: "Settings",
    href: "/dashboard/settings",
    icon: Sliders,
    roles: ["admin"],
  },
  {
    label: "SMS Outbox",
    href: "/dashboard/sms-outbox",
    icon: Mail,
    roles: ["admin"],
  },
  {
    label: "Audit Logs",
    href: "/dashboard/audit",
    icon: ShieldCheck,
    roles: ["admin"],
  },
];

interface SidebarProps {
  mobileOpen?: boolean;
  onMobileClose?: () => void;
}

export function Sidebar({ mobileOpen = false, onMobileClose }: SidebarProps) {
  const { user, logout } = useAuth();
  const pathname = usePathname();

  if (!user) return null;

  const userRole = user.role;
  const visibleNav = NAV_ITEMS.filter(
    (item) => !item.roles || item.roles.includes(userRole)
  );

  const sidebarContent = (
    <div className="flex flex-col h-full bg-card">
      <div className="p-5 border-b flex items-center justify-between">
        <div>
          <h2 className="font-bold text-xl tracking-tight text-primary">Garuka</h2>
          <p className="text-xs text-muted-foreground uppercase tracking-wider font-semibold">
            {userRole.replace("_", " ")}
          </p>
        </div>
        {onMobileClose && (
          <button
            type="button"
            onClick={onMobileClose}
            aria-label="Close menu"
            className="md:hidden p-1.5 rounded-lg text-muted-foreground hover:text-foreground hover:bg-muted focus:outline-hidden focus:ring-2 focus:ring-ring"
          >
            <X className="h-5 w-5" />
          </button>
        )}
      </div>

      <nav className="flex-1 p-3 space-y-1 overflow-y-auto" aria-label="Main Navigation">
        {visibleNav.map((item) => {
          const isActive = pathname === item.href;
          const Icon = item.icon;
          return (
            <Link
              key={item.href}
              href={item.href}
              onClick={() => onMobileClose?.()}
              className={`flex items-center gap-3 px-3 py-2 text-sm font-medium rounded-lg transition-colors focus:outline-hidden focus:ring-2 focus:ring-ring ${
                isActive
                  ? "bg-primary text-primary-foreground font-semibold shadow-xs"
                  : "text-muted-foreground hover:bg-muted hover:text-foreground"
              }`}
            >
              <Icon className="h-4 w-4 shrink-0" />
              <span>{item.label}</span>
            </Link>
          );
        })}
      </nav>

      <div className="p-4 border-t space-y-3 bg-muted/20">
        <div className="text-xs">
          <p className="font-semibold text-foreground truncate">{user.full_name}</p>
          <p className="text-muted-foreground truncate">{user.email || user.phone_masked}</p>
        </div>
        <Button
          variant="outline"
          size="sm"
          onClick={logout}
          className="w-full flex items-center justify-center gap-2 text-destructive hover:text-destructive"
        >
          <LogOut className="h-4 w-4" />
          <span>Sign Out</span>
        </Button>
      </div>
    </div>
  );

  return (
    <>
      {/* Desktop Sticky Sidebar */}
      <aside className="hidden md:flex w-64 border-r shrink-0 min-h-screen flex-col">
        {sidebarContent}
      </aside>

      {/* Mobile Drawer Backdrop & Drawer */}
      {mobileOpen && (
        <div
          className="fixed inset-0 z-50 md:hidden bg-black/60 backdrop-blur-xs transition-opacity animate-in fade-in"
          onClick={onMobileClose}
        >
          <div
            className="fixed inset-y-0 left-0 w-72 max-w-[80vw] bg-card border-r shadow-2xl animate-in slide-in-from-left duration-200"
            onClick={(e) => e.stopPropagation()}
            role="dialog"
            aria-modal="true"
            aria-label="Navigation drawer"
          >
            {sidebarContent}
          </div>
        </div>
      )}
    </>
  );
}
