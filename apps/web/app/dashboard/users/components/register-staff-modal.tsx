"use client";

import { useEffect, useState } from "react";
import { AccessibleModal } from "@/components/ui/modal";
import { Button } from "@/components/ui/button";
import { createUser, fetchSchoolClasses, UserItem } from "@/lib/api/client";
import { validateRwandaPhone } from "../lib/phone-utils";
import {
  AlertTriangle,
  GraduationCap,
  ShieldCheck,
  Smartphone,
  CheckCircle2,
  BookOpen,
} from "lucide-react";

interface SchoolClassOption {
  id: string;
  name: string;
  grade: number;
}

interface RegisterStaffModalProps {
  isOpen: boolean;
  onClose: () => void;
  onSuccess: (newUser: UserItem) => void;
  currentUserRole?: string;
  schoolId?: string;
}

export function RegisterStaffModal({
  isOpen,
  onClose,
  onSuccess,
  currentUserRole = "head_teacher",
  schoolId,
}: RegisterStaffModalProps) {
  const [fullName, setFullName] = useState("");
  const [role, setRole] = useState("teacher");
  const [phone, setPhone] = useState("");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [selectedClassIds, setSelectedClassIds] = useState<string[]>([]);

  // School classes
  const [availableClasses, setAvailableClasses] = useState<SchoolClassOption[]>([]);
  const [classesLoading, setClassesLoading] = useState(false);

  // Submission state
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // Phone validation status
  const phoneValidation = validateRwandaPhone(phone);
  const isPhoneValid = phone.trim() ? phoneValidation.isValid : false;

  // Load school classes when modal opens and schoolId is available
  useEffect(() => {
    if (isOpen && schoolId) {
      setClassesLoading(true);
      fetchSchoolClasses(schoolId)
        .then((classes) => {
          setAvailableClasses(
            classes.map((c) => ({
              id: c.id,
              name: c.name,
              grade: c.grade,
            }))
          );
        })
        .catch(() => {
          // If fetching classes fails, keep empty array
          setAvailableClasses([]);
        })
        .finally(() => setClassesLoading(false));
    }
  }, [isOpen, schoolId]);

  // Reset form when modal closes
  const handleClose = () => {
    setError(null);
    setFullName("");
    setEmail("");
    setPhone("");
    setPassword("");
    setSelectedClassIds([]);
    setRole("teacher");
    onClose();
  };

  const toggleClassSelection = (classId: string) => {
    setSelectedClassIds((prev) =>
      prev.includes(classId)
        ? prev.filter((id) => id !== classId)
        : [...prev, classId]
    );
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError(null);

    // Validation
    if (!fullName.trim()) {
      setError("Please provide the staff member's full name.");
      return;
    }

    if (["teacher", "mentor"].includes(role)) {
      if (!phone.trim()) {
        setError("Phone number is required for teachers and mentors to access USSD.");
        return;
      }
      if (!phoneValidation.isValid) {
        setError(phoneValidation.error || "Please enter a valid Rwandan phone number.");
        return;
      }
    }

    if (["admin", "head_teacher", "sector_officer", "district_director"].includes(role)) {
      if (!email.trim()) {
        setError("Email address is required for web dashboard administrators.");
        return;
      }
      if (!password.trim() || password.length < 8) {
        setError("Password must be at least 8 characters long for dashboard access.");
        return;
      }
    }

    setSubmitting(true);
    try {
      const normalizedPhone = phone.trim() ? phoneValidation.normalized : undefined;

      const newUser = await createUser({
        full_name: fullName.trim(),
        email: email.trim() || undefined,
        phone_e164: normalizedPhone,
        role,
        password: password || undefined,
        school_id: schoolId || undefined,
        class_ids: role === "teacher" && selectedClassIds.length > 0 ? selectedClassIds : undefined,
      });

      handleClose();
      onSuccess(newUser);
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : "Failed to register staff member.");
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <AccessibleModal
      isOpen={isOpen}
      onClose={handleClose}
      title="Register Staff Member"
      description="Add classroom teachers, mentors, or administrators with assigned duties and USSD/Dashboard access."
      maxWidth="lg"
    >
      <form onSubmit={handleSubmit} className="space-y-4 pt-1">
        {error && (
          <div
            role="alert"
            className="p-3 bg-destructive/15 border border-destructive/20 text-destructive rounded-lg text-xs font-medium flex items-center gap-2"
          >
            <AlertTriangle className="h-4 w-4 shrink-0" />
            <span>{error}</span>
          </div>
        )}

        {/* Role Selection */}
        <div className="space-y-1.5">
          <label htmlFor="staff-role" className="text-xs font-semibold uppercase text-muted-foreground">
            Staff Role & Assignment <span className="text-destructive">*</span>
          </label>
          <select
            id="staff-role"
            value={role}
            onChange={(e) => {
              setRole(e.target.value);
              setError(null);
            }}
            className="w-full px-3 py-2 border rounded-md text-sm bg-background focus:outline-hidden focus:ring-2 focus:ring-primary"
          >
            <option value="teacher">Classroom Teacher (USSD Daily Attendance)</option>
            {currentUserRole === "admin" && (
              <>
                <option value="mentor">Community Mentor (USSD Home Visits)</option>
                <option value="head_teacher">Head Teacher (School Oversight)</option>
                <option value="sector_officer">Sector Officer (SEO Escalations)</option>
                <option value="district_director">District Education Director</option>
                <option value="admin">National System Administrator</option>
              </>
            )}
          </select>
        </div>

        {/* Full Name */}
        <div className="space-y-1.5">
          <label htmlFor="staff-full-name" className="text-xs font-semibold uppercase text-muted-foreground">
            Full Name <span className="text-destructive">*</span>
          </label>
          <input
            id="staff-full-name"
            type="text"
            required
            data-autofocus
            value={fullName}
            onChange={(e) => setFullName(e.target.value)}
            placeholder="e.g. Jean Damascene Hakizimana"
            className="w-full px-3 py-2 border rounded-md text-sm bg-background focus:outline-hidden focus:ring-2 focus:ring-primary"
          />
        </div>

        {/* Teacher Class Assignment (When role == 'teacher') */}
        {role === "teacher" && (
          <div className="p-3.5 rounded-lg border bg-muted/30 space-y-2.5">
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-1.5 text-xs font-semibold uppercase text-foreground">
                <GraduationCap className="h-4 w-4 text-emerald-600 dark:text-emerald-400" />
                <span>Assigned Class / Grade Stream</span>
              </div>
              <span className="text-[11px] text-muted-foreground">
                {selectedClassIds.length === 0
                  ? "Optional (can assign later)"
                  : `${selectedClassIds.length} selected`}
              </span>
            </div>

            <p className="text-xs text-muted-foreground leading-relaxed">
              Select the class(es) this teacher is responsible for. When assigned, the teacher will automatically be presented with their class when dialing USSD attendance (<span className="font-mono text-[11px]">*384*...#</span>).
            </p>

            {classesLoading ? (
              <div className="text-xs text-muted-foreground py-2 animate-pulse">
                Loading school classes...
              </div>
            ) : availableClasses.length === 0 ? (
              <div className="p-2.5 rounded border border-dashed text-xs text-muted-foreground flex items-center gap-2">
                <BookOpen className="h-4 w-4 text-muted-foreground/70 shrink-0" />
                <span>No classes found for this school. Classes can be created in the School Setup or Attendance page.</span>
              </div>
            ) : (
              <div className="grid grid-cols-2 sm:grid-cols-3 gap-2 pt-1 max-h-36 overflow-y-auto">
                {availableClasses.map((cls) => {
                  const isChecked = selectedClassIds.includes(cls.id);
                  return (
                    <label
                      key={cls.id}
                      className={`flex items-center gap-2 p-2 rounded-md border text-xs cursor-pointer transition-colors ${
                        isChecked
                          ? "border-primary bg-primary/10 text-primary font-medium"
                          : "border-border hover:bg-muted/50 text-foreground"
                      }`}
                    >
                      <input
                        type="checkbox"
                        checked={isChecked}
                        onChange={() => toggleClassSelection(cls.id)}
                        className="rounded border-input text-primary focus:ring-primary h-3.5 w-3.5"
                      />
                      <span className="truncate">{cls.name}</span>
                    </label>
                  );
                })}
              </div>
            )}
          </div>
        )}

        {/* Phone Number (Rwanda E.164) */}
        <div className="space-y-1.5">
          <div className="flex items-center justify-between">
            <label htmlFor="staff-phone" className="text-xs font-semibold uppercase text-muted-foreground flex items-center gap-1">
              <Smartphone className="h-3.5 w-3.5" />
              <span>Mobile Phone Number (USSD Dialer)</span>
              {["teacher", "mentor"].includes(role) && <span className="text-destructive">*</span>}
            </label>
            {phone.trim() && (
              <span
                className={`text-[11px] font-medium ${
                  isPhoneValid
                    ? "text-emerald-600 dark:text-emerald-400"
                    : "text-amber-600 dark:text-amber-400"
                }`}
              >
                {isPhoneValid
                  ? `✓ ${phoneValidation.carrier || "Valid Rwanda Mobile"}`
                  : phoneValidation.error}
              </span>
            )}
          </div>
          <input
            id="staff-phone"
            type="tel"
            value={phone}
            onChange={(e) => setPhone(e.target.value)}
            placeholder="0788123456 or +250788123456"
            className={`w-full px-3 py-2 border rounded-md text-sm bg-background font-mono focus:outline-hidden focus:ring-2 ${
              phone.trim() && !isPhoneValid
                ? "border-amber-500/50 focus:ring-amber-500"
                : "focus:ring-primary"
            }`}
          />
          <p className="text-[11px] text-muted-foreground">
            Accepts Rwandan local format (<span className="font-mono">0788...</span>, <span className="font-mono">072...</span>) or international (<span className="font-mono">+250788...</span>). Normalized to E.164 automatically.
          </p>
        </div>

        {/* Dashboard Email & Password for Admins / Head Teachers */}
        {["admin", "head_teacher", "sector_officer", "district_director"].includes(role) ? (
          <div className="space-y-3 pt-1 border-t">
            <div className="flex items-center gap-1.5 text-xs font-semibold uppercase text-foreground pt-1">
              <ShieldCheck className="h-4 w-4 text-primary" />
              <span>Web Dashboard Access Credentials</span>
            </div>

            <div className="space-y-1.5">
              <label htmlFor="staff-email" className="text-xs font-semibold uppercase text-muted-foreground">
                Email Address <span className="text-destructive">*</span>
              </label>
              <input
                id="staff-email"
                type="email"
                required
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                placeholder="staff@school.rw"
                className="w-full px-3 py-2 border rounded-md text-sm bg-background focus:outline-hidden focus:ring-2 focus:ring-primary"
              />
            </div>

            <div className="space-y-1.5">
              <label htmlFor="staff-password" className="text-xs font-semibold uppercase text-muted-foreground">
                Dashboard Password <span className="text-destructive">*</span>
              </label>
              <input
                id="staff-password"
                type="password"
                required
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                placeholder="Minimum 8 characters"
                className="w-full px-3 py-2 border rounded-md text-sm bg-background focus:outline-hidden focus:ring-2 focus:ring-primary"
              />
            </div>
          </div>
        ) : (
          /* Optional email for teachers/mentors */
          <div className="space-y-1.5">
            <label htmlFor="staff-email" className="text-xs font-semibold uppercase text-muted-foreground">
              Email Address <span className="text-muted-foreground/60 text-[11px] normal-case">(Optional)</span>
            </label>
            <input
              id="staff-email"
              type="email"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              placeholder="teacher@school.rw"
              className="w-full px-3 py-2 border rounded-md text-sm bg-background focus:outline-hidden focus:ring-2 focus:ring-primary"
            />
          </div>
        )}

        {/* USSD Security Note */}
        <div className="p-3 bg-muted/40 rounded-lg border text-xs text-muted-foreground flex items-start gap-2">
          <CheckCircle2 className="h-4 w-4 text-primary shrink-0 mt-0.5" />
          <p>
            <strong>USSD Security:</strong> The staff member will be prompted to choose their secret 4-digit PIN upon their initial dial into the USSD gateway (<span className="font-mono text-[11px]">*384*...#</span>). PINs can be reset by administrators anytime.
          </p>
        </div>

        {/* Actions */}
        <div className="flex items-center justify-end gap-2 pt-3 border-t">
          <Button variant="outline" type="button" onClick={handleClose} disabled={submitting}>
            Cancel
          </Button>
          <Button type="submit" disabled={submitting}>
            {submitting ? "Registering Staff..." : "Create Staff Account"}
          </Button>
        </div>
      </form>
    </AccessibleModal>
  );
}
