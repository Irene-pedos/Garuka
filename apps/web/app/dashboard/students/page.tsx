"use client";

import { useEffect, useState } from "react";
import { useAuth } from "@/lib/auth-context";
import { fetchStudents, uploadStudentsCSV } from "@/lib/api/client";
import { Button } from "@/components/ui/button";
import { AccessibleModal } from "@/components/ui/modal";
import { ScopeHeader } from "@/components/scope-header";
import { Upload, Download, RefreshCw, AlertTriangle } from "lucide-react";

interface StudentItem {
  id: string;
  roll_number: number;
  full_name: string;
  student_code?: string | null;
  class_name?: string | null;
  sex?: string | null;
  birth_year?: number | null;
  status: string;
  guardians: Array<{
    id: string;
    full_name: string;
    phone_masked: string;
  }>;
}

export default function StudentsPage() {
  const { user } = useAuth();
  const [students, setStudents] = useState<StudentItem[]>([]);
  const [search, setSearch] = useState("");
  const [loading, setLoading] = useState(true);
  const [fetchError, setFetchError] = useState<string | null>(null);

  // CSV Import State
  const [isModalOpen, setIsModalOpen] = useState(false);
  const [file, setFile] = useState<File | null>(null);
  const [importLoading, setImportLoading] = useState(false);
  const [importError, setImportError] = useState<string | null>(null);
  const [importResult, setImportResult] = useState<{
    created: number;
    updated: number;
    skipped: number;
    errors: Array<{ row: number; message: string }>;
  } | null>(null);

  const loadStudents = (signal?: AbortSignal) => {
    setLoading(true);
    setFetchError(null);
    fetchStudents({ q: search || undefined }, signal)
      .then((data) => setStudents(data as StudentItem[]))
      .catch((err) => {
        if (err.name !== "AbortError") {
          setFetchError(err.message || "Failed to load students");
        }
      })
      .finally(() => setLoading(false));
  };

  useEffect(() => {
    const controller = new AbortController();
    loadStudents(controller.signal);
    return () => controller.abort();
  }, [search]);

  const handleImport = async (dryRun: boolean) => {
    if (!file) return;
    setImportLoading(true);
    setImportError(null);
    setImportResult(null);
    try {
      const res = await uploadStudentsCSV(file, user?.school_id || undefined, dryRun);
      setImportResult(res);
      if (!dryRun && res.errors.length === 0) {
        loadStudents();
      }
    } catch (err: unknown) {
      setImportError(err instanceof Error ? err.message : "Import failed");
    } finally {
      setImportLoading(false);
    }
  };

  const downloadCSVTemplate = () => {
    const csvContent =
      "student_code,full_name,sex,birth_year,class_name,roll_number,guardian_name,guardian_phone,guardian_relationship\n" +
      "SDMS-2026101,Uwase Jeanne,F,2014,P5 A,1,Mama Jeanne,+250780000101,mother\n" +
      "SDMS-2026102,Kamana Eric,M,2013,P5 A,2,Papa Eric,+250780000102,father\n";
    const blob = new Blob([csvContent], { type: "text/csv;charset=utf-8;" });
    const url = URL.createObjectURL(blob);
    const link = document.createElement("a");
    link.href = url;
    link.setAttribute("download", "garuka_students_template.csv");
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
  };

  return (
    <div className="space-y-6 max-w-6xl">
      <ScopeHeader
        title="Students Directory"
        description="View enrolled pupils, guardian contact linkages, and bulk CSV enrollment."
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
          onClick={() => loadStudents()}
          disabled={loading}
        >
          <RefreshCw className={`h-4 w-4 mr-1.5 ${loading ? "animate-spin" : ""}`} />
          Refresh
        </Button>
        <Button variant="outline" size="sm" onClick={downloadCSVTemplate}>
          <Download className="h-4 w-4 mr-1.5" />
          Template
        </Button>
        <Button
          size="sm"
          onClick={() => {
            setIsModalOpen(true);
            setImportError(null);
            setImportResult(null);
          }}
        >
          <Upload className="h-4 w-4 mr-1.5" />
          Import CSV
        </Button>
      </ScopeHeader>

      {fetchError && (
        <div
          role="alert"
          className="p-4 bg-destructive/15 border border-destructive/20 text-destructive rounded-lg flex items-center justify-between"
        >
          <div className="flex items-center gap-2 text-sm font-medium">
            <AlertTriangle className="h-4 w-4 shrink-0" />
            <span>{fetchError}</span>
          </div>
          <Button variant="outline" size="sm" onClick={() => loadStudents()}>
            Retry
          </Button>
        </div>
      )}

      {/* Search Input */}
      <div className="flex items-center gap-4">
        <input
          type="text"
          placeholder="Search by student or guardian name..."
          value={search}
          onChange={(e) => setSearch(e.target.value)}
          className="max-w-sm w-full px-3 py-2 border rounded-md text-sm bg-background focus:outline-hidden focus:ring-2 focus:ring-primary"
        />
      </div>

      {/* Table */}
      <div className="border rounded-xl bg-card overflow-hidden shadow-xs">
        <div className="overflow-x-auto">
          <table className="w-full text-sm text-left">
            <thead className="bg-muted/50 border-b text-xs uppercase text-muted-foreground font-semibold">
              <tr>
                <th className="px-6 py-4">Roll</th>
                <th className="px-6 py-4">Student Name</th>
                <th className="px-6 py-4">Class</th>
                <th className="px-6 py-4">Birth Year</th>
                <th className="px-6 py-4">Primary Guardian</th>
                <th className="px-6 py-4">Status</th>
              </tr>
            </thead>
            <tbody className="divide-y">
              {loading ? (
                <tr>
                  <td colSpan={6} className="px-6 py-8 text-center text-muted-foreground animate-pulse">
                    Loading student records...
                  </td>
                </tr>
              ) : students.length === 0 ? (
                <tr>
                  <td colSpan={6} className="px-6 py-8 text-center text-muted-foreground">
                    No students found. Use "Import CSV" to enroll your class rosters.
                  </td>
                </tr>
              ) : (
                students.map((student) => (
                  <tr key={student.id} className="hover:bg-muted/20">
                    <td className="px-6 py-4 font-mono text-muted-foreground text-xs">
                      #{student.roll_number}
                    </td>
                    <td className="px-6 py-4 font-medium text-foreground">
                      {student.full_name}
                      {student.student_code && (
                        <span className="block text-xs font-mono text-muted-foreground">
                          {student.student_code}
                        </span>
                      )}
                    </td>
                    <td className="px-6 py-4 text-muted-foreground">
                      {student.class_name || "—"}
                    </td>
                    <td className="px-6 py-4 text-muted-foreground font-mono text-xs">
                      {student.birth_year || "—"}
                    </td>
                    <td className="px-6 py-4">
                      {student.guardians.length > 0 ? (
                        <div>
                          <p className="text-foreground text-xs font-medium">
                            {student.guardians[0].full_name}
                          </p>
                          <p className="text-muted-foreground font-mono text-xs">
                            {student.guardians[0].phone_masked}
                          </p>
                        </div>
                      ) : (
                        <span className="text-xs text-amber-600 font-medium">
                          No guardian linked
                        </span>
                      )}
                    </td>
                    <td className="px-6 py-4">
                      <span
                        className={`inline-flex items-center px-2 py-0.5 rounded-full text-xs font-medium ${
                          student.status === "active"
                            ? "bg-emerald-500/10 text-emerald-600 dark:text-emerald-400"
                            : "bg-muted text-muted-foreground"
                        }`}
                      >
                        {student.status}
                      </span>
                    </td>
                  </tr>
                ))
              )}
            </tbody>
          </table>
        </div>
      </div>

      {/* Accessible CSV Import Modal */}
      <AccessibleModal
        isOpen={isModalOpen}
        onClose={() => {
          setIsModalOpen(false);
          setImportError(null);
        }}
        title="CSV Student Import Wizard"
        description="Upload your standard school roster CSV file."
        maxWidth="lg"
      >
        <div className="space-y-4">
          {importError && (
            <div
              role="alert"
              className="p-3 bg-destructive/15 border border-destructive/20 text-destructive rounded text-xs font-medium flex items-center gap-1.5"
            >
              <AlertTriangle className="h-4 w-4 shrink-0" />
              <span>{importError}</span>
            </div>
          )}

          <p className="text-xs text-muted-foreground leading-relaxed">
            Columns required: <code className="bg-muted px-1 rounded">full_name</code>,{" "}
            <code className="bg-muted px-1 rounded">class_name</code>,{" "}
            <code className="bg-muted px-1 rounded">roll_number</code>,{" "}
            <code className="bg-muted px-1 rounded">guardian_name</code>,{" "}
            <code className="bg-muted px-1 rounded">guardian_phone</code>.
          </p>

          <div className="border border-dashed rounded-lg p-6 text-center space-y-2">
            <input
              type="file"
              accept=".csv"
              onChange={(e) => setFile(e.target.files ? e.target.files[0] : null)}
              className="text-sm file:mr-3 file:py-1.5 file:px-3 file:rounded-md file:border-0 file:text-xs file:font-semibold file:bg-primary file:text-primary-foreground hover:file:opacity-90"
            />
            {file && (
              <p className="text-xs font-mono text-emerald-600 font-medium">
                Selected: {file.name}
              </p>
            )}
          </div>

          {importResult && (
            <div
              className={`p-3 rounded-lg text-xs space-y-1.5 ${
                importResult.errors.length > 0
                  ? "bg-destructive/15 text-destructive border border-destructive/30"
                  : "bg-emerald-500/15 text-emerald-700 dark:text-emerald-400 border border-emerald-500/20"
              }`}
            >
              <p className="font-bold">
                {importResult.errors.length > 0
                  ? "Import Validation Errors:"
                  : "Import Completed Successfully:"}
              </p>
              <p>
                Created: {importResult.created} | Updated: {importResult.updated} | Skipped:{" "}
                {importResult.skipped} | Errors: {importResult.errors.length}
              </p>
              {importResult.errors.map((err, idx) => (
                <p key={idx} className="font-mono">
                  Row {err.row}: {err.message}
                </p>
              ))}
            </div>
          )}

          <div className="flex justify-end gap-2 pt-2 border-t">
            <Button
              variant="outline"
              onClick={() => {
                setIsModalOpen(false);
                setImportError(null);
              }}
            >
              Cancel
            </Button>
            <Button
              variant="outline"
              disabled={!file || importLoading}
              onClick={() => handleImport(true)}
            >
              Dry Run (Validate)
            </Button>
            <Button
              disabled={!file || importLoading}
              onClick={() => handleImport(false)}
            >
              {importLoading ? "Importing..." : "Confirm & Import"}
            </Button>
          </div>
        </div>
      </AccessibleModal>
    </div>
  );
}
