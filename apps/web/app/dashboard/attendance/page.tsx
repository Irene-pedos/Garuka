"use client";

import { useEffect, useState, useMemo } from "react";
import { useAuth } from "@/lib/auth-context";
import {
  fetchAttendanceCompliance,
  fetchClassAttendance,
  fetchSchoolClasses,
  fetchSchools,
  getComplianceCSVUrl,
  downloadComplianceCSV,
  submitClassAttendance,
  voidAbsence,
} from "@/lib/api/client";
import { Button } from "@/components/ui/button";
import { ScopeHeader } from "@/components/scope-header";
import { AccessibleModal } from "@/components/ui/modal";
import { toast } from "sonner";
import {
  ClipboardCheck,
  Search,
  Users,
  CheckCircle2,
  AlertCircle,
  Calendar,
  Check,
  X,
  FileSpreadsheet,
  Clock,
  Sparkles,
  Info,
} from "lucide-react";

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
  const [isModalOpen, setIsModalOpen] = useState(false);
  const [classes, setClasses] = useState<ClassItem[]>([]);
  const [selectedClassId, setSelectedClassId] = useState<string>("");
  const [selectedDate, setSelectedDate] = useState<string>(
    new Date().toISOString().split("T")[0]
  );
  const [searchQuery, setSearchQuery] = useState("");
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

  const markAllPresent = () => {
    setAbsentIds(new Set());
    toast.info("All students marked present.");
  };

  const markAllAbsent = () => {
    if (!roster) return;
    setAbsentIds(new Set(roster.students.map((s) => s.id)));
    toast.info("All students marked absent.");
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
      const successText = `Attendance saved successfully for ${selectedDate} (${absentIds.size} absent).`;
      setFeedback({
        type: "success",
        message: successText,
      });
      toast.success(successText);

      // Refresh compliance grid and roster
      if (selectedSchoolId) {
        fetchAttendanceCompliance(selectedSchoolId).then(setCompliance);
      }
      loadRoster(selectedClassId, selectedDate);

      // Auto close modal on successful save after a short pause
      setTimeout(() => {
        setIsModalOpen(false);
      }, 700);
    } catch (err: any) {
      const errorMsg = err.message || "Failed to submit attendance";
      setFeedback({ type: "error", message: errorMsg });
      toast.error(errorMsg);
    } finally {
      setSaveLoading(false);
    }
  };

  const handleVoidAbsence = async (absenceId: string) => {
    if (!confirm("Are you sure you want to void this absence record?")) return;
    try {
      await voidAbsence(absenceId);
      setFeedback({ type: "success", message: "Absence voided successfully." });
      toast.success("Absence voided successfully.");
      if (selectedClassId && selectedDate) {
        loadRoster(selectedClassId, selectedDate);
      }
      if (selectedSchoolId) {
        fetchAttendanceCompliance(selectedSchoolId).then(setCompliance);
      }
    } catch (err: any) {
      const errorMsg = err.message || "Failed to void absence";
      setFeedback({ type: "error", message: errorMsg });
      toast.error(errorMsg);
    }
  };

  const [isExportingCSV, setIsExportingCSV] = useState(false);

  const handleExportCSV = async () => {
    if (!selectedSchoolId) return;
    setIsExportingCSV(true);
    try {
      await downloadComplianceCSV(
        selectedSchoolId,
        compliance?.from_date,
        compliance?.to_date,
        compliance?.school_name
      );
      toast.success("Compliance CSV downloaded successfully.");
    } catch (err: any) {
      toast.error(err.message || "Failed to download CSV");
    } finally {
      setIsExportingCSV(false);
    }
  };

  // Filter roster students by search query
  const filteredStudents = useMemo(() => {
    if (!roster) return [];
    if (!searchQuery.trim()) return roster.students;
    const q = searchQuery.toLowerCase().trim();
    return roster.students.filter(
      (s) =>
        s.full_name.toLowerCase().includes(q) ||
        String(s.roll_number).includes(q)
    );
  }, [roster, searchQuery]);

  return (
    <div className="space-y-8">
      {/* Header with Scope & Kigali timezone */}
      <ScopeHeader
        title="Classes & Daily Attendance"
        description="Track daily attendance submissions, compliance rates, and manual fallbacks."
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
                name: compliance?.school_name || user.full_name,
              }
            : undefined
        }
        dateInfo={`Kigali School Day: ${selectedDate}`}
      >
        <div className="flex items-center gap-2.5">
          {user?.role === "admin" && schools.length > 0 && (
            <select
              aria-label="Select school"
              value={selectedSchoolId}
              onChange={(e) => setSelectedSchoolId(e.target.value)}
              className="border rounded-md px-3 py-1.5 text-xs bg-background focus:outline-hidden focus:ring-2 focus:ring-primary"
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
              disabled={isExportingCSV}
              className="h-8 text-xs gap-1.5"
              onClick={handleExportCSV}
            >
              <FileSpreadsheet className="w-3.5 h-3.5" />
              {isExportingCSV ? "Exporting..." : "Export CSV"}
            </Button>
          )}

          <Button
            size="sm"
            onClick={() => setIsModalOpen(true)}
            className="h-8 text-xs gap-1.5 shadow-xs"
          >
            <ClipboardCheck className="w-3.5 h-3.5" />
            Manual Entry
          </Button>
        </div>
      </ScopeHeader>

      {/* Compliance Overview Section */}
      <div className="border rounded-xl p-6 bg-card shadow-xs">
        <div className="flex flex-col sm:flex-row justify-between items-start sm:items-center mb-6 gap-3">
          <div>
            <div className="flex items-center gap-2">
              <h2 className="text-lg font-semibold tracking-tight">Submission Compliance Grid</h2>
              <span className="text-xs text-muted-foreground bg-muted/60 px-2 py-0.5 rounded-md border">
                Last 14 School Days
              </span>
            </div>
            <p className="text-xs text-muted-foreground mt-0.5">
              Click on any class date cell to immediately open the manual attendance editor.
            </p>
          </div>
          {compliance && (
            <div className="flex items-center gap-3">
              <span className="text-sm font-medium text-muted-foreground">Compliance:</span>
              <span
                className={`text-lg font-bold px-3 py-1 rounded-full ${
                  compliance.compliance_pct >= 90
                    ? "bg-green-100 text-green-800 dark:bg-green-950/60 dark:text-green-300"
                    : compliance.compliance_pct >= 70
                    ? "bg-amber-100 text-amber-800 dark:bg-amber-950/60 dark:text-amber-300"
                    : "bg-red-100 text-red-800 dark:bg-red-950/60 dark:text-red-300"
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
                    <th key={d.date} className="py-2.5 px-2 text-center font-medium text-xs whitespace-nowrap">
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
                            setIsModalOpen(true);
                          }}
                        >
                          <div
                            className={`rounded py-1 px-1.5 text-[11px] transition hover:opacity-80 hover:ring-1 hover:ring-primary/40 ${cellColor}`}
                            title={`Click to open attendance editor for ${cls.class_name} on ${day.date} (${day.status})`}
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

        <div className="flex flex-wrap items-center justify-between gap-4 mt-5 pt-4 border-t text-xs text-muted-foreground">
          <div className="flex items-center gap-6">
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

          <span className="text-[11px] text-muted-foreground/80 italic">
            Tip: Click any cell above to open the full attendance editor.
          </span>
        </div>
      </div>

      {/* Quick Launch Card for Manual Attendance Entry */}
      <div className="border rounded-xl p-5 bg-card/60 flex flex-col sm:flex-row items-start sm:items-center justify-between gap-4 shadow-xs">
        <div className="space-y-1">
          <div className="flex items-center gap-2">
            <ClipboardCheck className="w-4 h-4 text-primary" />
            <h3 className="text-sm font-semibold text-foreground">
              Manual Attendance Entry (Fallback)
            </h3>
          </div>
          <p className="text-xs text-muted-foreground">
            Quickly fill and save attendance records when SMS or USSD sessions are unavailable, or update past submissions.
          </p>
        </div>

        <Button
          onClick={() => setIsModalOpen(true)}
          className="shrink-0 h-8 text-xs gap-1.5"
        >
          <ClipboardCheck className="w-3.5 h-3.5" />
          Open Manual Attendance Entry
        </Button>
      </div>

      {/* Manual Attendance Fallback Popup Overlay */}
      <AccessibleModal
        isOpen={isModalOpen}
        onClose={() => {
          setIsModalOpen(false);
          setSearchQuery("");
        }}
        title="Manual Attendance Entry (Fallback)"
        description="Fill class attendance when USSD (*384*1234#) is unavailable, or review and update existing submissions."
        maxWidth="full"
        className="max-w-[96vw] xl:max-w-6xl w-full p-6"
      >
        <div className="space-y-5">
          {/* Feedback alert inside modal */}
          {feedback && (
            <div
              className={`p-3 rounded-lg text-xs flex items-center gap-2 ${
                feedback.type === "success"
                  ? "bg-emerald-500/10 text-emerald-800 dark:text-emerald-300 border border-emerald-500/20"
                  : "bg-destructive/10 text-destructive border border-destructive/20"
              }`}
            >
              {feedback.type === "success" ? (
                <CheckCircle2 className="w-4 h-4 shrink-0 text-emerald-600" />
              ) : (
                <AlertCircle className="w-4 h-4 shrink-0 text-destructive" />
              )}
              <span className="font-medium">{feedback.message}</span>
            </div>
          )}

          {/* Filter & Selector Controls */}
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-12 gap-3.5 p-3.5 rounded-xl border bg-muted/20">
            {/* Class Selection */}
            <div className="sm:col-span-1 lg:col-span-4 space-y-1">
              <label className="text-xs font-semibold text-muted-foreground flex items-center gap-1.5">
                <Users className="w-3.5 h-3.5 text-primary" />
                Select Class
              </label>
              <select
                value={selectedClassId}
                onChange={(e) => setSelectedClassId(e.target.value)}
                className="w-full h-8 px-2.5 py-1 text-xs rounded-md border border-input bg-background focus:outline-hidden focus:ring-2 focus:ring-primary block"
              >
                {classes.map((c) => (
                  <option key={c.id} value={c.id}>
                    {c.name} (Grade {c.grade})
                  </option>
                ))}
              </select>
            </div>

            {/* Date Selection */}
            <div className="sm:col-span-1 lg:col-span-3 space-y-1">
              <label className="text-xs font-semibold text-muted-foreground flex items-center gap-1.5">
                <Calendar className="w-3.5 h-3.5 text-primary" />
                Attendance Date
              </label>
              <input
                type="date"
                value={selectedDate}
                onChange={(e) => setSelectedDate(e.target.value)}
                className="w-full h-8 px-2.5 py-1 text-xs rounded-md border border-input bg-background focus:outline-hidden focus:ring-2 focus:ring-primary block"
              />
            </div>

            {/* Quick Student Search */}
            <div className="sm:col-span-2 lg:col-span-5 space-y-1">
              <label className="text-xs font-semibold text-muted-foreground flex items-center gap-1.5">
                <Search className="w-3.5 h-3.5 text-primary" />
                Search in Roster
              </label>
              <div className="relative">
                <input
                  type="text"
                  value={searchQuery}
                  onChange={(e) => setSearchQuery(e.target.value)}
                  placeholder="Filter by student name or roll number..."
                  className="w-full h-8 pl-8 pr-3 text-xs rounded-md border border-input bg-background focus:outline-hidden focus:ring-2 focus:ring-primary"
                />
                <Search className="w-3.5 h-3.5 text-muted-foreground absolute left-2.5 top-2.5 pointer-events-none" />
                {searchQuery && (
                  <button
                    type="button"
                    onClick={() => setSearchQuery("")}
                    className="absolute right-2 top-2 text-muted-foreground hover:text-foreground text-xs"
                  >
                    <X className="w-3.5 h-3.5" />
                  </button>
                )}
              </div>
            </div>
          </div>

          {/* Submission Metadata Banner (if existing) */}
          {roster?.submission && (
            <div className="flex flex-wrap items-center justify-between gap-2 px-3.5 py-2 rounded-lg bg-primary/5 border border-primary/20 text-xs">
              <div className="flex items-center gap-2">
                <Info className="w-4 h-4 text-primary shrink-0" />
                <span className="font-semibold text-foreground">
                  Recorded via {roster.submission.source}
                </span>
                <span className="text-muted-foreground">•</span>
                <span className="text-muted-foreground">
                  {roster.submission.absent_count} marked absent
                </span>
              </div>
              <span className="text-muted-foreground text-[11px] flex items-center gap-1">
                <Clock className="w-3 h-3" />
                {new Date(roster.submission.submitted_at).toLocaleString()}
              </span>
            </div>
          )}

          {/* Bulk Action Buttons & Roster Counters */}
          <div className="flex flex-wrap items-center justify-between gap-2 pt-1 text-xs">
            <div className="flex items-center gap-2">
              <span className="text-muted-foreground font-medium">
                Showing {filteredStudents.length} of {roster?.students.length || 0} students
              </span>
              {absentIds.size > 0 && (
                <span className="px-2 py-0.5 rounded-full font-semibold bg-red-100 text-red-800 dark:bg-red-950 dark:text-red-300 text-[11px]">
                  {absentIds.size} Marked Absent
                </span>
              )}
            </div>

            <div className="flex items-center gap-2">
              <Button
                type="button"
                variant="outline"
                size="sm"
                onClick={markAllPresent}
                disabled={rosterLoading || !roster || roster.students.length === 0}
                className="h-7 text-xs px-2.5 text-emerald-700 hover:text-emerald-800 hover:bg-emerald-50 dark:hover:bg-emerald-950/40"
              >
                <Check className="w-3.5 h-3.5 mr-1 text-emerald-600" />
                Mark All Present
              </Button>
              <Button
                type="button"
                variant="outline"
                size="sm"
                onClick={markAllAbsent}
                disabled={rosterLoading || !roster || roster.students.length === 0}
                className="h-7 text-xs px-2.5 text-red-700 hover:text-red-800 hover:bg-red-50 dark:hover:bg-red-950/40"
              >
                <X className="w-3.5 h-3.5 mr-1 text-red-600" />
                Mark All Absent
              </Button>
            </div>
          </div>

          {/* Student Roster Table */}
          {rosterLoading ? (
            <div className="py-16 text-center space-y-2">
              <p className="text-sm font-medium text-muted-foreground animate-pulse">
                Loading class roster for {selectedDate}...
              </p>
            </div>
          ) : !roster || roster.students.length === 0 ? (
            <div className="border rounded-xl p-12 text-center bg-muted/10 space-y-2">
              <Users className="w-8 h-8 text-muted-foreground/60 mx-auto" />
              <p className="text-sm font-medium text-foreground">No students enrolled in this class.</p>
              <p className="text-xs text-muted-foreground">Select another class or import students.</p>
            </div>
          ) : filteredStudents.length === 0 ? (
            <div className="border rounded-xl p-10 text-center bg-muted/10 space-y-1">
              <Search className="w-6 h-6 text-muted-foreground/60 mx-auto mb-1" />
              <p className="text-sm font-medium text-foreground">No students matching "{searchQuery}"</p>
              <button
                type="button"
                onClick={() => setSearchQuery("")}
                className="text-xs text-primary underline cursor-pointer"
              >
                Clear filter
              </button>
            </div>
          ) : (
            <div className="border rounded-xl overflow-hidden max-h-[50vh] overflow-y-auto shadow-xs">
              <table className="w-full text-xs sm:text-sm">
                <thead className="sticky top-0 z-10 bg-muted/80 backdrop-blur-xs border-b">
                  <tr className="text-left font-semibold text-muted-foreground text-xs">
                    <th className="py-2.5 px-4 w-16">Roll</th>
                    <th className="py-2.5 px-4">Student Name</th>
                    <th className="py-2.5 px-4 text-center w-36">Status</th>
                    <th className="py-2.5 px-4 text-right w-44">Action</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-border">
                  {filteredStudents.map((st) => {
                    const isMarkedAbsent = absentIds.has(st.id);
                    return (
                      <tr
                        key={st.id}
                        className={`transition-colors ${
                          isMarkedAbsent
                            ? "bg-red-50/50 dark:bg-red-950/20"
                            : "hover:bg-muted/30"
                        }`}
                      >
                        <td className="py-2.5 px-4 font-mono text-muted-foreground text-xs">
                          #{st.roll_number}
                        </td>
                        <td className="py-2.5 px-4 font-medium text-foreground">
                          {st.full_name}
                        </td>
                        <td className="py-2.5 px-4 text-center">
                          {isMarkedAbsent ? (
                            <span className="inline-flex items-center px-2 py-0.5 rounded-full text-xs font-semibold bg-red-100 text-red-800 dark:bg-red-950 dark:text-red-300">
                              Absent {st.reason_code ? `(${st.reason_code})` : ""}
                            </span>
                          ) : (
                            <span className="inline-flex items-center px-2 py-0.5 rounded-full text-xs font-semibold bg-emerald-100 text-emerald-800 dark:bg-emerald-950 dark:text-emerald-300">
                              Present
                            </span>
                          )}
                        </td>
                        <td className="py-2.5 px-4 text-right space-x-1.5 whitespace-nowrap">
                          <Button
                            size="sm"
                            variant={isMarkedAbsent ? "destructive" : "outline"}
                            className="h-7 text-xs px-2.5"
                            onClick={() => toggleStudentAbsence(st.id)}
                          >
                            {isMarkedAbsent ? (
                              <>
                                <Check className="w-3 h-3 mr-1" />
                                Mark Present
                              </>
                            ) : (
                              <>
                                <X className="w-3 h-3 mr-1" />
                                Mark Absent
                              </>
                            )}
                          </Button>
                          {st.absence_id && (
                            <Button
                              size="sm"
                              variant="ghost"
                              className="h-7 text-xs text-muted-foreground hover:text-destructive px-2"
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

          {/* Modal Action Footer */}
          <div className="flex flex-col sm:flex-row items-center justify-between gap-4 pt-4 border-t">
            <div className="text-xs text-muted-foreground">
              Total Enrolled:{" "}
              <span className="font-semibold text-foreground">
                {roster?.students.length || 0}
              </span>{" "}
              • Present:{" "}
              <span className="font-semibold text-emerald-600">
                {roster ? Math.max(0, roster.students.length - absentIds.size) : 0}
              </span>{" "}
              • Absent:{" "}
              <span className="font-semibold text-red-600">
                {absentIds.size}
              </span>
            </div>

            <div className="flex items-center gap-2.5 w-full sm:w-auto justify-end">
              <Button
                type="button"
                variant="outline"
                onClick={() => {
                  setIsModalOpen(false);
                  setSearchQuery("");
                }}
                className="h-8 text-xs px-4"
              >
                Cancel
              </Button>
              <Button
                type="button"
                onClick={handleSaveAttendance}
                disabled={saveLoading || !roster || roster.students.length === 0}
                className="h-8 text-xs px-5 shadow-xs"
              >
                {saveLoading ? "Saving Attendance..." : "Save Attendance Record"}
              </Button>
            </div>
          </div>
        </div>
      </AccessibleModal>
    </div>
  );
}
