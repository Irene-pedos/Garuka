"use client";

import { useEffect, useState } from "react";
import { useAuth } from "@/lib/auth-context";
import {
  fetchHelpRequests,
  updateHelpRequestStatus,
  type HelpRequestItem,
} from "@/lib/api/client";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { ScopeHeader } from "@/components/scope-header";

const BARRIER_LABELS: Record<string, string> = {
  COST: "Fees / Materials",
  HUNGER: "Food / Hunger",
  HEALTH: "Health / Medical",
  DISTANCE: "Distance / Transport",
  FAMILY: "Family situation",
  OTHER: "Other barrier",
};

const STATUS_COLORS: Record<string, "destructive" | "default" | "secondary" | "outline"> = {
  new: "destructive",
  seen: "secondary",
  in_progress: "default",
  closed: "outline",
};

export default function HelpRequestsPage() {
  const { user } = useAuth();
  const [requests, setRequests] = useState<HelpRequestItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [statusFilter, setStatusFilter] = useState<string>("all");
  const [barrierFilter, setBarrierFilter] = useState<string>("all");
  const [search, setSearch] = useState("");
  const [updatingId, setUpdatingId] = useState<string | null>(null);

  const loadRequests = () => {
    setLoading(true);
    setError(null);
    fetchHelpRequests({
      status: statusFilter !== "all" ? statusFilter : undefined,
      barrier_code: barrierFilter !== "all" ? barrierFilter : undefined,
    })
      .then((data) => setRequests(data as HelpRequestItem[]))
      .catch((err) => {
        console.error(err);
        setError("Failed to load help requests.");
      })
      .finally(() => setLoading(false));
  };

  useEffect(() => {
    loadRequests();
  }, [statusFilter, barrierFilter]);

  const handleStatusChange = async (
    id: string,
    newStatus: "new" | "seen" | "in_progress" | "closed"
  ) => {
    setUpdatingId(id);
    setError(null);
    try {
      await updateHelpRequestStatus(id, newStatus);
      setRequests((prev) =>
        prev.map((r) => (r.id === id ? { ...r, status: newStatus } : r))
      );
    } catch (err: any) {
      setError(err.message || "Failed to update help request status");
    } finally {
      setUpdatingId(null);
    }
  };

  const filteredRequests = requests.filter((r) => {
    if (!search.trim()) return true;
    const q = search.toLowerCase();
    return (
      r.student_name.toLowerCase().includes(q) ||
      r.guardian_name.toLowerCase().includes(q) ||
      r.school_name.toLowerCase().includes(q)
    );
  });

  return (
    <div className="space-y-6 max-w-6xl">
      <ScopeHeader
        title="Parent Help Requests"
        description="Inquiries and barrier assistance requested by parents via USSD."
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
          onClick={loadRequests}
          disabled={loading || !!updatingId}
        >
          Refresh
        </Button>
      </ScopeHeader>

      <div className="flex flex-wrap items-center gap-3">
        <Input
          placeholder="Search student, guardian, school..."
          value={search}
          onChange={(e) => setSearch(e.target.value)}
          className="max-w-xs"
        />

        <select
          value={statusFilter}
          onChange={(e) => setStatusFilter(e.target.value)}
          className="h-9 px-3 rounded-md border text-sm bg-background text-foreground"
        >
          <option value="all">All Statuses</option>
          <option value="new">New</option>
          <option value="seen">Seen</option>
          <option value="in_progress">In Progress</option>
          <option value="closed">Closed</option>
        </select>

        <select
          value={barrierFilter}
          onChange={(e) => setBarrierFilter(e.target.value)}
          className="h-9 px-3 rounded-md border text-sm bg-background text-foreground"
        >
          <option value="all">All Barriers</option>
          <option value="COST">Fees / Materials</option>
          <option value="HUNGER">Food / Hunger</option>
          <option value="HEALTH">Health</option>
          <option value="DISTANCE">Distance</option>
          <option value="FAMILY">Family</option>
          <option value="OTHER">Other</option>
        </select>
      </div>

      {error && (
        <div className="p-3 text-sm bg-destructive/15 text-destructive rounded-md">
          {error}
        </div>
      )}

      <Card>
        <CardHeader className="py-4">
          <CardTitle className="text-base font-medium">
            Inbox ({filteredRequests.length})
          </CardTitle>
        </CardHeader>
        <CardContent className="p-0">
          {loading ? (
            <div className="p-8 text-center text-sm text-muted-foreground animate-pulse">
              Loading help requests...
            </div>
          ) : filteredRequests.length === 0 ? (
            <div className="p-8 text-center text-sm text-muted-foreground">
              No help requests found.
            </div>
          ) : (
            <div className="overflow-x-auto">
              <table className="w-full text-left text-sm">
                <thead className="bg-muted/50 border-b text-xs uppercase text-muted-foreground">
                  <tr>
                    <th className="px-4 py-3 font-medium">Date</th>
                    <th className="px-4 py-3 font-medium">Student</th>
                    <th className="px-4 py-3 font-medium">School</th>
                    <th className="px-4 py-3 font-medium">Guardian</th>
                    <th className="px-4 py-3 font-medium">Barrier</th>
                    <th className="px-4 py-3 font-medium">Status</th>
                    <th className="px-4 py-3 font-medium text-right">Actions</th>
                  </tr>
                </thead>
                <tbody className="divide-y">
                  {filteredRequests.map((req) => (
                    <tr key={req.id} className="hover:bg-muted/20">
                      <td className="px-4 py-3 text-muted-foreground whitespace-nowrap">
                        {new Date(req.created_at).toLocaleDateString()}
                      </td>
                      <td className="px-4 py-3">
                        <div className="font-medium text-foreground">
                          {req.student_name}
                        </div>
                        {req.class_name && (
                          <div className="text-xs text-muted-foreground">
                            {req.class_name}
                          </div>
                        )}
                      </td>
                      <td className="px-4 py-3 text-muted-foreground whitespace-nowrap">
                        {req.school_name}
                      </td>
                      <td className="px-4 py-3">
                        <div className="font-medium">{req.guardian_name}</div>
                        <div className="text-xs text-muted-foreground font-mono">
                          {req.guardian_phone}
                        </div>
                      </td>
                      <td className="px-4 py-3">
                        <span className="inline-block px-2 py-0.5 rounded text-xs bg-muted font-medium">
                          {BARRIER_LABELS[req.barrier_code] || req.barrier_code}
                        </span>
                      </td>
                      <td className="px-4 py-3">
                        <Badge variant={STATUS_COLORS[req.status] || "default"}>
                          {req.status.replace("_", " ")}
                        </Badge>
                      </td>
                      <td className="px-4 py-3 text-right whitespace-nowrap space-x-1">
                        {req.status === "new" && (
                          <Button
                            size="sm"
                            variant="outline"
                            disabled={updatingId === req.id}
                            onClick={() => handleStatusChange(req.id, "seen")}
                          >
                            Mark Seen
                          </Button>
                        )}
                        {(req.status === "new" || req.status === "seen") && (
                          <Button
                            size="sm"
                            variant="secondary"
                            disabled={updatingId === req.id}
                            onClick={() => handleStatusChange(req.id, "in_progress")}
                          >
                            In Progress
                          </Button>
                        )}
                        {req.status !== "closed" && (
                          <Button
                            size="sm"
                            variant="outline"
                            disabled={updatingId === req.id}
                            onClick={() => handleStatusChange(req.id, "closed")}
                          >
                            Close
                          </Button>
                        )}
                        {req.status === "closed" && (
                          <span className="text-xs text-muted-foreground">Resolved</span>
                        )}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </CardContent>
      </Card>
    </div>
  );
}
