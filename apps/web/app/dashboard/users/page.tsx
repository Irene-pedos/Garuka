"use client";

import { useEffect, useState, useMemo, useCallback } from "react";
import { useAuth } from "@/lib/auth-context";
import { fetchUsers, resetUserPin, UserItem } from "@/lib/api/client";
import { Button } from "@/components/ui/button";
import { ScopeHeader } from "@/components/scope-header";
import { StaffStats } from "./components/staff-stats";
import { StaffTable } from "./components/staff-table";
import { RegisterStaffModal } from "./components/register-staff-modal";
import { EditStaffModal } from "./components/edit-staff-modal";
import { ResetPinModal } from "./components/reset-pin-modal";
import {
  Plus,
  RefreshCw,
  Search,
  CheckCircle2,
  AlertTriangle,
  X,
} from "lucide-react";

export default function UsersPage() {
  const { user } = useAuth();
  const [users, setUsers] = useState<UserItem[]>([]);
  const [roleFilter, setRoleFilter] = useState<string>("");
  const [search, setSearch] = useState<string>("");
  const [statusFilter, setStatusFilter] = useState<"all" | "active" | "disabled">("all");
  const [loading, setLoading] = useState(true);
  const [fetchError, setFetchError] = useState<string | null>(null);

  // Modals state
  const [isRegisterModalOpen, setIsRegisterModalOpen] = useState(false);
  const [editingUser, setEditingUser] = useState<UserItem | null>(null);
  const [pinResetTarget, setPinResetTarget] = useState<UserItem | null>(null);
  const [pinResetLoading, setPinResetLoading] = useState(false);

  // Notification banners
  const [message, setMessage] = useState<string | null>(null);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);

  const loadUsers = useCallback((signal?: AbortSignal) => {
    setLoading(true);
    setFetchError(null);
    fetchUsers(roleFilter || undefined, signal)
      .then((data) => setUsers(data))
      .catch((err) => {
        if (err.name !== "AbortError") {
          setFetchError(err.message || "Failed to load staff list");
        }
      })
      .finally(() => setLoading(false));
  }, [roleFilter]);

  useEffect(() => {
    const controller = new AbortController();
    loadUsers(controller.signal);
    return () => controller.abort();
  }, [loadUsers]);

  const handleConfirmResetPin = async () => {
    if (!pinResetTarget) return;
    setPinResetLoading(true);
    setErrorMessage(null);
    try {
      const res = await resetUserPin(pinResetTarget.id);
      setMessage(res.message);
      setPinResetTarget(null);
      setTimeout(() => setMessage(null), 5000);
    } catch (err: unknown) {
      setErrorMessage(err instanceof Error ? err.message : "Failed to reset PIN");
    } finally {
      setPinResetLoading(false);
    }
  };

  const handleStaffRegistered = (newUser: UserItem) => {
    setMessage(`Staff member "${newUser.full_name}" registered successfully.`);
    setTimeout(() => setMessage(null), 5000);
    loadUsers();
  };

  const handleStaffUpdated = (updatedUser: UserItem) => {
    setMessage(`Staff member "${updatedUser.full_name}" updated successfully.`);
    setTimeout(() => setMessage(null), 5000);
    setUsers((prev) =>
      prev.map((u) => (u.id === updatedUser.id ? updatedUser : u))
    );
  };

  // Filtered staff list based on search and status
  const filteredUsers = useMemo(() => {
    return users.filter((u) => {
      // Status filter
      if (statusFilter === "active" && !u.is_active) return false;
      if (statusFilter === "disabled" && u.is_active) return false;

      // Search filter
      if (!search.trim()) return true;
      const query = search.toLowerCase().trim();
      const nameMatch = u.full_name?.toLowerCase().includes(query);
      const emailMatch = u.email?.toLowerCase().includes(query);
      const phoneMatch =
        (u.phone_masked && u.phone_masked.toLowerCase().includes(query)) ||
        (u.phone_e164 && u.phone_e164.toLowerCase().includes(query));
      const classMatch = u.assigned_classes?.some((c) =>
        c.name.toLowerCase().includes(query)
      );

      return nameMatch || emailMatch || phoneMatch || classMatch;
    });
  }, [users, search, statusFilter]);

  return (
    <div className="w-full space-y-6">
      {/* Header with Scope & Actions */}
      <ScopeHeader
        title="Staff & User Accounts"
        description="Manage teachers, community mentors, school administrators, and USSD attendance credentials."
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
        <div className="flex flex-wrap items-center gap-2 w-full sm:w-auto">
          <Button
            variant="outline"
            size="sm"
            onClick={() => loadUsers()}
            disabled={loading}
            className="flex-1 sm:flex-initial"
          >
            <RefreshCw className={`h-4 w-4 mr-1.5 ${loading ? "animate-spin" : ""}`} />
            Refresh
          </Button>
          <Button
            size="sm"
            onClick={() => setIsRegisterModalOpen(true)}
            className="flex-1 sm:flex-initial"
          >
            <Plus className="h-4 w-4 mr-1.5" />
            Add New Staff
          </Button>
        </div>
      </ScopeHeader>

      {/* Notifications */}
      {message && (
        <div
          role="status"
          className="p-3.5 bg-emerald-500/15 border border-emerald-500/20 text-emerald-800 dark:text-emerald-300 rounded-lg flex items-center justify-between text-xs font-medium"
        >
          <div className="flex items-center gap-2">
            <CheckCircle2 className="h-4 w-4 shrink-0 text-emerald-600 dark:text-emerald-400" />
            <span>{message}</span>
          </div>
          <button
            type="button"
            onClick={() => setMessage(null)}
            className="text-emerald-600 hover:text-emerald-800 dark:hover:text-emerald-200"
          >
            <X className="h-4 w-4" />
          </button>
        </div>
      )}

      {(errorMessage || fetchError) && (
        <div
          role="alert"
          className="p-3.5 bg-destructive/15 border border-destructive/20 text-destructive rounded-lg flex items-center justify-between text-xs font-medium"
        >
          <div className="flex items-center gap-2">
            <AlertTriangle className="h-4 w-4 shrink-0" />
            <span>{errorMessage || fetchError}</span>
          </div>
          {fetchError && (
            <Button variant="outline" size="sm" onClick={() => loadUsers()} className="h-7 text-xs">
              Retry
            </Button>
          )}
        </div>
      )}

      {/* Stats KPI Cards */}
      <StaffStats users={users} loading={loading} />

      {/* Filter and Search Bar */}
      <div className="flex flex-col sm:flex-row items-stretch sm:items-center justify-between gap-3 pt-1 w-full">
        {/* Search Input */}
        <div className="relative flex-1 w-full sm:max-w-md lg:max-w-lg xl:max-w-xl">
          <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-3.5 w-3.5 text-muted-foreground" />
          <input
            type="text"
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            placeholder="Search by name, phone, email, or class..."
            className="w-full pl-8.5 pr-8 py-1.5 text-xs rounded-lg border bg-card text-foreground placeholder:text-muted-foreground focus:outline-hidden focus:ring-2 focus:ring-primary h-9"
          />
          {search && (
            <button
              type="button"
              onClick={() => setSearch("")}
              className="absolute right-2.5 top-1/2 -translate-y-1/2 text-muted-foreground hover:text-foreground p-0.5"
            >
              <X className="h-3.5 w-3.5" />
            </button>
          )}
        </div>

        {/* Status Filter Toggle */}
        <div className="flex items-center gap-1.5 self-start sm:self-auto overflow-x-auto py-0.5">
          <span className="text-xs text-muted-foreground font-medium hidden md:inline">
            Status:
          </span>
          {(["all", "active", "disabled"] as const).map((st) => (
            <Button
              key={st}
              variant={statusFilter === st ? "secondary" : "ghost"}
              size="sm"
              onClick={() => setStatusFilter(st)}
              className="text-xs h-8 capitalize px-2.5"
            >
              {st}
            </Button>
          ))}
        </div>
      </div>

      {/* Role Filter Tabs (Scrollable on mobile) */}
      <div className="flex items-center gap-1.5 overflow-x-auto pb-1.5 sm:pb-0 sm:flex-wrap no-scrollbar w-full">
        {[
          { label: "All Roles", value: "" },
          { label: "Teachers", value: "teacher" },
          { label: "Community Mentors", value: "mentor" },
          { label: "Head Teachers", value: "head_teacher" },
          ...(user?.role === "admin"
            ? [
                { label: "Sector Officers", value: "sector_officer" },
                { label: "District Directors", value: "district_director" },
              ]
            : []),
        ].map((tab) => (
          <Button
            key={tab.value}
            variant={roleFilter === tab.value ? "default" : "outline"}
            size="sm"
            onClick={() => setRoleFilter(tab.value)}
            className="text-xs h-8 shrink-0"
          >
            {tab.label}
          </Button>
        ))}
      </div>

      {/* Staff Directory Table */}
      <StaffTable
        users={filteredUsers}
        loading={loading}
        onEditUser={(u) => setEditingUser(u)}
        onResetPin={(u) => setPinResetTarget(u)}
        onOpenRegisterModal={() => setIsRegisterModalOpen(true)}
      />

      {/* Register Staff Modal */}
      <RegisterStaffModal
        isOpen={isRegisterModalOpen}
        onClose={() => setIsRegisterModalOpen(false)}
        onSuccess={handleStaffRegistered}
        currentUserRole={user?.role}
        schoolId={user?.school_id || undefined}
      />

      {/* Edit Staff Modal */}
      <EditStaffModal
        user={editingUser}
        isOpen={!!editingUser}
        onClose={() => setEditingUser(null)}
        onSuccess={handleStaffUpdated}
        schoolId={user?.school_id || undefined}
      />

      {/* Reset USSD PIN Modal */}
      <ResetPinModal
        user={pinResetTarget}
        isOpen={!!pinResetTarget}
        onClose={() => setPinResetTarget(null)}
        onConfirm={handleConfirmResetPin}
        loading={pinResetLoading}
      />
    </div>
  );
}
