"use client";

import { useEffect, useState } from "react";
import { AccessibleModal } from "@/components/ui/modal";
import { Button } from "@/components/ui/button";
import { fetchSchoolClasses, updateUser, UserItem } from "@/lib/api/client";
import { validateRwandaPhone } from "../lib/phone-utils";
import {
  AlertTriangle,
  GraduationCap,
  Smartphone,
  BookOpen,
} from "lucide-react";

interface SchoolClassOption {
  id: string;
  name: string;
  grade: number;
}

interface EditStaffModalProps {
  user: UserItem | null;
  isOpen: boolean;
  onClose: () => void;
  onSuccess: (updatedUser: UserItem) => void;
  schoolId?: string;
}

export function EditStaffModal({
  user,
  isOpen,
  onClose,
  onSuccess,
  schoolId,
}: EditStaffModalProps) {
  const [fullName, setFullName] = useState("");
  const [phone, setPhone] = useState("");
  const [email, setEmail] = useState("");
  const [isActive, setIsActive] = useState(true);
  const [selectedClassIds, setSelectedClassIds] = useState<string[]>([]);

  // School classes
  const [availableClasses, setAvailableClasses] = useState<SchoolClassOption[]>([]);
  const [classesLoading, setClassesLoading] = useState(false);

  // Submission state
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // Sync state when user prop changes or modal opens
  useEffect(() => {
    if (user && isOpen) {
      setFullName(user.full_name || "");
      setPhone(user.phone_masked || user.phone_e164 || "");
      setEmail(user.email || "");
      setIsActive(user.is_active);
      const existingClassIds = user.assigned_classes?.map((c) => c.id) || [];
      setSelectedClassIds(existingClassIds);
      setError(null);
    }
  }, [user, isOpen]);

  // Load school classes when modal opens for teachers
  useEffect(() => {
    if (isOpen && schoolId && user?.role === "teacher") {
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
          setAvailableClasses([]);
        })
        .finally(() => setClassesLoading(false));
    }
  }, [isOpen, schoolId, user?.role]);

  const toggleClassSelection = (classId: string) => {
    setSelectedClassIds((prev) =>
      prev.includes(classId)
        ? prev.filter((id) => id !== classId)
        : [...prev, classId]
    );
  };

  const phoneValidation = validateRwandaPhone(phone);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!user) return;
    setError(null);

    if (!fullName.trim()) {
      setError("Full name cannot be blank.");
      return;
    }

    let normalizedPhone: string | undefined = undefined;
    if (phone.trim()) {
      // If the phone was masked (e.g. +250 788 *** 456) and untouched, don't update phone
      if (phone.includes("*")) {
        normalizedPhone = undefined;
      } else {
        if (!phoneValidation.isValid) {
          setError(phoneValidation.error || "Please enter a valid Rwandan mobile number.");
          return;
        }
        normalizedPhone = phoneValidation.normalized;
      }
    }

    setSubmitting(true);
    try {
      const updated = await updateUser(user.id, {
        full_name: fullName.trim(),
        email: email.trim() || undefined,
        phone_e164: normalizedPhone,
        is_active: isActive,
        class_ids: user.role === "teacher" ? selectedClassIds : undefined,
      });

      onSuccess(updated);
      onClose();
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : "Failed to update staff member.");
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <AccessibleModal
      isOpen={isOpen}
      onClose={onClose}
      title="Edit Staff Member"
      description={`Update profile details and assignments for ${user?.full_name || "staff"}.`}
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

        {/* Full Name */}
        <div className="space-y-1.5">
          <label htmlFor="edit-full-name" className="text-xs font-semibold uppercase text-muted-foreground">
            Full Name <span className="text-destructive">*</span>
          </label>
          <input
            id="edit-full-name"
            type="text"
            required
            value={fullName}
            onChange={(e) => setFullName(e.target.value)}
            className="w-full px-3 py-2 border rounded-md text-sm bg-background focus:outline-hidden focus:ring-2 focus:ring-primary"
          />
        </div>

        {/* Teacher Class Assignment (When role == 'teacher') */}
        {user?.role === "teacher" && (
          <div className="p-3.5 rounded-lg border bg-muted/30 space-y-2.5">
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-1.5 text-xs font-semibold uppercase text-foreground">
                <GraduationCap className="h-4 w-4 text-emerald-600 dark:text-emerald-400" />
                <span>Assigned Class / Grade Stream</span>
              </div>
              <span className="text-[11px] text-muted-foreground">
                {selectedClassIds.length === 0
                  ? "No classes assigned"
                  : `${selectedClassIds.length} assigned`}
              </span>
            </div>

            <p className="text-xs text-muted-foreground leading-relaxed">
              Check all classes this teacher records attendance for. This instantly configures their USSD dialer menu.
            </p>

            {classesLoading ? (
              <div className="text-xs text-muted-foreground py-2 animate-pulse">
                Loading school classes...
              </div>
            ) : availableClasses.length === 0 ? (
              <div className="p-2.5 rounded border border-dashed text-xs text-muted-foreground flex items-center gap-2">
                <BookOpen className="h-4 w-4 text-muted-foreground/70 shrink-0" />
                <span>No classes available for this school.</span>
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

        {/* Phone */}
        <div className="space-y-1.5">
          <label htmlFor="edit-phone" className="text-xs font-semibold uppercase text-muted-foreground flex items-center gap-1">
            <Smartphone className="h-3.5 w-3.5" />
            <span>Mobile Phone (USSD)</span>
          </label>
          <input
            id="edit-phone"
            type="tel"
            value={phone}
            onChange={(e) => setPhone(e.target.value)}
            placeholder="+250788123456"
            className="w-full px-3 py-2 border rounded-md text-sm bg-background font-mono focus:outline-hidden focus:ring-2 focus:ring-primary"
          />
          <p className="text-[11px] text-muted-foreground">
            Updating the phone changes the USSD MSISDN used for authentication.
          </p>
        </div>

        {/* Email */}
        <div className="space-y-1.5">
          <label htmlFor="edit-email" className="text-xs font-semibold uppercase text-muted-foreground">
            Email Address
          </label>
          <input
            id="edit-email"
            type="email"
            value={email}
            onChange={(e) => setEmail(e.target.value)}
            placeholder="user@garuka.rw"
            className="w-full px-3 py-2 border rounded-md text-sm bg-background focus:outline-hidden focus:ring-2 focus:ring-primary"
          />
        </div>

        {/* Active Status Toggle */}
        <div className="p-3 rounded-lg border bg-muted/20 flex items-center justify-between">
          <div>
            <div className="text-xs font-semibold text-foreground">Account Status</div>
            <p className="text-[11px] text-muted-foreground">
              Disabled staff cannot dial into USSD or access dashboards.
            </p>
          </div>
          <button
            type="button"
            role="switch"
            aria-checked={isActive}
            onClick={() => setIsActive(!isActive)}
            className={`relative inline-flex h-6 w-11 shrink-0 cursor-pointer rounded-full border-2 border-transparent transition-colors duration-200 ease-in-out focus:outline-hidden focus:ring-2 focus:ring-primary ${
              isActive ? "bg-emerald-600" : "bg-muted-foreground/30"
            }`}
          >
            <span
              className={`pointer-events-none inline-block h-5 w-5 transform rounded-full bg-white shadow-lg ring-0 transition duration-200 ease-in-out ${
                isActive ? "translate-x-5" : "translate-x-0"
              }`}
            />
          </button>
        </div>

        {/* Actions */}
        <div className="flex items-center justify-end gap-2 pt-3 border-t">
          <Button variant="outline" type="button" onClick={onClose} disabled={submitting}>
            Cancel
          </Button>
          <Button type="submit" disabled={submitting}>
            {submitting ? "Saving Changes..." : "Save Changes"}
          </Button>
        </div>
      </form>
    </AccessibleModal>
  );
}
