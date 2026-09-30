"use client";

import { useEffect, useState } from "react";
import { createSchool, fetchSchools, fetchSectors } from "@/lib/api/client";
import { Button } from "@/components/ui/button";

interface SchoolItem {
  id: string;
  name: string;
  code?: string | null;
  level: "primary" | "secondary" | "both";
  is_active: boolean;
}

interface SectorItem {
  id: string;
  name: string;
}

export default function SchoolsPage() {
  const [schools, setSchools] = useState<SchoolItem[]>([]);
  const [sectors, setSectors] = useState<SectorItem[]>([]);
  const [loading, setLoading] = useState(true);

  // Create School Modal
  const [isModalOpen, setIsModalOpen] = useState(false);
  const [name, setName] = useState("");
  const [code, setCode] = useState("");
  const [level, setLevel] = useState<"primary" | "secondary" | "both">("both");
  const [sectorId, setSectorId] = useState("");
  const [submitting, setSubmitting] = useState(false);

  const loadData = () => {
    setLoading(true);
    Promise.all([fetchSchools(), fetchSectors()])
      .then(([schData, secData]) => {
        setSchools(schData as SchoolItem[]);
        setSectors(secData as SectorItem[]);
        if (secData.length > 0 && !sectorId) {
          setSectorId(secData[0].id);
        }
      })
      .catch((err) => console.error(err))
      .finally(() => setLoading(false));
  };

  useEffect(() => {
    loadData();
  }, []);

  const handleCreateSchool = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!sectorId) return;
    setSubmitting(true);
    try {
      await createSchool({
        sector_id: sectorId,
        name,
        code: code || undefined,
        level,
      });
      setIsModalOpen(false);
      setName("");
      setCode("");
      loadData();
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
          <h1 className="text-2xl font-bold tracking-tight">Schools</h1>
          <p className="text-sm text-muted-foreground">Manage schools participating in the Garuka dropout early-warning system</p>
        </div>
        <Button onClick={() => setIsModalOpen(true)}>Add School</Button>
      </div>

      <div className="border rounded-xl bg-card overflow-hidden shadow-sm">
        <div className="overflow-x-auto">
          <table className="w-full text-sm text-left">
            <thead className="bg-muted text-muted-foreground uppercase text-xs border-b">
              <tr>
                <th className="px-4 py-3">School Name</th>
                <th className="px-4 py-3">School Code</th>
                <th className="px-4 py-3">Level</th>
                <th className="px-4 py-3">Status</th>
              </tr>
            </thead>
            <tbody className="divide-y">
              {loading ? (
                <tr>
                  <td colSpan={4} className="text-center py-8 text-muted-foreground">
                    Loading schools...
                  </td>
                </tr>
              ) : (
                schools.map((s) => (
                  <tr key={s.id} className="hover:bg-muted/30">
                    <td className="px-4 py-3 font-semibold text-foreground">{s.name}</td>
                    <td className="px-4 py-3 font-mono text-xs text-muted-foreground">{s.code || "—"}</td>
                    <td className="px-4 py-3 capitalize text-muted-foreground">{s.level}</td>
                    <td className="px-4 py-3">
                      <span
                        className={`inline-flex items-center px-2 py-0.5 rounded-full text-xs font-medium ${
                          s.is_active
                            ? "bg-emerald-100 text-emerald-800 dark:bg-emerald-950 dark:text-emerald-300"
                            : "bg-muted text-muted-foreground"
                        }`}
                      >
                        {s.is_active ? "Active" : "Inactive"}
                      </span>
                    </td>
                  </tr>
                ))
              )}
            </tbody>
          </table>
        </div>
      </div>

      {/* Create School Modal */}
      {isModalOpen && (
        <div className="fixed inset-0 z-50 bg-black/50 flex items-center justify-center p-4">
          <div className="bg-card border rounded-xl max-w-md w-full p-6 shadow-xl space-y-4">
            <div className="flex items-center justify-between border-b pb-3">
              <h2 className="font-bold text-lg">Add New School</h2>
              <button
                onClick={() => setIsModalOpen(false)}
                className="text-muted-foreground hover:text-foreground text-sm"
              >
                ✕
              </button>
            </div>

            <form onSubmit={handleCreateSchool} className="space-y-3">
              <div className="space-y-1">
                <label className="text-xs font-semibold uppercase text-muted-foreground">Sector</label>
                <select
                  value={sectorId}
                  onChange={(e) => setSectorId(e.target.value)}
                  required
                  className="w-full px-3 py-2 border rounded-md text-sm bg-background"
                >
                  {sectors.map((sec) => (
                    <option key={sec.id} value={sec.id}>
                      {sec.name}
                    </option>
                  ))}
                </select>
              </div>

              <div className="space-y-1">
                <label className="text-xs font-semibold uppercase text-muted-foreground">School Name</label>
                <input
                  type="text"
                  required
                  value={name}
                  onChange={(e) => setName(e.target.value)}
                  placeholder="GS Demo 3"
                  className="w-full px-3 py-2 border rounded-md text-sm bg-background"
                />
              </div>

              <div className="space-y-1">
                <label className="text-xs font-semibold uppercase text-muted-foreground">School Code</label>
                <input
                  type="text"
                  value={code}
                  onChange={(e) => setCode(e.target.value)}
                  placeholder="GSD3"
                  className="w-full px-3 py-2 border rounded-md text-sm bg-background font-mono"
                />
              </div>

              <div className="space-y-1">
                <label className="text-xs font-semibold uppercase text-muted-foreground">Level</label>
                <select
                  value={level}
                  onChange={(e) => setLevel(e.target.value as "primary" | "secondary" | "both")}
                  className="w-full px-3 py-2 border rounded-md text-sm bg-background"
                >
                  <option value="primary">Primary</option>
                  <option value="secondary">Secondary</option>
                  <option value="both">Both (Primary + Secondary)</option>
                </select>
              </div>

              <div className="flex justify-end gap-2 pt-3 border-t">
                <Button variant="outline" type="button" onClick={() => setIsModalOpen(false)}>
                  Cancel
                </Button>
                <Button type="submit" disabled={submitting}>
                  {submitting ? "Saving..." : "Save School"}
                </Button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  );
}
