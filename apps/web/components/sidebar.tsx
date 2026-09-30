"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { useAuth } from "@/lib/auth-context";
import { Button } from "@/components/ui/button";

interface NavItem {
  label: string;
  href: string;
  roles?: string[];
}

const NAV_ITEMS: NavItem[] = [
  { label: "Overview", href: "/dashboard" },
  { label: "Cases", href: "/dashboard/cases" },
  {
    label: "Students",
    href: "/dashboard/students",
    roles: ["admin", "head_teacher"],
  },
  {
    label: "Classes & Attendance",
    href: "/dashboard/attendance",
    roles: ["admin", "head_teacher", "teacher"],
  },
  {
    label: "Mentors",
    href: "/dashboard/mentors",
    roles: ["admin", "sector_officer"],
  },
  {
    label: "Schools Compare",
    href: "/dashboard/schools-compare",
    roles: ["admin", "sector_officer", "district_director"],
  },
  {
    label: "Help Requests",
    href: "/dashboard/help-requests",
    roles: ["admin", "head_teacher", "sector_officer"],
  },
  {
    label: "Users",
    href: "/dashboard/users",
    roles: ["admin", "sector_officer", "head_teacher"],
  },
  {
    label: "Schools",
    href: "/dashboard/schools",
    roles: ["admin"],
  },
];

export function Sidebar() {
  const { user, logout } = useAuth();
  const pathname = usePathname();

  if (!user) return null;

  const userRole = user.role;
  const visibleNav = NAV_ITEMS.filter(
    (item) => !item.roles || item.roles.includes(userRole)
  );

  return (
    <aside className="w-64 border-r bg-card flex flex-col min-h-screen">
      <div className="p-6 border-b flex items-center justify-between">
        <div>
          <h2 className="font-bold text-xl tracking-tight text-primary">Garuka</h2>
          <p className="text-xs text-muted-foreground uppercase tracking-wider font-semibold">
            {userRole.replace("_", " ")}
          </p>
        </div>
      </div>

      <nav className="flex-1 p-4 space-y-1">
        {visibleNav.map((item) => {
          const isActive = pathname === item.href;
          return (
            <Link
              key={item.href}
              href={item.href}
              className={`flex items-center px-3 py-2 text-sm font-medium rounded-md transition-colors ${
                isActive
                  ? "bg-primary text-primary-foreground font-semibold"
                  : "text-muted-foreground hover:bg-muted hover:text-foreground"
              }`}
            >
              {item.label}
            </Link>
          );
        })}
      </nav>

      <div className="p-4 border-t space-y-2">
        <div className="text-xs">
          <p className="font-medium text-foreground truncate">{user.full_name}</p>
          <p className="text-muted-foreground truncate">{user.email || user.phone_masked}</p>
        </div>
        <Button variant="outline" size="sm" onClick={logout} className="w-full">
          Sign out
        </Button>
      </div>
    </aside>
  );
}
