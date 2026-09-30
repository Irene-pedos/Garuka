"use client";

import { useEffect, useState } from "react";
import { useAuth } from "@/lib/auth-context";
import { fetchStudents, uploadStudentsCSV } from "@/lib/api/client";
import { Button } from "@/components/ui/button";

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

  // CSV Import State
  const [isModalOpen, setIsModalOpen] = useState(false);
  const [file, setFile] = useState<File | null>(null);
  const [importLoading, setImportLoading] = useState(false);
  const [importResult, setImportResult] = useState<{
    created: number;
    updated: number;
    skipped: number;
    errors: Array<{ row: number; message: string }>;
  } | null>(null);

  const loadStudents = () => {
    setLoading(true);
    fetchStudents({ q: search || undefined })
      .then((data) => setStudents(data as StudentItem[]))
      .catch((err) => console.error(err))
      .finally(() => setLoading(false));
  };

  useEffect(() => {
    loadStudents();
  }, [search]);

  const handleImport = async (dryRun: boolean) => {
    if (!file) return;
    setImportLoading(true);
    setImportResult(null);
    try {
      const res = await uploadStudentsCSV(file, user?.school_id || undefined, dryRun);
      setImportResult(res);
      if (!dryRun && res.errors.length === 0) {
        loadStudents();
      }
    } catch (err: unknown) {
      alert(err instanceof Error ? err.message : "Import failed");
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
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold tracking-tight">Students</h1>
          <p className="text-sm text-muted-foreground">Manage enrolled students and guardian contact links</p>
        </div>
        <div className="flex gap-2">
          <Button variant="outline" onClick={downloadCSVTemplate}>
            Download Template
          </Button>
          <Button onClick={() => setIsModalOpen(true)}>Import Students (CSV)</Button>
        </div>
      </div>

      <div className="flex items-center gap-4">
        <input
          type="text"
          placeholder="Search by student name or SDMS code..."
          value={search}
          onChange={(e) => setSearch(e.target.value)}
          className="max-w-sm px-3 py-2 border rounded-md text-sm bg-background w-full focus:outline-none focus:ring-2 focus:ring-primary"
        />
      </div>

      <div className="border rounded-xl bg-card overflow-hidden shadow-sm">
        <div className="overflow-x-auto">
          <table className="w-full text-sm text-left">
            <thead className="bg-muted text-muted-foreground uppercase text-xs border-b">
              <tr>
                <th className="px-4 py-3">Roll</th>
                <th className="px-4 py-3">Full Name</th>
                <th className="px-4 py-3">Class</th>
                <th className="px-4 py-3">SDMS Code</th>
                <th className="px-4 py-3">Sex / Year</th>
                <th className="px-4 py-3">Primary Guardian</th>
                <th className="px-4 py-3">Status</th>
              </tr>
            </thead>
            <tbody className="divide-y">
              {loading ? (
                <tr>
                  <td colSpan={7} className="text-center py-8 text-muted-foreground">
                    Loading students...
                  </td>
                </tr>
              ) : students.length === 0 ? (
                <tr>
                  <td colSpan={7} className="text-center py-8 text-muted-foreground">
                    No students found. Use &quot;Import Students&quot; to load classes.
                  </td>
                </tr>
              ) : (
                students.map((s) => (
                  <tr key={s.id} className="hover:bg-muted/30">
                    <td className="px-4 py-3 font-mono font-medium">{s.roll_number}</td>
                    <td className="px-4 py-3 font-semibold text-foreground">{s.full_name}</td>
                    <td className="px-4 py-3 font-medium text-primary">{s.class_name || "—"}</td>
                    <td className="px-4 py-3 font-mono text-xs text-muted-foreground">{s.student_code || "—"}</td>
                    <td className="px-4 py-3 text-muted-foreground">
                      {s.sex || "—"} {s.birth_year ? `(${s.birth_year})` : ""}
                    </td>
                    <td className="px-4 py-3">
                      {s.guardians && s.guardians.length > 0 ? (
                        <div>
                          <p className="font-medium">{s.guardians[0].full_name}</p>
                          <p className="text-xs font-mono text-muted-foreground">{s.guardians[0].phone_masked}</p>
                        </div>
                      ) : (
                        <span className="text-muted-foreground text-xs italic">No guardian linked</span>
                      )}
                    </td>
                    <td className="px-4 py-3">
                      <span className="inline-flex items-center px-2 py-0.5 rounded-full text-xs font-medium bg-emerald-100 text-emerald-800 dark:bg-emerald-950 dark:text-emerald-300">
                        {s.status}
                      </span>
                    </td>
                  </tr>
                ))
              )}
            </tbody>
          </table>
        </div>
      </div>

      {/* CSV Import Modal */}
      {isModalOpen && (
        <div className="fixed inset-0 z-50 bg-black/50 flex items-center justify-center p-4">
          <div className="bg-card border rounded-xl max-w-lg w-full p-6 shadow-xl space-y-4">
            <div className="flex items-center justify-between border-b pb-3">
              <h2 className="font-bold text-lg">CSV Student Import Wizard</h2>
              <button
                onClick={() => setIsModalOpen(false)}
                className="text-muted-foreground hover:text-foreground text-sm"
              >
                ✕
              </button>
            </div>

            <p className="text-xs text-muted-foreground leading-relaxed">
              Upload standard format CSV. Columns required: <code className="bg-muted px-1 rounded">full_name</code>,{" "}
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
              {file && <p className="text-xs font-mono text-emerald-600 font-medium">Selected: {file.name}</p>}
            </div>

            {importResult && (
              <div
                className={`p-3 rounded-lg text-xs space-y-1.5 ${
                  importResult.errors.length > 0
                    ? "bg-destructive/15 text-destructive border border-destructive/30"
                    : "bg-emerald-100 text-emerald-900 border border-emerald-300"
                }`}
              >
                <p className="font-bold">
                  {importResult.errors.length > 0 ? "Import Validation Errors:" : "Import Result:"}
                </p>
                <p>
                  Created: {importResult.created} | Updated: {importResult.updated} | Errors:{" "}
                  {importResult.errors.length}
                </p>
                {importResult.errors.map((err, idx) => (
                  <p key={idx} className="font-mono">
                    Row {err.row}: {err.message}
                  </p>
                ))}
              </div>
            )}

            <div className="flex justify-end gap-2 pt-2 border-t">
              <Button variant="outline" onClick={() => setIsModalOpen(false)}>
                Cancel
              </Button>
              <Button
                variant="outline"
                disabled={!file || importLoading}
                onClick={() => handleImport(true)}
              >
                Dry Run (Validate)
              </Button>
              <Button disabled={!file || importLoading} onClick={() => handleImport(false)}>
                {importLoading ? "Importing..." : "Confirm & Import"}
              </Button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
