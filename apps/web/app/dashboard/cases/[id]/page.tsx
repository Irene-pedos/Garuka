"use client";

import { use, useEffect, useState } from "react";
import Link from "next/link";
import {
  addCaseNote,
  assignCaseMentor,
  escalateCase,
  fetchCaseDetail,
  fetchMentors,
  resolveCase,
} from "@/lib/api/client";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { AccessibleModal } from "@/components/ui/modal";

export default function CaseDetailPage({ params }: { params: Promise<{ id: string }> }) {
  const resolvedParams = use(params);
  const caseId = resolvedParams.id;

  const [caseData, setCaseData] = useState<any>(null);
  const [mentors, setMentors] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  // Action states
  const [actionLoading, setActionLoading] = useState(false);
  const [actionError, setActionError] = useState<string | null>(null);
  const [selectedMentorId, setSelectedMentorId] = useState("");
  const [escalateNote, setEscalateNote] = useState("");
  const [newNote, setNewNote] = useState("");
  const [resolveOutcome, setResolveOutcome] = useState("resolved_returned");
  const [resolveNote, setResolveNote] = useState("");

  // Modals / toggles
  const [showAssignModal, setShowAssignModal] = useState(false);
  const [showEscalateModal, setShowEscalateModal] = useState(false);
  const [showNoteModal, setShowNoteModal] = useState(false);
  const [showResolveModal, setShowResolveModal] = useState(false);

  const loadData = async () => {
    setLoading(true);
    setError(null);
    try {
      const [detail, mentorList] = await Promise.all([
        fetchCaseDetail(caseId),
        fetchMentors().catch(() => []),
      ]);
      setCaseData(detail);
      setMentors(mentorList);
      if (detail.mentor_id) {
        setSelectedMentorId(detail.mentor_id);
      }
    } catch (err: any) {
      setError(err.message || "Failed to load case detail");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadData();
  }, [caseId]);

  const handleAssignMentor = async () => {
    if (!selectedMentorId) return;
    setActionLoading(true);
    setActionError(null);
    try {
      const updated = await assignCaseMentor(caseId, selectedMentorId);
      setCaseData(updated);
      setShowAssignModal(false);
    } catch (err: any) {
      setActionError(err.message || "Failed to assign mentor");
    } finally {
      setActionLoading(false);
    }
  };

  const handleEscalate = async () => {
    setActionLoading(true);
    setActionError(null);
    try {
      const updated = await escalateCase(caseId, 3, escalateNote);
      setCaseData(updated);
      setShowEscalateModal(false);
      setEscalateNote("");
    } catch (err: any) {
      setActionError(err.message || "Failed to escalate case");
    } finally {
      setActionLoading(false);
    }
  };

  const handleAddNote = async () => {
    if (!newNote.trim()) return;
    setActionLoading(true);
    setActionError(null);
    try {
      const updated = await addCaseNote(caseId, newNote.trim());
      setCaseData(updated);
      setShowNoteModal(false);
      setNewNote("");
    } catch (err: any) {
      setActionError(err.message || "Failed to add note");
    } finally {
      setActionLoading(false);
    }
  };

  const handleResolve = async () => {
    setActionLoading(true);
    setActionError(null);
    try {
      const updated = await resolveCase(caseId, resolveOutcome, resolveNote);
      setCaseData(updated);
      setShowResolveModal(false);
      setResolveNote("");
    } catch (err: any) {
      setActionError(err.message || "Failed to resolve case");
    } finally {
      setActionLoading(false);
    }
  };

  if (loading) {
    return (
      <div className="py-12 text-center text-sm text-muted-foreground animate-pulse">
        Loading case file {caseId}...
      </div>
    );
  }

  if (error || !caseData) {
    return (
      <div className="space-y-4">
        <Link href="/dashboard/cases" className="text-xs text-primary hover:underline">
          &larr; Back to Cases
        </Link>
        <div className="p-4 rounded-lg bg-destructive/10 text-destructive text-sm">
          {error || "Case not found"}
        </div>
      </div>
    );
  }

  const isClosed =
    caseData.status === "resolved_returned" ||
    caseData.status === "closed_moved" ||
    caseData.status === "closed_other";

  return (
    <div className="space-y-6">
      {/* Breadcrumb & Navigation */}
      <div className="flex items-center justify-between">
        <Link
          href="/dashboard/cases"
          className="text-xs font-semibold text-muted-foreground hover:text-foreground"
        >
          &larr; Back to Cases
        </Link>
        <div className="flex items-center gap-2">
          {!isClosed && (
            <>
              <Button
                variant="outline"
                size="sm"
                onClick={() => setShowAssignModal(true)}
              >
                {caseData.mentor_name ? "Reassign Mentor" : "Assign Mentor"}
              </Button>
              {caseData.level === 2 && (
                <Button
                  variant="outline"
                  size="sm"
                  onClick={() => setShowEscalateModal(true)}
                  className="border-amber-500 text-amber-600 hover:bg-amber-50"
                >
                  Escalate to Level 3
                </Button>
              )}
              <Button
                variant="secondary"
                size="sm"
                onClick={() => setShowNoteModal(true)}
              >
                + Add Note
              </Button>
              <Button
                variant="default"
                size="sm"
                onClick={() => setShowResolveModal(true)}
                className="bg-emerald-600 hover:bg-emerald-700"
              >
                Resolve Case
              </Button>
            </>
          )}
          {isClosed && (
            <Badge className="bg-emerald-600">Case Resolved / Closed</Badge>
          )}
        </div>
      </div>

      {/* Case Header Card */}
      <Card className="bg-card">
        <CardContent className="pt-6">
          <div className="flex flex-col md:flex-row md:items-center justify-between gap-4">
            <div>
              <div className="flex items-center gap-3">
                <h1 className="text-2xl font-bold tracking-tight">{caseData.student_name}</h1>
                <span className="font-mono text-sm px-2 py-0.5 rounded bg-muted text-muted-foreground">
                  {caseData.ref}
                </span>
                <Badge variant={caseData.level === 3 ? "destructive" : "secondary"}>
                  Level {caseData.level}
                </Badge>
              </div>
              <p className="text-xs text-muted-foreground mt-1">
                {caseData.school_name} &bull; {caseData.class_name || "Primary Class"} &bull;{" "}
                Gender: {caseData.student_gender || "N/A"}
              </p>
            </div>

            <div className="flex items-center gap-6">
              <div className="text-right">
                <span className="text-xs text-muted-foreground block">Guardian / Parent</span>
                <span className="text-sm font-medium">{caseData.parent_name || "Family Guardian"}</span>
                <span className="text-xs text-muted-foreground block">{caseData.parent_phone || "No phone"}</span>
              </div>
              <div className="text-right pl-4 border-l">
                <span className="text-xs text-muted-foreground block">Assigned Mentor</span>
                <span className="text-sm font-semibold text-primary">
                  {caseData.mentor_name || "Unassigned"}
                </span>
              </div>
            </div>
          </div>
        </CardContent>
      </Card>

      {/* 4 Metrics Cards */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
        <Card>
          <CardHeader className="pb-2">
            <CardTitle className="text-xs font-medium text-muted-foreground">
              Consecutive Absences
            </CardTitle>
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold text-destructive">
              {caseData.metrics?.consecutive_absences ?? 0} days
            </div>
          </CardContent>
        </Card>

        <Card>
          <CardHeader className="pb-2">
            <CardTitle className="text-xs font-medium text-muted-foreground">
              30-Day Absences
            </CardTitle>
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold">
              {caseData.metrics?.monthly_absences ?? 0} days
            </div>
          </CardContent>
        </Card>

        <Card>
          <CardHeader className="pb-2">
            <CardTitle className="text-xs font-medium text-muted-foreground">
              Term Absences
            </CardTitle>
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold">
              {caseData.metrics?.term_absences ?? 0} days
            </div>
          </CardContent>
        </Card>

        <Card>
          <CardHeader className="pb-2">
            <CardTitle className="text-xs font-medium text-muted-foreground">
              Return Streak
            </CardTitle>
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold text-emerald-600">
              {caseData.metrics?.return_streak ?? 0} / 10 days
            </div>
          </CardContent>
        </Card>
      </div>

      {/* Main Content: Left Column (Visits & Heatmap), Right Column (Timeline Events) */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Left Column (2 Cols) */}
        <div className="lg:col-span-2 space-y-6">
          {/* Mentor Visits */}
          <Card>
            <CardHeader className="flex flex-row items-center justify-between pb-2">
              <CardTitle className="text-base font-semibold">Home Visits ({caseData.visits?.length || 0})</CardTitle>
            </CardHeader>
            <CardContent>
              {caseData.visits?.length === 0 ? (
                <p className="text-xs text-muted-foreground py-4">
                  No mentor home visits logged yet. The assigned mentor can visit and record findings via USSD.
                </p>
              ) : (
                <div className="space-y-3">
                  {caseData.visits.map((v: any) => (
                    <div
                      key={v.id}
                      className="p-3 rounded-lg border bg-muted/40 text-xs space-y-1.5"
                    >
                      <div className="flex items-center justify-between">
                        <span className="font-semibold text-foreground">
                          Visited by {v.mentor_name}
                        </span>
                        <span className="text-muted-foreground">
                          {new Date(v.started_at).toLocaleString()}
                        </span>
                      </div>
                      <div className="flex flex-wrap items-center gap-2 pt-1">
                        {v.verified ? (
                          <Badge className="bg-emerald-600 text-[10px]">Verified with Parent Code</Badge>
                        ) : (
                          <Badge variant="outline" className="text-[10px]">Unverified</Badge>
                        )}
                        <Badge variant="secondary" className="text-[10px]">
                          Outcome: {v.outcome.replace(/_/g, " ")}
                        </Badge>
                        {v.barrier_code && (
                          <Badge variant="outline" className="text-[10px] border-amber-500 text-amber-600">
                            Barrier: {v.barrier_code}
                          </Badge>
                        )}
                      </div>
                      {v.notes && <p className="text-muted-foreground pt-1">{v.notes}</p>}
                    </div>
                  ))}
                </div>
              )}
            </CardContent>
          </Card>

          {/* Attendance Heatmap */}
          <Card>
            <CardHeader className="pb-2">
              <CardTitle className="text-base font-semibold">Recent Attendance Records (Last 30 days)</CardTitle>
            </CardHeader>
            <CardContent>
              {caseData.absence_heatmap?.length === 0 ? (
                <p className="text-xs text-muted-foreground py-4">
                  No absence records recorded for this student in the current window.
                </p>
              ) : (
                <div className="grid grid-cols-2 sm:grid-cols-3 md:grid-cols-4 gap-2">
                  {caseData.absence_heatmap.map((r: any, idx: number) => (
                    <div
                      key={idx}
                      className={`p-2 rounded border text-xs flex flex-col justify-between ${
                        r.status === "active"
                          ? "bg-red-50/50 border-red-200 dark:bg-red-950/20 dark:border-red-900"
                          : "bg-muted/40"
                      }`}
                    >
                      <span className="font-semibold text-[11px]">{r.date}</span>
                      <div className="mt-1 flex items-center justify-between">
                        <span className="text-red-600 font-bold uppercase text-[10px]">
                          {r.status === "active" ? "Absent" : r.status}
                        </span>
                        {r.reason && (
                          <span className="text-[10px] bg-background px-1.5 py-0.5 rounded border">
                            {r.reason}
                          </span>
                        )}
                      </div>
                    </div>
                  ))}
                </div>
              )}
            </CardContent>
          </Card>
        </div>

        {/* Right Column: Case Events Timeline */}
        <div className="space-y-6">
          <Card>
            <CardHeader className="pb-2">
              <CardTitle className="text-base font-semibold">Audit Timeline</CardTitle>
            </CardHeader>
            <CardContent>
              {caseData.events?.length === 0 ? (
                <p className="text-xs text-muted-foreground py-4">No events logged.</p>
              ) : (
                <div className="relative pl-4 border-l border-muted space-y-4 text-xs">
                  {caseData.events.map((ev: any) => (
                    <div key={ev.id} className="relative">
                      <div className="absolute -left-[21px] top-1 h-2.5 w-2.5 rounded-full bg-primary" />
                      <div className="flex items-center justify-between">
                        <span className="font-semibold uppercase tracking-wider text-[10px] text-foreground">
                          {ev.type.replace(/_/g, " ")}
                        </span>
                        <span className="text-[10px] text-muted-foreground">
                          {new Date(ev.created_at).toLocaleDateString()}
                        </span>
                      </div>
                      {ev.actor_name && (
                        <p className="text-muted-foreground text-[11px]">By {ev.actor_name}</p>
                      )}
                      {ev.payload?.note && (
                        <p className="mt-1 bg-muted p-2 rounded text-[11px] italic">
                          &ldquo;{ev.payload.note}&rdquo;
                        </p>
                      )}
                      {ev.payload?.reason && (
                        <p className="mt-1 text-[11px] text-muted-foreground">
                          Reason: {ev.payload.reason}
                        </p>
                      )}
                    </div>
                  ))}
                </div>
              )}
            </CardContent>
          </Card>
        </div>
      </div>

      {/* Assign Mentor Modal */}
      <AccessibleModal
        isOpen={showAssignModal}
        onClose={() => {
          setShowAssignModal(false);
          setActionError(null);
        }}
        title="Assign Community Mentor"
        description="Select an active mentor from the community to follow up on this student."
      >
        <div className="space-y-4">
          {actionError && (
            <div role="alert" className="p-3 bg-destructive/15 border border-destructive/20 text-destructive rounded text-xs">
              {actionError}
            </div>
          )}
          <select
            aria-label="Select community mentor"
            value={selectedMentorId}
            onChange={(e) => setSelectedMentorId(e.target.value)}
            className="w-full text-sm border rounded px-3 py-2 bg-background focus:outline-hidden focus:ring-2 focus:ring-primary"
          >
            <option value="">-- Choose a mentor --</option>
            {mentors.map((m) => (
              <option key={m.id} value={m.id}>
                {m.name} ({m.active_cases} active cases, {m.sector_name || "Sector"})
              </option>
            ))}
          </select>
          <div className="flex justify-end gap-2 pt-2">
            <Button
              variant="outline"
              size="sm"
              onClick={() => {
                setShowAssignModal(false);
                setActionError(null);
              }}
            >
              Cancel
            </Button>
            <Button
              size="sm"
              disabled={!selectedMentorId || actionLoading}
              onClick={handleAssignMentor}
            >
              {actionLoading ? "Saving..." : "Confirm Assignment"}
            </Button>
          </div>
        </div>
      </AccessibleModal>

      {/* Escalate Modal */}
      <AccessibleModal
        isOpen={showEscalateModal}
        onClose={() => {
          setShowEscalateModal(false);
          setActionError(null);
        }}
        title="Escalate to Level 3 (Sector Officer)"
        description="This will notify the Sector Education Officer (SEO) that school-level and mentor interventions require sector administrative support."
      >
        <div className="space-y-4">
          {actionError && (
            <div role="alert" className="p-3 bg-destructive/15 border border-destructive/20 text-destructive rounded text-xs">
              {actionError}
            </div>
          )}
          <Input
            aria-label="Reason for escalation"
            placeholder="Reason / context for escalation..."
            value={escalateNote}
            onChange={(e) => setEscalateNote(e.target.value)}
          />
          <div className="flex justify-end gap-2 pt-2">
            <Button
              variant="outline"
              size="sm"
              onClick={() => {
                setShowEscalateModal(false);
                setActionError(null);
              }}
            >
              Cancel
            </Button>
            <Button
              variant="destructive"
              size="sm"
              disabled={actionLoading}
              onClick={handleEscalate}
            >
              {actionLoading ? "Escalating..." : "Confirm Escalation"}
            </Button>
          </div>
        </div>
      </AccessibleModal>

      {/* Add Note Modal */}
      <AccessibleModal
        isOpen={showNoteModal}
        onClose={() => {
          setShowNoteModal(false);
          setActionError(null);
        }}
        title="Add Audit Note"
        description="Add operational follow-up notes, observations, or action items."
      >
        <div className="space-y-4">
          {actionError && (
            <div role="alert" className="p-3 bg-destructive/15 border border-destructive/20 text-destructive rounded text-xs">
              {actionError}
            </div>
          )}
          <textarea
            aria-label="Audit note text"
            rows={3}
            placeholder="Write follow-up notes, observations, or action items..."
            value={newNote}
            onChange={(e) => setNewNote(e.target.value)}
            className="w-full text-sm border rounded px-3 py-2 bg-background focus:outline-hidden focus:ring-2 focus:ring-primary"
          />
          <div className="flex justify-end gap-2 pt-2">
            <Button
              variant="outline"
              size="sm"
              onClick={() => {
                setShowNoteModal(false);
                setActionError(null);
              }}
            >
              Cancel
            </Button>
            <Button
              size="sm"
              disabled={!newNote.trim() || actionLoading}
              onClick={handleAddNote}
            >
              {actionLoading ? "Saving..." : "Save Note"}
            </Button>
          </div>
        </div>
      </AccessibleModal>

      {/* Resolve Case Modal */}
      <AccessibleModal
        isOpen={showResolveModal}
        onClose={() => {
          setShowResolveModal(false);
          setActionError(null);
        }}
        title="Resolve / Close Case"
        description="Select resolution outcome and summarize the resolution."
      >
        <div className="space-y-4">
          {actionError && (
            <div role="alert" className="p-3 bg-destructive/15 border border-destructive/20 text-destructive rounded text-xs">
              {actionError}
            </div>
          )}
          <div className="space-y-1.5">
            <label className="text-xs font-semibold">Outcome</label>
            <select
              value={resolveOutcome}
              onChange={(e) => setResolveOutcome(e.target.value)}
              className="w-full text-sm border rounded px-3 py-2 bg-background focus:outline-hidden focus:ring-2 focus:ring-primary"
            >
              <option value="resolved_returned">Student Returned to School</option>
              <option value="closed_moved">Student Moved / Transferred</option>
              <option value="closed_other">Closed Other</option>
            </select>
          </div>
          <div className="space-y-1.5">
            <label className="text-xs font-semibold">Notes</label>
            <Input
              placeholder="Resolution summary..."
              value={resolveNote}
              onChange={(e) => setResolveNote(e.target.value)}
            />
          </div>
          <div className="flex justify-end gap-2 pt-2">
            <Button
              variant="outline"
              size="sm"
              onClick={() => {
                setShowResolveModal(false);
                setActionError(null);
              }}
            >
              Cancel
            </Button>
            <Button
              size="sm"
              className="bg-emerald-600 hover:bg-emerald-700"
              disabled={actionLoading}
              onClick={handleResolve}
            >
              {actionLoading ? "Resolving..." : "Confirm Resolution"}
            </Button>
          </div>
        </div>
      </AccessibleModal>
    </div>
  );
}
