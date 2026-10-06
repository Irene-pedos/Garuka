"use client";

import { UserItem } from "@/lib/api/client";
import { Button } from "@/components/ui/button";
import {
  KeyRound,
  Pencil,
  GraduationCap,
  HeartHandshake,
  Shield,
  School,
  AlertCircle,
  Plus,
  Smartphone,
  Mail,
} from "lucide-react";

interface StaffTableProps {
  users: UserItem[];
  loading: boolean;
  onEditUser: (user: UserItem) => void;
  onResetPin: (user: UserItem) => void;
  onOpenRegisterModal: () => void;
}

export function StaffTable({
  users,
  loading,
  onEditUser,
  onResetPin,
  onOpenRegisterModal,
}: StaffTableProps) {
  const getInitials = (name: string) => {
    if (!name) return "U";
    const parts = name.trim().split(/\s+/);
    if (parts.length === 1) return parts[0].slice(0, 2).toUpperCase();
    return (parts[0][0] + parts[parts.length - 1][0]).toUpperCase();
  };

  const getRoleBadge = (role: string) => {
    switch (role) {
      case "teacher":
        return {
          label: "Teacher",
          icon: GraduationCap,
          className: "bg-emerald-500/10 text-emerald-700 dark:text-emerald-400 border-emerald-500/20",
        };
      case "mentor":
        return {
          label: "Community Mentor",
          icon: HeartHandshake,
          className: "bg-indigo-500/10 text-indigo-700 dark:text-indigo-400 border-indigo-500/20",
        };
      case "head_teacher":
        return {
          label: "Head Teacher",
          icon: School,
          className: "bg-amber-500/10 text-amber-700 dark:text-amber-400 border-amber-500/20",
        };
      case "sector_officer":
        return {
          label: "Sector Officer (SEO)",
          icon: Shield,
          className: "bg-blue-500/10 text-blue-700 dark:text-blue-400 border-blue-500/20",
        };
      case "district_director":
        return {
          label: "District Director",
          icon: Shield,
          className: "bg-purple-500/10 text-purple-700 dark:text-purple-400 border-purple-500/20",
        };
      case "admin":
        return {
          label: "Administrator",
          icon: Shield,
          className: "bg-rose-500/10 text-rose-700 dark:text-rose-400 border-rose-500/20",
        };
      default:
        return {
          label: role.replace("_", " "),
          icon: Shield,
          className: "bg-muted text-foreground border-border",
        };
    }
  };

  // Empty State Render
  if (!loading && users.length === 0) {
    return (
      <div className="w-full border rounded-xl bg-card p-8 sm:p-12 text-center shadow-2xs">
        <div className="max-w-sm mx-auto space-y-3">
          <div className="w-10 h-10 rounded-full bg-muted flex items-center justify-center mx-auto text-muted-foreground">
            <AlertCircle className="h-5 w-5" />
          </div>
          <div>
            <h3 className="text-sm font-semibold text-foreground">
              No staff members found
            </h3>
            <p className="text-xs text-muted-foreground mt-1">
              Try adjusting your search query or role filter, or add a new staff member to this school.
            </p>
          </div>
          <Button size="sm" onClick={onOpenRegisterModal} className="h-8 text-xs">
            <Plus className="h-3.5 w-3.5 mr-1" />
            Register New Staff
          </Button>
        </div>
      </div>
    );
  }

  return (
    <div className="w-full space-y-4">
      {/* ------------------------------------------------------------- */}
      {/* MOBILE CARDS VIEW (Visible on < 768px screens)               */}
      {/* ------------------------------------------------------------- */}
      <div className="block md:hidden space-y-3">
        {loading
          ? Array.from({ length: 3 }).map((_, idx) => (
              <div
                key={idx}
                className="p-4 rounded-xl border bg-card shadow-2xs space-y-3 animate-pulse"
              >
                <div className="flex items-center gap-3">
                  <div className="w-9 h-9 rounded-full bg-muted shrink-0" />
                  <div className="flex-1 space-y-1.5">
                    <div className="h-3.5 w-32 bg-muted rounded" />
                    <div className="h-2.5 w-20 bg-muted/60 rounded" />
                  </div>
                </div>
                <div className="h-5 w-24 bg-muted rounded" />
                <div className="h-8 w-full bg-muted rounded" />
              </div>
            ))
          : users.map((u) => {
              const roleInfo = getRoleBadge(u.role);
              const RoleIcon = roleInfo.icon;
              const assignedClasses = u.assigned_classes || [];

              return (
                <div
                  key={u.id}
                  className="p-4 rounded-xl border bg-card shadow-2xs space-y-3 transition-colors hover:border-border/80"
                >
                  {/* Card Header: Avatar + Name + Status */}
                  <div className="flex items-start justify-between gap-2">
                    <div className="flex items-center gap-3 min-w-0">
                      <div className="h-9 w-9 rounded-full bg-primary/10 text-primary flex items-center justify-center font-bold text-xs shrink-0 select-none">
                        {getInitials(u.full_name)}
                      </div>
                      <div className="min-w-0">
                        <span className="font-semibold text-foreground text-sm block truncate">
                          {u.full_name}
                        </span>
                        <div className="flex items-center gap-2 mt-0.5">
                          <span
                            className={`inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-[10px] font-medium border ${roleInfo.className}`}
                          >
                            <RoleIcon className="h-2.5 w-2.5" />
                            <span>{roleInfo.label}</span>
                          </span>
                          <span
                            className={`inline-flex items-center px-1.5 py-0.2 text-[10px] rounded-full font-medium ${
                              u.is_active
                                ? "bg-emerald-500/10 text-emerald-600 dark:text-emerald-400"
                                : "bg-muted text-muted-foreground"
                            }`}
                          >
                            <span
                              className={`w-1 h-1 rounded-full mr-1 ${
                                u.is_active ? "bg-emerald-500" : "bg-muted-foreground/60"
                              }`}
                            />
                            {u.is_active ? "Active" : "Disabled"}
                          </span>
                        </div>
                      </div>
                    </div>
                  </div>

                  {/* Assigned Classes for Teachers */}
                  {u.role === "teacher" && (
                    <div className="pt-1 text-xs">
                      <span className="text-[11px] text-muted-foreground block mb-1 font-medium">
                        Class Assignment:
                      </span>
                      {assignedClasses.length > 0 ? (
                        <div className="flex flex-wrap gap-1.5">
                          {assignedClasses.map((ac) => (
                            <span
                              key={ac.id}
                              className="inline-flex items-center gap-1 px-2 py-0.5 rounded-md bg-emerald-500/10 text-emerald-800 dark:text-emerald-300 text-xs font-medium border border-emerald-500/20"
                            >
                              <GraduationCap className="h-3 w-3 text-emerald-600 dark:text-emerald-400" />
                              <span>{ac.name}</span>
                            </span>
                          ))}
                        </div>
                      ) : (
                        <div className="flex items-center gap-2">
                          <span className="inline-flex items-center px-2 py-0.5 rounded text-[11px] font-medium bg-amber-500/15 text-amber-700 dark:text-amber-400 border border-amber-500/20">
                            No Class Assigned
                          </span>
                          <button
                            type="button"
                            onClick={() => onEditUser(u)}
                            className="text-xs text-primary font-medium underline"
                          >
                            Assign Class
                          </button>
                        </div>
                      )}
                    </div>
                  )}

                  {/* Contact Info (Phone & Email) */}
                  <div className="grid grid-cols-1 gap-1 pt-1 text-xs text-muted-foreground border-t border-border/40">
                    <div className="flex items-center gap-2 font-mono text-[11px] text-foreground">
                      <Smartphone className="h-3.5 w-3.5 text-muted-foreground shrink-0" />
                      <span>{u.phone_masked || u.phone_e164 || "No phone registered"}</span>
                    </div>
                    {u.email && (
                      <div className="flex items-center gap-2 text-[11px] truncate">
                        <Mail className="h-3.5 w-3.5 text-muted-foreground shrink-0" />
                        <span className="truncate">{u.email}</span>
                      </div>
                    )}
                  </div>

                  {/* Card Actions */}
                  <div className="flex items-center justify-end gap-2 pt-2 border-t border-border/40">
                    <Button
                      variant="outline"
                      size="sm"
                      onClick={() => onEditUser(u)}
                      className="h-7 text-xs flex-1 gap-1"
                    >
                      <Pencil className="h-3 w-3" />
                      <span>Edit Staff</span>
                    </Button>
                    {["teacher", "mentor"].includes(u.role) && (
                      <Button
                        variant="outline"
                        size="sm"
                        onClick={() => onResetPin(u)}
                        className="h-7 text-xs flex-1 gap-1 text-amber-600 dark:text-amber-400 hover:border-amber-500/50"
                      >
                        <KeyRound className="h-3 w-3" />
                        <span>Reset PIN</span>
                      </Button>
                    )}
                  </div>
                </div>
              );
            })}
      </div>

      {/* ------------------------------------------------------------- */}
      {/* DESKTOP & TABLET TABLE VIEW (Visible on >= 768px screens)    */}
      {/* ------------------------------------------------------------- */}
      <div className="hidden md:block w-full border rounded-xl bg-card overflow-hidden shadow-2xs">
        <div className="w-full overflow-x-auto">
          <table className="w-full text-sm text-left">
            <thead className="bg-muted/40 border-b text-[11px] uppercase tracking-wider text-muted-foreground font-semibold">
              <tr>
                <th className="px-5 py-3.5">Staff Member</th>
                <th className="px-5 py-3.5">Role</th>
                <th className="px-5 py-3.5">Assigned Class</th>
                <th className="px-5 py-3.5">Phone (USSD)</th>
                <th className="px-5 py-3.5">Email</th>
                <th className="px-5 py-3.5">Status</th>
                <th className="px-5 py-3.5 text-right">Actions</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-border/60">
              {loading
                ? Array.from({ length: 4 }).map((_, idx) => (
                    <tr key={idx} className="animate-pulse">
                      <td className="px-5 py-4">
                        <div className="flex items-center gap-3">
                          <div className="w-8 h-8 rounded-full bg-muted" />
                          <div className="space-y-1.5">
                            <div className="h-3.5 w-32 bg-muted rounded" />
                            <div className="h-2.5 w-16 bg-muted/60 rounded" />
                          </div>
                        </div>
                      </td>
                      <td className="px-5 py-4">
                        <div className="h-5 w-20 bg-muted rounded-full" />
                      </td>
                      <td className="px-5 py-4">
                        <div className="h-5 w-24 bg-muted rounded" />
                      </td>
                      <td className="px-5 py-4">
                        <div className="h-3.5 w-28 bg-muted rounded font-mono" />
                      </td>
                      <td className="px-5 py-4">
                        <div className="h-3.5 w-24 bg-muted rounded" />
                      </td>
                      <td className="px-5 py-4">
                        <div className="h-4 w-14 bg-muted rounded-full" />
                      </td>
                      <td className="px-5 py-4 text-right">
                        <div className="h-8 w-20 bg-muted rounded ml-auto" />
                      </td>
                    </tr>
                  ))
                : users.map((u) => {
                    const roleInfo = getRoleBadge(u.role);
                    const RoleIcon = roleInfo.icon;
                    const assignedClasses = u.assigned_classes || [];

                    return (
                      <tr key={u.id} className="hover:bg-muted/20 transition-colors">
                        {/* Staff Member */}
                        <td className="px-5 py-3.5">
                          <div className="flex items-center gap-3">
                            <div className="h-8 w-8 rounded-full bg-primary/10 text-primary flex items-center justify-center font-bold text-xs shrink-0 select-none">
                              {getInitials(u.full_name)}
                            </div>
                            <div>
                              <span className="font-medium text-foreground block">
                                {u.full_name}
                              </span>
                              <span className="text-[11px] text-muted-foreground uppercase tracking-wider">
                                Lang: {u.language.toUpperCase()}
                              </span>
                            </div>
                          </div>
                        </td>

                        {/* Role */}
                        <td className="px-5 py-3.5">
                          <span
                            className={`inline-flex items-center gap-1.5 px-2.5 py-0.5 rounded-full text-xs font-medium border ${roleInfo.className}`}
                          >
                            <RoleIcon className="h-3 w-3" />
                            <span>{roleInfo.label}</span>
                          </span>
                        </td>

                        {/* Assigned Class */}
                        <td className="px-5 py-3.5">
                          {u.role === "teacher" ? (
                            assignedClasses.length > 0 ? (
                              <div className="flex flex-wrap gap-1.5">
                                {assignedClasses.map((ac) => (
                                  <span
                                    key={ac.id}
                                    className="inline-flex items-center gap-1 px-2 py-0.5 rounded-md bg-emerald-500/10 text-emerald-800 dark:text-emerald-300 text-xs font-medium border border-emerald-500/20"
                                  >
                                    <GraduationCap className="h-3 w-3 text-emerald-600 dark:text-emerald-400" />
                                    <span>{ac.name}</span>
                                  </span>
                                ))}
                              </div>
                            ) : (
                              <div className="flex items-center gap-2">
                                <span className="inline-flex items-center px-2 py-0.5 rounded text-[11px] font-medium bg-amber-500/15 text-amber-700 dark:text-amber-400 border border-amber-500/20">
                                  Unassigned
                                </span>
                                <button
                                  type="button"
                                  onClick={() => onEditUser(u)}
                                  className="text-xs text-primary hover:underline font-medium cursor-pointer"
                                >
                                  Assign
                                </button>
                              </div>
                            )
                          ) : u.role === "mentor" ? (
                            <span className="text-xs text-muted-foreground italic">
                              Sector Mentorship
                            </span>
                          ) : (
                            <span className="text-xs text-muted-foreground">—</span>
                          )}
                        </td>

                        {/* Phone (USSD) */}
                        <td className="px-5 py-3.5">
                          {u.phone_masked || u.phone_e164 ? (
                            <span className="font-mono text-xs text-foreground bg-muted/40 px-1.5 py-0.5 rounded">
                              {u.phone_masked || u.phone_e164}
                            </span>
                          ) : (
                            <span className="text-xs text-muted-foreground italic">
                              No phone
                            </span>
                          )}
                        </td>

                        {/* Email */}
                        <td className="px-5 py-3.5">
                          {u.email ? (
                            <span className="text-xs text-muted-foreground truncate max-w-[180px] block">
                              {u.email}
                            </span>
                          ) : (
                            <span className="text-xs text-muted-foreground italic">—</span>
                          )}
                        </td>

                        {/* Status */}
                        <td className="px-5 py-3.5">
                          <span
                            className={`inline-flex items-center px-2 py-0.5 rounded-full text-xs font-medium ${
                              u.is_active
                                ? "bg-emerald-500/10 text-emerald-600 dark:text-emerald-400"
                                : "bg-muted text-muted-foreground"
                            }`}
                          >
                            <span
                              className={`w-1.5 h-1.5 rounded-full mr-1.5 ${
                                u.is_active ? "bg-emerald-500" : "bg-muted-foreground/60"
                              }`}
                            />
                            {u.is_active ? "Active" : "Disabled"}
                          </span>
                        </td>

                        {/* Actions */}
                        <td className="px-5 py-3.5 text-right">
                          <div className="flex items-center justify-end gap-1.5">
                            <Button
                              variant="ghost"
                              size="sm"
                              onClick={() => onEditUser(u)}
                              className="h-8 px-2 text-xs gap-1 text-muted-foreground hover:text-foreground"
                              title="Edit details and assigned class"
                            >
                              <Pencil className="h-3.5 w-3.5" />
                              <span className="hidden lg:inline">Edit</span>
                            </Button>

                            {["teacher", "mentor"].includes(u.role) && (
                              <Button
                                variant="outline"
                                size="sm"
                                onClick={() => onResetPin(u)}
                                className="h-8 px-2 text-xs gap-1 text-muted-foreground hover:text-foreground hover:border-amber-500/50"
                                title="Reset USSD PIN"
                              >
                                <KeyRound className="h-3.5 w-3.5 text-amber-600 dark:text-amber-400" />
                                <span className="hidden lg:inline">Reset PIN</span>
                              </Button>
                            )}
                          </div>
                        </td>
                      </tr>
                    );
                  })}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
}
