"use client";

import { useEffect, useState } from "react";
import { createSchool, fetchSchools, fetchSectors } from "@/lib/api/client";
import { Button } from "@/components/ui/button";
import { AccessibleModal } from "@/components/ui/modal";
import { ScopeHeader } from "@/components/scope-header";
import { Plus, RefreshCw, AlertTriangle } from "lucide-react";

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
  const [fetchError, setFetchError] = useState<string | null>(null);

  // Create School Modal
  const [isModalOpen, setIsModalOpen] = useState(false);
  const [name, setName] = useState("");
  const [code, setCode] = useState("");
  const [level, setLevel] = useState<"primary" | "secondary" | "both">("both");
  const [sectorId, setSectorId] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [createError, setCreateError] = useState<string | null>(null);

  const loadData = (signal?: AbortSignal) => {
    setLoading(true);
    setFetchError(null);
    Promise.all([fetchSchools(signal), fetchSectors(undefined, signal)])
      .then(([schData, secData]) => {
        setSchools(schData as SchoolItem[]);
        setSectors(secData as SectorItem[]);
        if (secData.length > 0 && !sectorId) {
          setSectorId((secData[0] as SectorItem).id);
        }
      })
      .catch((err) => {
        if (err.name !== "AbortError") {
          setFetchError(err.message || "Failed to load schools");
        }
      })
      .finally(() => setLoading(false));
  };

  useEffect(() => {
    const controller = new AbortController();
    loadData(controller.signal);
    return () => controller.abort();
  }, []);

  const handleCreateSchool = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!sectorId) return;
    setSubmitting(true);
    setCreateError(null);
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
      setCreateError(err instanceof Error ? err.message : "Creation failed");
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <div className="space-y-6 max-w-6xl">
      <ScopeHeader
        title="Schools Directory"
        description="Manage schools participating in the Garuka dropout early-warning system."
        scope={{ level: "national", name: "Rwanda" }}
      >
        <Button
          variant="outline"
          size="sm"
          onClick={() => loadData()}
          disabled={loading}
        >
          <RefreshCw className={`h-4 w-4 mr-1.5 ${loading ? "animate-spin" : ""}`} />
          Refresh
        </Button>
        <Button size="sm" onClick={() => setIsModalOpen(true)}>
          <Plus className="h-4 w-4 mr-1.5" />
          Add School
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
          <Button variant="outline" size="sm" onClick={() => loadData()}>
            Retry
          </Button>
        </div>
      )}

      <div className="border rounded-xl bg-card overflow-hidden shadow-xs">
        <div className="overflow-x-auto">
          <table className="w-full text-sm text-left">
            <thead className="bg-muted/50 border-b text-xs uppercase text-muted-foreground font-semibold">
              <tr>
                <th className="px-6 py-4">School Name</th>
                <th className="px-6 py-4">Code</th>
                <th className="px-6 py-4">Level</th>
                <th className="px-6 py-4">Status</th>
                <th className="px-6 py-4 text-right">Actions</th>
              </tr>
            </thead>
            <tbody className="divide-y">
              {loading ? (
                <tr>
                  <td colSpan={5} className="px-6 py-8 text-center text-muted-foreground animate-pulse">
                    Loading schools list...
                  </td>
                </tr>
              ) : schools.length === 0 ? (
                <tr>
                  <td colSpan={5} className="px-6 py-8 text-center text-muted-foreground">
                    No schools enrolled yet. Click "Add School" to register the first institution.
                  </td>
                </tr>
              ) : (
                schools.map((school) => (
                  <tr key={school.id} className="hover:bg-muted/20">
                    <td className="px-6 py-4 font-medium text-foreground">
                      {school.name}
                    </td>
                    <td className="px-6 py-4 font-mono text-xs text-muted-foreground">
                      {school.code || "—"}
                    </td>
                    <td className="px-6 py-4 capitalize text-muted-foreground">
                      {school.level}
                    </td>
                    <td className="px-6 py-4">
                      <span
                        className={`inline-flex items-center px-2 py-0.5 rounded-full text-xs font-medium ${
                          school.is_active
                            ? "bg-emerald-500/10 text-emerald-600 dark:text-emerald-400"
                            : "bg-muted text-muted-foreground"
                        }`}
                      >
                        {school.is_active ? "Active" : "Inactive"}
                      </span>
                    </td>
                    <td className="px-6 py-4 text-right">
                      <Button variant="ghost" size="sm" className="h-8 text-xs">
                        Configure
                      </Button>
                    </td>
                  </tr>
                ))
              )}
            </tbody>
          </table>
        </div>
      </div>

      {/* Accessible Create School Modal */}
      <AccessibleModal
        isOpen={isModalOpen}
        onClose={() => {
          setIsModalOpen(false);
          setCreateError(null);
        }}
        title="Register New School"
        description="Add a primary or secondary school into Garuka."
      >
        <form onSubmit={handleCreateSchool} className="space-y-4">
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
            <label htmlFor="school-sector" className="text-xs font-semibold uppercase text-muted-foreground">
              Sector
            </label>
            <select
              id="school-sector"
              value={sectorId}
              onChange={(e) => setSectorId(e.target.value)}
              required
              className="w-full px-3 py-2 border rounded-md text-sm bg-background focus:outline-hidden focus:ring-2 focus:ring-primary"
            >
              {sectors.map((sec) => (
                <option key={sec.id} value={sec.id}>
                  {sec.name}
                </option>
              ))}
            </select>
          </div>

          <div className="space-y-1.5">
            <label htmlFor="school-name" className="text-xs font-semibold uppercase text-muted-foreground">
              School Name
            </label>
            <input
              id="school-name"
              type="text"
              required
              value={name}
              onChange={(e) => setName(e.target.value)}
              placeholder="e.g. GS Remera Protestant"
              className="w-full px-3 py-2 border rounded-md text-sm bg-background focus:outline-hidden focus:ring-2 focus:ring-primary"
            />
          </div>

          <div className="space-y-1.5">
            <label htmlFor="school-code" className="text-xs font-semibold uppercase text-muted-foreground">
              School Code
            </label>
            <input
              id="school-code"
              type="text"
              value={code}
              onChange={(e) => setCode(e.target.value)}
              placeholder="e.g. GS_REM_01"
              className="w-full px-3 py-2 border rounded-md text-sm bg-background font-mono focus:outline-hidden focus:ring-2 focus:ring-primary"
            />
          </div>

          <div className="space-y-1.5">
            <label htmlFor="school-level" className="text-xs font-semibold uppercase text-muted-foreground">
              Level
            </label>
            <select
              id="school-level"
              value={level}
              onChange={(e) => setLevel(e.target.value as "primary" | "secondary" | "both")}
              className="w-full px-3 py-2 border rounded-md text-sm bg-background focus:outline-hidden focus:ring-2 focus:ring-primary"
            >
              <option value="primary">Primary</option>
              <option value="secondary">Secondary</option>
              <option value="both">Both (Primary + Secondary)</option>
            </select>
          </div>

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
              {submitting ? "Saving..." : "Save School"}
            </Button>
          </div>
        </form>
      </AccessibleModal>
    </div>
  );
}
