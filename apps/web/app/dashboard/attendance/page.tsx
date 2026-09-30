"use client";

import { useEffect, useState } from "react";
import { useAuth } from "@/lib/auth-context";
import {
  fetchAttendanceCompliance,
  fetchClassAttendance,
  fetchSchoolClasses,
  fetchSchools,
  getComplianceCSVUrl,
  submitClassAttendance,
  voidAbsence,
} from "@/lib/api/client";
import { Button } from "@/components/ui/button";

interface SchoolItem {
  id: string;
  name: string;
}

interface ClassItem {
  id: string;
  name: string;
  grade: number;
}

interface ComplianceData {
  school_id: string;
  school_name: string;
  from_date: string;
  to_date: string;
  compliance_pct: number;
  classes: Array<{
    class_id: string;
    class_name: string;
    grade: number;
    days: Array<{
      date: string;
      status: "submitted" | "missing" | "non_school_day";
      absent_count: number | null;
    }>;
  }>;
}

interface AttendanceRoster {
  class_id: string;
  class_name: string;
  date: string;
  submission: {
    id: string;
    class_id: string;
    date: string;
    submitted_by: string;
    source: string;
    absent_count: number;
    submitted_at: string;
  } | null;
  students: Array<{
    id: string;
    roll_number: number;
    full_name: string;
    is_absent: boolean;
    absence_id: string | null;
    reason_code: string | null;
    status: string | null;
  }>;
}

export default function AttendancePage() {
  const { user } = useAuth();

  const [schools, setSchools] = useState<SchoolItem[]>([]);
  const [selectedSchoolId, setSelectedSchoolId] = useState<string>("");
  const [compliance, setCompliance] = useState<ComplianceData | null>(null);
  const [complianceLoading, setComplianceLoading] = useState(false);

  // Manual Attendance Fallback state
  const [classes, setClasses] = useState<ClassItem[]>([]);
  const [selectedClassId, setSelectedClassId] = useState<string>("");
  const [selectedDate, setSelectedDate] = useState<string>(
    new Date().toISOString().split("T")[0]
  );
  const [roster, setRoster] = useState<AttendanceRoster | null>(null);
  const [rosterLoading, setRosterLoading] = useState(false);
  const [absentIds, setAbsentIds] = useState<Set<string>>(new Set());
  const [saveLoading, setSaveLoading] = useState(false);
  const [feedback, setFeedback] = useState<{ type: "success" | "error"; message: string } | null>(
    null
  );

  // Load available schools
  useEffect(() => {
    if (user?.role === "admin") {
      fetchSchools()
        .then((data) => {
          const list = data as SchoolItem[];
          setSchools(list);
          if (list.length > 0 && !selectedSchoolId) {
            setSelectedSchoolId(list[0].id);
          }
        })
        .catch(console.error);
    } else if (user?.school_id) {
      setSelectedSchoolId(user.school_id);
    }
  }, [user]);

  // Load compliance grid & classes whenever selectedSchoolId changes
  useEffect(() => {
    if (!selectedSchoolId) return;

    setComplianceLoading(true);
    fetchAttendanceCompliance(selectedSchoolId)
      .then((data) => setCompliance(data))
      .catch(console.error)
      .finally(() => setComplianceLoading(false));

    fetchSchoolClasses(selectedSchoolId)
      .then((clsList) => {
        setClasses(clsList);
        if (clsList.length > 0 && !selectedClassId) {
          setSelectedClassId(clsList[0].id);
        }
      })
      .catch(console.error);
  }, [selectedSchoolId]);

  // Load roster for manual entry
  const loadRoster = (classId: string, date: string) => {
    if (!classId) return;
    setRosterLoading(true);
    setFeedback(null);
    fetchClassAttendance(classId, date)
      .then((data) => {
        setRoster(data);
        const marked = new Set(
          data.students.filter((s) => s.is_absent).map((s) => s.id)
        );
        setAbsentIds(marked);
      })
      .catch((err) => {
        console.error(err);
        setFeedback({ type: "error", message: "Failed to load class roster" });
      })
      .finally(() => setRosterLoading(false));
  };

  useEffect(() => {
    if (selectedClassId && selectedDate) {
      loadRoster(selectedClassId, selectedDate);
    }
  }, [selectedClassId, selectedDate]);

  const toggleStudentAbsence = (studentId: string) => {
    const next = new Set(absentIds);
    if (next.has(studentId)) {
      next.delete(studentId);
    } else {
      next.add(studentId);
    }
    setAbsentIds(next);
  };

  const handleSaveAttendance = async () => {
    if (!selectedClassId || !selectedDate) return;
    setSaveLoading(true);
    setFeedback(null);
    try {
      await submitClassAttendance(selectedClassId, {
        date: selectedDate,
        absent_student_ids: Array.from(absentIds),
      });
      setFeedback({
        type: "success",
        message: `Attendance saved successfully for ${selectedDate} (${absentIds.size} absent).`,
      });
      // Refresh compliance grid and roster
      if (selectedSchoolId) {
        fetchAttendanceCompliance(selectedSchoolId).then(setCompliance);
      }
      loadRoster(selectedClassId, selectedDate);
    } catch (err: any) {
      setFeedback({ type: "error", message: err.message || "Failed to submit attendance" });
    } finally {
      setSaveLoading(false);
    }
  };

  const handleVoidAbsence = async (absenceId: string) => {
    if (!confirm("Are you sure you want to void this absence record?")) return;
    try {
      await voidAbsence(absenceId);
      setFeedback({ type: "success", message: "Absence voided successfully." });
      if (selectedClassId && selectedDate) {
        loadRoster(selectedClassId, selectedDate);
      }
      if (selectedSchoolId) {
        fetchAttendanceCompliance(selectedSchoolId).then(setCompliance);
      }
    } catch (err: any) {
      setFeedback({ type: "error", message: err.message || "Failed to void absence" });
    }
  };

  return (
    <div className="space-y-8">
      {/* Header */}
      <div className="flex flex-col sm:flex-row justify-between items-start sm:items-center gap-4">
        <div>
          <h1 className="text-2xl font-bold tracking-tight">Classes & Attendance</h1>
          <p className="text-sm text-muted-foreground mt-1">
            Track daily attendance submissions, compliance rates, and manual fallbacks.
          </p>
        </div>

        <div className="flex items-center gap-3">
          {user?.role === "admin" && schools.length > 0 && (
            <select
              value={selectedSchoolId}
              onChange={(e) => setSelectedSchoolId(e.target.value)}
              className="border rounded-md px-3 py-2 text-sm bg-background"
            >
              {schools.map((s) => (
                <option key={s.id} value={s.id}>
                  {s.name}
                </option>
              ))}
            </select>
          )}

          {selectedSchoolId && (
            <Button
              variant="outline"
              size="sm"
              onClick={() => {
                const url = getComplianceCSVUrl(selectedSchoolId);
                window.open(url, "_blank");
              }}
            >
              Export CSV
            </Button>
          )}
        </div>
      </div>

      {/* Compliance Overview Section */}
      <div className="border rounded-xl p-6 bg-card">
        <div className="flex flex-col sm:flex-row justify-between items-start sm:items-center mb-6 gap-2">
          <div>
            <h2 className="text-lg font-semibold">Submission Compliance Grid</h2>
            <p className="text-xs text-muted-foreground mt-0.5">
              School days compliance over the last 14 days.
            </p>
          </div>
          {compliance && (
            <div className="flex items-center gap-3">
              <span className="text-sm font-medium text-muted-foreground">Compliance:</span>
              <span
                className={`text-lg font-bold px-3 py-1 rounded-full ${
                  compliance.compliance_pct >= 90
                    ? "bg-green-100 text-green-800"
                    : compliance.compliance_pct >= 70
                    ? "bg-amber-100 text-amber-800"
                    : "bg-red-100 text-red-800"
                }`}
              >
                {compliance.compliance_pct}%
              </span>
            </div>
          )}
        </div>

        {complianceLoading ? (
          <p className="text-sm text-muted-foreground animate-pulse py-6 text-center">
            Loading compliance grid...
          </p>
        ) : !compliance || compliance.classes.length === 0 ? (
          <p className="text-sm text-muted-foreground py-6 text-center">
            No classes found for this school.
          </p>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-sm border-collapse">
              <thead>
                <tr className="border-b bg-muted/40">
                  <th className="py-2.5 px-3 text-left font-medium">Class</th>
                  {compliance.classes[0]?.days.map((d) => (
                    <th key={d.date} className="py-2.5 px-2 text-center font-medium text-xs">
                      {d.date.slice(5)}
                    </th>
                  ))}
                </tr>
              </thead>
              <tbody className="divide-y">
                {compliance.classes.map((cls) => (
                  <tr key={cls.class_id} className="hover:bg-muted/20">
                    <td className="py-3 px-3 font-medium whitespace-nowrap">
                      {cls.class_name}
                      <span className="text-xs text-muted-foreground ml-2">(Gr. {cls.grade})</span>
                    </td>
                    {cls.days.map((day) => {
                      let cellColor = "bg-muted/30 text-muted-foreground";
                      let label = "–";

                      if (day.status === "submitted") {
                        cellColor = "bg-emerald-100 text-emerald-800 dark:bg-emerald-950 dark:text-emerald-300";
                        label = `${day.absent_count} abs`;
                      } else if (day.status === "missing") {
                        cellColor = "bg-red-100 text-red-800 dark:bg-red-950 dark:text-red-300 font-semibold";
                        label = "Missing";
                      } else {
                        label = "Off";
                      }

                      return (
                        <td
                          key={day.date}
                          className="py-2 px-1 text-center cursor-pointer"
                          onClick={() => {
                            setSelectedClassId(cls.class_id);
                            setSelectedDate(day.date);
                          }}
                        >
                          <div
                            className={`rounded py-1 px-1.5 text-[11px] transition hover:opacity-80 ${cellColor}`}
                            title={`${cls.class_name} on ${day.date}: ${day.status}`}
                          >
                            {label}
                          </div>
                        </td>
                      );
                    })}
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}

        <div className="flex items-center gap-6 mt-4 text-xs text-muted-foreground">
          <div className="flex items-center gap-1.5">
            <span className="w-3 h-3 rounded bg-emerald-100 dark:bg-emerald-950 border border-emerald-300" />
            <span>Submitted</span>
          </div>
          <div className="flex items-center gap-1.5">
            <span className="w-3 h-3 rounded bg-red-100 dark:bg-red-950 border border-red-300" />
            <span>Missing (Data Gap)</span>
          </div>
          <div className="flex items-center gap-1.5">
            <span className="w-3 h-3 rounded bg-muted/30 border" />
            <span>Non-School Day</span>
          </div>
        </div>
      </div>

      {/* Manual Attendance Fallback Form */}
      <div className="border rounded-xl p-6 bg-card space-y-6">
        <div>
          <h2 className="text-lg font-semibold">Manual Attendance Entry (Fallback)</h2>
          <p className="text-xs text-muted-foreground mt-0.5">
            Use when teachers cannot submit attendance via USSD or to update an existing submission.
          </p>
        </div>

        {feedback && (
          <div
            className={`p-3 rounded-md text-sm ${
              feedback.type === "success"
                ? "bg-green-50 text-green-800 border border-green-200"
                : "bg-red-50 text-red-800 border border-red-200"
            }`}
          >
            {feedback.message}
          </div>
        )}

        <div className="flex flex-wrap items-center gap-4">
          <div className="space-y-1">
            <label className="text-xs font-medium text-muted-foreground">Class</label>
            <select
              value={selectedClassId}
              onChange={(e) => setSelectedClassId(e.target.value)}
              className="border rounded-md px-3 py-2 text-sm bg-background block"
            >
              {classes.map((c) => (
                <option key={c.id} value={c.id}>
                  {c.name} (Grade {c.grade})
                </option>
              ))}
            </select>
          </div>

          <div className="space-y-1">
            <label className="text-xs font-medium text-muted-foreground">Date</label>
            <input
              type="date"
              value={selectedDate}
              onChange={(e) => setSelectedDate(e.target.value)}
              className="border rounded-md px-3 py-2 text-sm bg-background block"
            />
          </div>

          {roster?.submission && (
            <div className="ml-auto text-right text-xs text-muted-foreground">
              <span className="font-semibold text-foreground">Recorded via {roster.submission.source}</span>
              <p>
                {roster.submission.absent_count} absent •{" "}
                {new Date(roster.submission.submitted_at).toLocaleTimeString()}
              </p>
            </div>
          )}
        </div>

        {rosterLoading ? (
          <p className="text-sm text-muted-foreground animate-pulse py-8 text-center">
            Loading class roster...
          </p>
        ) : !roster || roster.students.length === 0 ? (
          <p className="text-sm text-muted-foreground py-8 text-center">
            No students found in this class.
          </p>
        ) : (
          <div className="border rounded-lg overflow-hidden">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b bg-muted/40 text-left">
                  <th className="py-2.5 px-4 font-medium w-16">Roll</th>
                  <th className="py-2.5 px-4 font-medium">Student Name</th>
                  <th className="py-2.5 px-4 font-medium text-center">Status</th>
                  <th className="py-2.5 px-4 font-medium text-right">Action</th>
                </tr>
              </thead>
              <tbody className="divide-y">
                {roster.students.map((st) => {
                  const isMarkedAbsent = absentIds.has(st.id);
                  return (
                    <tr
                      key={st.id}
                      className={isMarkedAbsent ? "bg-red-50/40 dark:bg-red-950/20" : ""}
                    >
                      <td className="py-3 px-4 font-mono text-muted-foreground">{st.roll_number}</td>
                      <td className="py-3 px-4 font-medium">{st.full_name}</td>
                      <td className="py-3 px-4 text-center">
                        {isMarkedAbsent ? (
                          <span className="inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-semibold bg-red-100 text-red-800 dark:bg-red-950 dark:text-red-300">
                            Absent {st.reason_code ? `(${st.reason_code})` : ""}
                          </span>
                        ) : (
                          <span className="inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-semibold bg-emerald-100 text-emerald-800 dark:bg-emerald-950 dark:text-emerald-300">
                            Present
                          </span>
                        )}
                      </td>
                      <td className="py-3 px-4 text-right space-x-2">
                        <Button
                          size="sm"
                          variant={isMarkedAbsent ? "destructive" : "outline"}
                          onClick={() => toggleStudentAbsence(st.id)}
                        >
                          {isMarkedAbsent ? "Mark Present" : "Mark Absent"}
                        </Button>
                        {st.absence_id && (
                          <Button
                            size="sm"
                            variant="ghost"
                            className="text-xs text-muted-foreground hover:text-destructive"
                            onClick={() => handleVoidAbsence(st.absence_id!)}
                          >
                            Void
                          </Button>
                        )}
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        )}

        {roster && roster.students.length > 0 && (
          <div className="flex justify-between items-center pt-2">
            <p className="text-xs text-muted-foreground">
              Total students: {roster.students.length} • Marked absent: {absentIds.size}
            </p>
            <Button onClick={handleSaveAttendance} disabled={saveLoading}>
              {saveLoading ? "Saving..." : "Save Attendance Record"}
            </Button>
          </div>
        )}
      </div>
    </div>
  );
}
