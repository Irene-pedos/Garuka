"use client";

import Link from "next/link";
import { useAuth } from "@/lib/auth-context";
import { Button } from "@/components/ui/button";

export default function DashboardOverviewPage() {
  const { user } = useAuth();

  if (!user) return null;

  return (
    <div className="space-y-6 max-w-6xl">
      <div>
        <h1 className="text-2xl font-bold tracking-tight">Overview</h1>
        <p className="text-sm text-muted-foreground">
          Welcome back, {user.full_name} ({user.role.replace("_", " ")})
        </p>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
        <div className="border rounded-xl p-5 bg-card shadow-sm space-y-2">
          <p className="text-xs font-semibold uppercase text-muted-foreground">Assigned Role</p>
          <p className="text-2xl font-bold text-primary capitalize">{user.role.replace("_", " ")}</p>
          <p className="text-xs text-muted-foreground">
            {user.school_id ? "Scoped to School" : user.sector_id ? "Scoped to Sector" : "National / District"}
          </p>
        </div>

        <div className="border rounded-xl p-5 bg-card shadow-sm space-y-2">
          <p className="text-xs font-semibold uppercase text-muted-foreground">Active Term</p>
          <p className="text-2xl font-bold text-foreground">Term 1 (2026)</p>
          <p className="text-xs text-emerald-600 font-medium">In Session</p>
        </div>

        <div className="border rounded-xl p-5 bg-card shadow-sm space-y-2">
          <p className="text-xs font-semibold uppercase text-muted-foreground">Language</p>
          <p className="text-2xl font-bold text-foreground uppercase">{user.language}</p>
          <p className="text-xs text-muted-foreground">Kinyarwanda / English</p>
        </div>

        <div className="border rounded-xl p-5 bg-card shadow-sm space-y-2">
          <p className="text-xs font-semibold uppercase text-muted-foreground">System Status</p>
          <p className="text-2xl font-bold text-emerald-600">Active</p>
          <p className="text-xs text-muted-foreground">Milestone M1 Verified</p>
        </div>
      </div>

      <div className="border rounded-xl p-6 bg-card space-y-4 shadow-sm">
        <h2 className="font-semibold text-lg">Quick Actions</h2>
        <div className="flex flex-wrap gap-3">
          {["admin", "head_teacher"].includes(user.role) && (
            <>
              <Link href="/dashboard/students">
                <Button>Manage Students & Import CSV</Button>
              </Link>
              <Link href="/dashboard/users">
                <Button variant="outline">Manage Staff & Reset PINs</Button>
              </Link>
            </>
          )}
          {["admin", "head_teacher", "teacher"].includes(user.role) && (
            <Link href="/dashboard/attendance">
              <Button variant="outline">Classes & Attendance</Button>
            </Link>
          )}
          {user.role === "admin" && (
            <Link href="/dashboard/schools">
              <Button variant="outline">Manage Schools & Sectors</Button>
            </Link>
          )}
        </div>
      </div>
    </div>
  );
}
