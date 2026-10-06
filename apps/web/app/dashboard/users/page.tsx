"use client";

import { useEffect, useState } from "react";
import { useAuth } from "@/lib/auth-context";
import { createUser, fetchUsers, resetUserPin } from "@/lib/api/client";
import { Button } from "@/components/ui/button";
import { AccessibleModal } from "@/components/ui/modal";
import { ScopeHeader } from "@/components/scope-header";
import { Plus, RefreshCw, KeyRound, CheckCircle2, AlertTriangle } from "lucide-react";

interface UserItem {
  id: string;
  full_name: string;
  email?: string | null;
  phone_masked?: string | null;
  role: string;
  language: string;
  is_active: boolean;
}

export default function UsersPage() {
  const { user } = useAuth();
  const [users, setUsers] = useState<UserItem[]>([]);
  const [roleFilter, setRoleFilter] = useState<string>("");
  const [loading, setLoading] = useState(true);
  const [fetchError, setFetchError] = useState<string | null>(null);

  // Create User Modal
  const [isModalOpen, setIsModalOpen] = useState(false);
  const [fullName, setFullName] = useState("");
  const [email, setEmail] = useState("");
  const [phone, setPhone] = useState("");
  const [role, setRole] = useState("teacher");
  const [password, setPassword] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [createError, setCreateError] = useState<string | null>(null);

  // Pin Reset Modal
  const [pinResetTarget, setPinResetTarget] = useState<UserItem | null>(null);
  const [pinResetLoading, setPinResetLoading] = useState(false);

  // Notifications
  const [message, setMessage] = useState<string | null>(null);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);

  const loadUsers = (signal?: AbortSignal) => {
    setLoading(true);
    setFetchError(null);
    fetchUsers(roleFilter || undefined, signal)
      .then((data) => setUsers(data as UserItem[]))
      .catch((err) => {
        if (err.name !== "AbortError") {
          setFetchError(err.message || "Failed to load staff list");
        }
      })
      .finally(() => setLoading(false));
  };

  useEffect(() => {
    const controller = new AbortController();
    loadUsers(controller.signal);
    return () => controller.abort();
  }, [roleFilter]);

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

  const handleCreateUser = async (e: React.FormEvent) => {
    e.preventDefault();
    setSubmitting(true);
    setCreateError(null);
    try {
      await createUser({
        full_name: fullName,
        email: email || undefined,
        phone_e164: phone || undefined,
        role,
        password: password || undefined,
        school_id: user?.school_id || undefined,
        sector_id: user?.sector_id || undefined,
      });
      setIsModalOpen(false);
      setFullName("");
      setEmail("");
      setPhone("");
      setPassword("");
      loadUsers();
      setMessage("Staff member created successfully!");
      setTimeout(() => setMessage(null), 5000);
    } catch (err: unknown) {
      setCreateError(err instanceof Error ? err.message : "Creation failed");
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <div className="space-y-6 max-w-6xl">
      <ScopeHeader
        title="Staff & User Accounts"
        description="Manage teachers, community mentors, school administrators, and USSD credentials."
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
        <Button
          variant="outline"
          size="sm"
          onClick={() => loadUsers()}
          disabled={loading}
        >
          <RefreshCw className={`h-4 w-4 mr-1.5 ${loading ? "animate-spin" : ""}`} />
          Refresh
        </Button>
        <Button
          size="sm"
          onClick={() => {
            setIsModalOpen(true);
            setCreateError(null);
          }}
        >
          <Plus className="h-4 w-4 mr-1.5" />
          Add New Staff
        </Button>
      </ScopeHeader>

      {/* Notifications */}
      {message && (
        <div
          role="status"
          className="p-4 bg-emerald-500/15 border border-emerald-500/20 text-emerald-700 dark:text-emerald-400 rounded-lg flex items-center gap-2 text-sm font-medium"
        >
          <CheckCircle2 className="h-4 w-4 shrink-0" />
          <span>{message}</span>
        </div>
      )}

      {(errorMessage || fetchError) && (
        <div
          role="alert"
          className="p-4 bg-destructive/15 border border-destructive/20 text-destructive rounded-lg flex items-center justify-between"
        >
          <div className="flex items-center gap-2 text-sm font-medium">
            <AlertTriangle className="h-4 w-4 shrink-0" />
            <span>{errorMessage || fetchError}</span>
          </div>
          {fetchError && (
            <Button variant="outline" size="sm" onClick={() => loadUsers()}>
              Retry
            </Button>
          )}
        </div>
      )}

      {/* Filter Tabs */}
      <div className="flex flex-wrap items-center gap-2">
        {[
          { label: "All Roles", value: "" },
          { label: "Teachers", value: "teacher" },
          { label: "Mentors", value: "mentor" },
          { label: "Head Teachers", value: "head_teacher" },
          { label: "Sector Officers", value: "sector_officer" },
        ].map((tab) => (
          <Button
            key={tab.value}
            variant={roleFilter === tab.value ? "default" : "outline"}
            size="sm"
            onClick={() => setRoleFilter(tab.value)}
            className="text-xs h-8"
          >
            {tab.label}
          </Button>
        ))}
      </div>

      {/* Table */}
      <div className="border rounded-xl bg-card overflow-hidden shadow-xs">
        <div className="overflow-x-auto">
          <table className="w-full text-sm text-left">
            <thead className="bg-muted/50 border-b text-xs uppercase text-muted-foreground font-semibold">
              <tr>
                <th className="px-6 py-4">Full Name</th>
                <th className="px-6 py-4">Role</th>
                <th className="px-6 py-4">Phone (USSD)</th>
                <th className="px-6 py-4">Email</th>
                <th className="px-6 py-4">Status</th>
                <th className="px-6 py-4 text-right">Actions</th>
              </tr>
            </thead>
            <tbody className="divide-y">
              {loading ? (
                <tr>
                  <td colSpan={6} className="px-6 py-8 text-center text-muted-foreground animate-pulse">
                    Loading staff directory...
                  </td>
                </tr>
              ) : users.length === 0 ? (
                <tr>
                  <td colSpan={6} className="px-6 py-8 text-center text-muted-foreground">
                    No users found matching current filter.
                  </td>
                </tr>
              ) : (
                users.map((u) => (
                  <tr key={u.id} className="hover:bg-muted/20">
                    <td className="px-6 py-4 font-medium text-foreground">
                      {u.full_name}
                    </td>
                    <td className="px-6 py-4">
                      <span className="capitalize font-medium text-xs text-foreground bg-muted px-2 py-0.5 rounded">
                        {u.role.replace("_", " ")}
                      </span>
                    </td>
                    <td className="px-6 py-4 font-mono text-xs text-muted-foreground">
                      {u.phone_masked || "—"}
                    </td>
                    <td className="px-6 py-4 text-muted-foreground text-xs">
                      {u.email || "—"}
                    </td>
                    <td className="px-6 py-4">
                      <span
                        className={`inline-flex items-center px-2 py-0.5 rounded-full text-xs font-medium ${
                          u.is_active
                            ? "bg-emerald-500/10 text-emerald-600 dark:text-emerald-400"
                            : "bg-muted text-muted-foreground"
                        }`}
                      >
                        {u.is_active ? "Active" : "Disabled"}
                      </span>
                    </td>
                    <td className="px-6 py-4 text-right">
                      {["teacher", "mentor"].includes(u.role) && (
                        <Button
                          variant="outline"
                          size="sm"
                          onClick={() => setPinResetTarget(u)}
                          className="h-8 text-xs gap-1.5"
                        >
                          <KeyRound className="h-3 w-3" />
                          Reset PIN
                        </Button>
                      )}
                    </td>
                  </tr>
                ))
              )}
            </tbody>
          </table>
        </div>
      </div>

      {/* Accessible Create User Modal */}
      <AccessibleModal
        isOpen={isModalOpen}
        onClose={() => {
          setIsModalOpen(false);
          setCreateError(null);
        }}
        title="Register Staff Member"
        description="Provision teachers, mentors, or administrators with USSD / Dashboard access."
      >
        <form onSubmit={handleCreateUser} className="space-y-4">
          {createError && (
            <div
              role="alert"
              className="p-3 bg-destructive/15 border border-destructive/20 text-destructive rounded text-xs font-medium flex items-center gap-1.5"
            >
              <AlertTriangle className="h-4 w-4 shrink-0" />
              <span>{createError}</span>
            </div>
          )}

          <div className="space-y-1.5">
            <label htmlFor="user-full-name" className="text-xs font-semibold uppercase text-muted-foreground">
              Full Name
            </label>
            <input
              id="user-full-name"
              type="text"
              required
              value={fullName}
              onChange={(e) => setFullName(e.target.value)}
              placeholder="e.g. Jean Damascene"
              className="w-full px-3 py-2 border rounded-md text-sm bg-background focus:outline-hidden focus:ring-2 focus:ring-primary"
            />
          </div>

          <div className="space-y-1.5">
            <label htmlFor="user-role" className="text-xs font-semibold uppercase text-muted-foreground">
              Role
            </label>
            <select
              id="user-role"
              value={role}
              onChange={(e) => setRole(e.target.value)}
              className="w-full px-3 py-2 border rounded-md text-sm bg-background focus:outline-hidden focus:ring-2 focus:ring-primary"
            >
              <option value="teacher">Teacher (USSD Daily Attendance)</option>
              <option value="mentor">Community Mentor (USSD Home Visits)</option>
              {user?.role === "admin" && (
                <>
                  <option value="head_teacher">Head Teacher</option>
                  <option value="sector_officer">Sector Officer (SEO)</option>
                  <option value="district_director">District Director</option>
                  <option value="admin">National Administrator</option>
                </>
              )}
            </select>
          </div>

          <div className="space-y-1.5">
            <label htmlFor="user-phone" className="text-xs font-semibold uppercase text-muted-foreground">
              Phone Number (E.164: +2507XXXXXXXX for USSD)
            </label>
            <input
              id="user-phone"
              type="tel"
              value={phone}
              onChange={(e) => setPhone(e.target.value)}
              placeholder="+250788123456"
              className="w-full px-3 py-2 border rounded-md text-sm bg-background font-mono focus:outline-hidden focus:ring-2 focus:ring-primary"
            />
          </div>

          {["admin", "head_teacher", "sector_officer", "district_director"].includes(role) && (
            <>
              <div className="space-y-1.5">
                <label htmlFor="user-email" className="text-xs font-semibold uppercase text-muted-foreground">
                  Email
                </label>
                <input
                  id="user-email"
                  type="email"
                  value={email}
                  onChange={(e) => setEmail(e.target.value)}
                  placeholder="user@garuka.rw"
                  className="w-full px-3 py-2 border rounded-md text-sm bg-background focus:outline-hidden focus:ring-2 focus:ring-primary"
                />
              </div>

              <div className="space-y-1.5">
                <label htmlFor="user-password" className="text-xs font-semibold uppercase text-muted-foreground">
                  Dashboard Password
                </label>
                <input
                  id="user-password"
                  type="password"
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                  placeholder="••••••••••••"
                  className="w-full px-3 py-2 border rounded-md text-sm bg-background focus:outline-hidden focus:ring-2 focus:ring-primary"
                />
              </div>
            </>
          )}

          <p className="text-xs text-muted-foreground italic">
            * USSD PIN is set by the staff member upon their initial dial into the gateway.
          </p>

          <div className="flex justify-end gap-2 pt-3 border-t">
            <Button
              variant="outline"
              type="button"
              onClick={() => {
                setIsModalOpen(false);
                setCreateError(null);
              }}
            >
              Cancel
            </Button>
            <Button type="submit" disabled={submitting}>
              {submitting ? "Saving..." : "Create Staff Account"}
            </Button>
          </div>
        </form>
      </AccessibleModal>

      {/* Accessible Reset PIN Confirmation Dialog */}
      <AccessibleModal
        isOpen={!!pinResetTarget}
        onClose={() => setPinResetTarget(null)}
        title="Confirm USSD PIN Reset"
        description="Reset credentials for mobile dialer."
        maxWidth="sm"
      >
        <div className="space-y-4">
          <p className="text-sm text-foreground">
            Are you sure you want to reset the USSD PIN for{" "}
            <span className="font-semibold">{pinResetTarget?.full_name}</span>?
          </p>
          <p className="text-xs text-muted-foreground">
            Their existing PIN will be cleared. On their next USSD dial, they will be prompted to choose a new 4-digit PIN.
          </p>

          <div className="flex justify-end gap-2 pt-2 border-t">
            <Button
              variant="outline"
              size="sm"
              onClick={() => setPinResetTarget(null)}
              disabled={pinResetLoading}
            >
              Cancel
            </Button>
            <Button
              variant="destructive"
              size="sm"
              onClick={handleConfirmResetPin}
              disabled={pinResetLoading}
            >
              {pinResetLoading ? "Resetting..." : "Reset PIN"}
            </Button>
          </div>
        </div>
      </AccessibleModal>
    </div>
  );
}
