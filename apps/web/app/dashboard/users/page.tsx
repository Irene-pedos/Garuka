"use client";

import { useEffect, useState } from "react";
import { useAuth } from "@/lib/auth-context";
import { createUser, fetchUsers, resetUserPin } from "@/lib/api/client";
import { Button } from "@/components/ui/button";

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

  // Create User Modal
  const [isModalOpen, setIsModalOpen] = useState(false);
  const [fullName, setFullName] = useState("");
  const [email, setEmail] = useState("");
  const [phone, setPhone] = useState("");
  const [role, setRole] = useState("teacher");
  const [password, setPassword] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [message, setMessage] = useState<string | null>(null);

  const loadUsers = () => {
    setLoading(true);
    fetchUsers(roleFilter || undefined)
      .then((data) => setUsers(data as UserItem[]))
      .catch((err) => console.error(err))
      .finally(() => setLoading(false));
  };

  useEffect(() => {
    loadUsers();
  }, [roleFilter]);

  const handleResetPin = async (userId: string, name: string) => {
    if (!confirm(`Reset PIN for ${name}? They will configure a new PIN on next USSD dial.`)) {
      return;
    }
    try {
      const res = await resetUserPin(userId);
      setMessage(res.message);
      setTimeout(() => setMessage(null), 4000);
    } catch (err: unknown) {
      alert(err instanceof Error ? err.message : "Failed to reset PIN");
    }
  };

  const handleCreateUser = async (e: React.FormEvent) => {
    e.preventDefault();
    setSubmitting(true);
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
      setTimeout(() => setMessage(null), 4000);
    } catch (err: unknown) {
      alert(err instanceof Error ? err.message : "Creation failed");
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <div className="space-y-6 max-w-6xl">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold tracking-tight">Staff & Users</h1>
          <p className="text-sm text-muted-foreground">Manage teachers, mentors, administrators, and USSD credentials</p>
        </div>
        <Button onClick={() => setIsModalOpen(true)}>Add New Staff</Button>
      </div>

      {message && (
        <div className="p-3 bg-emerald-100 text-emerald-900 border border-emerald-300 rounded-lg text-xs font-semibold">
          {message}
        </div>
      )}

      <div className="flex items-center gap-4">
        <select
          value={roleFilter}
          onChange={(e) => setRoleFilter(e.target.value)}
          aria-label="Filter by role"
          className="px-3 py-2 border rounded-md text-sm bg-background focus:outline-none focus:ring-2 focus:ring-primary"
        >
          <option value="">All Roles</option>
          <option value="teacher">Teachers</option>
          <option value="mentor">Mentors</option>
          <option value="head_teacher">Head Teachers</option>
          <option value="sector_officer">Sector Officers</option>
          <option value="district_director">District Directors</option>
          <option value="admin">Administrators</option>
        </select>
      </div>

      <div className="border rounded-xl bg-card overflow-hidden shadow-sm">
        <div className="overflow-x-auto">
          <table className="w-full text-sm text-left">
            <thead className="bg-muted text-muted-foreground uppercase text-xs border-b">
              <tr>
                <th className="px-4 py-3">Full Name</th>
                <th className="px-4 py-3">Role</th>
                <th className="px-4 py-3">Phone (USSD)</th>
                <th className="px-4 py-3">Email</th>
                <th className="px-4 py-3">Language</th>
                <th className="px-4 py-3">Status</th>
                <th className="px-4 py-3 text-right">Actions</th>
              </tr>
            </thead>
            <tbody className="divide-y">
              {loading ? (
                <tr>
                  <td colSpan={7} className="text-center py-8 text-muted-foreground">
                    Loading users...
                  </td>
                </tr>
              ) : (
                users.map((u) => (
                  <tr key={u.id} className="hover:bg-muted/30">
                    <td className="px-4 py-3 font-semibold text-foreground">{u.full_name}</td>
                    <td className="px-4 py-3">
                      <span className="inline-flex items-center px-2 py-0.5 rounded-full text-xs font-medium bg-primary/10 text-primary capitalize">
                        {u.role.replace("_", " ")}
                      </span>
                    </td>
                    <td className="px-4 py-3 font-mono text-xs text-muted-foreground">
                      {u.phone_masked || "—"}
                    </td>
                    <td className="px-4 py-3 text-muted-foreground">{u.email || "—"}</td>
                    <td className="px-4 py-3 uppercase text-xs font-semibold">{u.language}</td>
                    <td className="px-4 py-3">
                      <span
                        className={`inline-flex items-center px-2 py-0.5 rounded-full text-xs font-medium ${
                          u.is_active
                            ? "bg-emerald-100 text-emerald-800 dark:bg-emerald-950 dark:text-emerald-300"
                            : "bg-muted text-muted-foreground"
                        }`}
                      >
                        {u.is_active ? "Active" : "Inactive"}
                      </span>
                    </td>
                    <td className="px-4 py-3 text-right">
                      {["teacher", "mentor", "head_teacher"].includes(u.role) && (
                        <Button
                          variant="outline"
                          size="sm"
                          onClick={() => handleResetPin(u.id, u.full_name)}
                        >
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

      {/* Create User Modal */}
      {isModalOpen && (
        <div className="fixed inset-0 z-50 bg-black/50 flex items-center justify-center p-4">
          <div className="bg-card border rounded-xl max-w-md w-full p-6 shadow-xl space-y-4">
            <div className="flex items-center justify-between border-b pb-3">
              <h2 className="font-bold text-lg">Add New Staff / User</h2>
              <button
                onClick={() => setIsModalOpen(false)}
                className="text-muted-foreground hover:text-foreground text-sm"
              >
                ✕
              </button>
            </div>

            <form onSubmit={handleCreateUser} className="space-y-3">
              <div className="space-y-1">
                <label className="text-xs font-semibold uppercase text-muted-foreground">Full Name</label>
                <input
                  type="text"
                  required
                  value={fullName}
                  onChange={(e) => setFullName(e.target.value)}
                  placeholder="Teacher Mugabo"
                  className="w-full px-3 py-2 border rounded-md text-sm bg-background"
                />
              </div>

              <div className="space-y-1">
                <label className="text-xs font-semibold uppercase text-muted-foreground">Role</label>
                <select
                  value={role}
                  onChange={(e) => setRole(e.target.value)}
                  className="w-full px-3 py-2 border rounded-md text-sm bg-background"
                >
                  <option value="teacher">Teacher (USSD Attendance)</option>
                  <option value="mentor">Mentor (USSD Home Visits)</option>
                  {user?.role === "admin" && (
                    <>
                      <option value="head_teacher">Head Teacher</option>
                      <option value="sector_officer">Sector Officer</option>
                      <option value="district_director">District Director</option>
                      <option value="admin">Administrator</option>
                    </>
                  )}
                </select>
              </div>

              <div className="space-y-1">
                <label className="text-xs font-semibold uppercase text-muted-foreground">
                  Phone (+2507XXXXXXXX for USSD)
                </label>
                <input
                  type="text"
                  value={phone}
                  onChange={(e) => setPhone(e.target.value)}
                  placeholder="+250780000005"
                  className="w-full px-3 py-2 border rounded-md text-sm bg-background font-mono"
                />
              </div>

              {["admin", "head_teacher", "sector_officer", "district_director"].includes(role) && (
                <>
                  <div className="space-y-1">
                    <label className="text-xs font-semibold uppercase text-muted-foreground">Email</label>
                    <input
                      type="email"
                      value={email}
                      onChange={(e) => setEmail(e.target.value)}
                      placeholder="user@school.rw"
                      className="w-full px-3 py-2 border rounded-md text-sm bg-background"
                    />
                  </div>
                  <div className="space-y-1">
                    <label className="text-xs font-semibold uppercase text-muted-foreground">
                      Dashboard Password
                    </label>
                    <input
                      type="password"
                      value={password}
                      onChange={(e) => setPassword(e.target.value)}
                      placeholder="••••••••••••"
                      className="w-full px-3 py-2 border rounded-md text-sm bg-background"
                    />
                  </div>
                </>
              )}

              <p className="text-xs text-muted-foreground italic">
                * USSD PIN is set by the staff member upon their first dial into the gateway.
              </p>

              <div className="flex justify-end gap-2 pt-3 border-t">
                <Button variant="outline" type="button" onClick={() => setIsModalOpen(false)}>
                  Cancel
                </Button>
                <Button type="submit" disabled={submitting}>
                  {submitting ? "Saving..." : "Create User"}
                </Button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  );
}
