"use client";

import { UserItem } from "@/lib/api/client";
import { Users, GraduationCap, HeartHandshake, CheckCircle2 } from "lucide-react";

interface StaffStatsProps {
  users: UserItem[];
  loading: boolean;
}

export function StaffStats({ users, loading }: StaffStatsProps) {
  const total = users.length;
  const teachers = users.filter((u) => u.role === "teacher");
  const mentors = users.filter((u) => u.role === "mentor");
  const activeCount = users.filter((u) => u.is_active).length;

  const teachersWithClasses = teachers.filter(
    (t) => t.assigned_classes && t.assigned_classes.length > 0
  ).length;
  const teachersWithoutClasses = teachers.length - teachersWithClasses;

  return (
    <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
      {/* Total Staff */}
      <div className="p-3.5 rounded-xl border bg-card shadow-2xs flex flex-col justify-between">
        <div className="flex items-center justify-between text-muted-foreground mb-1">
          <span className="text-xs font-medium">Total Staff</span>
          <Users className="h-4 w-4 text-primary/70" />
        </div>
        <div>
          <div className="text-2xl font-bold tracking-tight text-foreground">
            {loading ? "—" : total}
          </div>
          <p className="text-[11px] text-muted-foreground mt-0.5">
            Registered accounts
          </p>
        </div>
      </div>

      {/* Classroom Teachers */}
      <div className="p-3.5 rounded-xl border bg-card shadow-2xs flex flex-col justify-between">
        <div className="flex items-center justify-between text-muted-foreground mb-1">
          <span className="text-xs font-medium">Teachers</span>
          <GraduationCap className="h-4 w-4 text-emerald-600 dark:text-emerald-400" />
        </div>
        <div>
          <div className="text-2xl font-bold tracking-tight text-foreground">
            {loading ? "—" : teachers.length}
          </div>
          <p className="text-[11px] text-muted-foreground mt-0.5 flex items-center gap-1">
            {teachersWithoutClasses > 0 ? (
              <span className="text-amber-600 dark:text-amber-400 font-medium">
                {teachersWithoutClasses} unassigned
              </span>
            ) : (
              <span className="text-emerald-600 dark:text-emerald-400 font-medium">
                All classes assigned
              </span>
            )}
          </p>
        </div>
      </div>

      {/* Community Mentors */}
      <div className="p-3.5 rounded-xl border bg-card shadow-2xs flex flex-col justify-between">
        <div className="flex items-center justify-between text-muted-foreground mb-1">
          <span className="text-xs font-medium">Mentors</span>
          <HeartHandshake className="h-4 w-4 text-indigo-600 dark:text-indigo-400" />
        </div>
        <div>
          <div className="text-2xl font-bold tracking-tight text-foreground">
            {loading ? "—" : mentors.length}
          </div>
          <p className="text-[11px] text-muted-foreground mt-0.5">
            Home visit officers
          </p>
        </div>
      </div>

      {/* Active Accounts */}
      <div className="p-3.5 rounded-xl border bg-card shadow-2xs flex flex-col justify-between">
        <div className="flex items-center justify-between text-muted-foreground mb-1">
          <span className="text-xs font-medium">Active Status</span>
          <CheckCircle2 className="h-4 w-4 text-emerald-600 dark:text-emerald-400" />
        </div>
        <div>
          <div className="text-2xl font-bold tracking-tight text-foreground">
            {loading ? "—" : `${activeCount}/${total}`}
          </div>
          <p className="text-[11px] text-muted-foreground mt-0.5">
            USSD dial enabled
          </p>
        </div>
      </div>
    </div>
  );
}
