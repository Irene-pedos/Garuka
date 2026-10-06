"use client";

import { useEffect, useState } from "react";
import { useAuth } from "@/lib/auth-context";
import { fetchSettings, updateSettings, type AppSettings } from "@/lib/api/client";
import { ScopeHeader } from "@/components/scope-header";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { CheckCircle2, AlertTriangle, RefreshCw, Save } from "lucide-react";

export default function SettingsPage() {
  const { user } = useAuth();
  const [settings, setSettings] = useState<AppSettings | null>(null);
  const [formData, setFormData] = useState<Partial<AppSettings>>({});
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [successMessage, setSuccessMessage] = useState<string | null>(null);

  const loadData = (signal?: AbortSignal) => {
    setLoading(true);
    setError(null);
    fetchSettings(signal)
      .then((data) => {
        setSettings(data);
        setFormData(data);
      })
      .catch((err) => {
        if (err.name !== "AbortError") {
          setError(err.message || "Failed to load settings");
        }
      })
      .finally(() => setLoading(false));
  };

  useEffect(() => {
    const controller = new AbortController();
    loadData(controller.signal);
    return () => controller.abort();
  }, []);

  if (!user || user.role !== "admin") {
    return (
      <div className="p-8 text-center">
        <h2 className="text-xl font-bold text-destructive">Access Restricted</h2>
        <p className="text-muted-foreground mt-2">
          Only national system administrators can view and modify system thresholds.
        </p>
      </div>
    );
  }

  const handleChange = (field: keyof AppSettings, value: any) => {
    setFormData((prev) => ({ ...prev, [field]: value }));
    setSuccessMessage(null);
  };

  const handleSave = async (e: React.FormEvent) => {
    e.preventDefault();
    setSaving(true);
    setError(null);
    setSuccessMessage(null);

    try {
      const updated = await updateSettings(formData);
      setSettings(updated);
      setFormData(updated);
      setSuccessMessage("System thresholds and quiet hours successfully updated.");
    } catch (err: any) {
      setError(err.message || "Failed to save settings");
    } finally {
      setSaving(false);
    }
  };

  return (
    <div className="space-y-6 max-w-5xl">
      <ScopeHeader
        title="Settings & System Thresholds"
        description="Configure dropout early-warning thresholds, SLA escalation windows, and SMS dispatch policies."
        scope={{ level: "national", name: "Rwanda" }}
      >
        <Button
          variant="outline"
          size="sm"
          onClick={() => loadData()}
          disabled={loading || saving}
        >
          <RefreshCw className={`h-4 w-4 mr-1.5 ${loading ? "animate-spin" : ""}`} />
          Refresh
        </Button>
      </ScopeHeader>

      {error && (
        <div
          role="alert"
          className="p-4 bg-destructive/15 border border-destructive/20 text-destructive rounded-lg flex items-center justify-between"
        >
          <div className="flex items-center gap-2 text-sm font-medium">
            <AlertTriangle className="h-4 w-4 shrink-0" />
            <span>{error}</span>
          </div>
          <Button variant="outline" size="sm" onClick={() => loadData()}>
            Retry
          </Button>
        </div>
      )}

      {successMessage && (
        <div
          role="status"
          className="p-4 bg-emerald-500/15 border border-emerald-500/20 text-emerald-700 dark:text-emerald-400 rounded-lg flex items-center gap-2 text-sm font-medium"
        >
          <CheckCircle2 className="h-4 w-4 shrink-0" />
          <span>{successMessage}</span>
        </div>
      )}

      {loading && !settings ? (
        <div className="p-12 text-center text-muted-foreground animate-pulse">
          Loading system thresholds...
        </div>
      ) : (
        <form onSubmit={handleSave} className="space-y-6">
          {/* Rules Engine Early Warning Thresholds */}
          <Card>
            <CardHeader>
              <CardTitle className="text-base font-semibold">
                Absence & Escalation Thresholds
              </CardTitle>
              <CardDescription>
                Criteria evaluated by the nightly batch rules engine to flag at-risk students and escalate cases.
              </CardDescription>
            </CardHeader>
            <CardContent className="grid grid-cols-1 md:grid-cols-2 gap-6">
              <div className="space-y-1.5">
                <label
                  htmlFor="rule_consecutive_days"
                  className="text-sm font-medium text-foreground"
                >
                  Consecutive Absences Trigger (Days)
                </label>
                <input
                  id="rule_consecutive_days"
                  type="number"
                  min={1}
                  max={30}
                  required
                  value={formData.rule_consecutive_days ?? 3}
                  onChange={(e) =>
                    handleChange("rule_consecutive_days", parseInt(e.target.value, 10))
                  }
                  className="w-full px-3 py-2 border rounded-md bg-background text-foreground text-sm focus:outline-hidden focus:ring-2 focus:ring-primary"
                />
                <p className="text-xs text-muted-foreground">
                  Triggers Level 2 case when a student misses N consecutive school days.
                </p>
              </div>

              <div className="space-y-1.5">
                <label
                  htmlFor="rule_monthly_absences"
                  className="text-sm font-medium text-foreground"
                >
                  30-Day Cumulative Absences Trigger (Days)
                </label>
                <input
                  id="rule_monthly_absences"
                  type="number"
                  min={1}
                  max={30}
                  required
                  value={formData.rule_monthly_absences ?? 5}
                  onChange={(e) =>
                    handleChange("rule_monthly_absences", parseInt(e.target.value, 10))
                  }
                  className="w-full px-3 py-2 border rounded-md bg-background text-foreground text-sm focus:outline-hidden focus:ring-2 focus:ring-primary"
                />
                <p className="text-xs text-muted-foreground">
                  Triggers Level 2 case when absences in a 30-day window reach this count.
                </p>
              </div>

              <div className="space-y-1.5">
                <label
                  htmlFor="rule_escalate_term_absences"
                  className="text-sm font-medium text-foreground"
                >
                  Term Cumulative Absences Escalation (Days)
                </label>
                <input
                  id="rule_escalate_term_absences"
                  type="number"
                  min={1}
                  max={90}
                  required
                  value={formData.rule_escalate_term_absences ?? 12}
                  onChange={(e) =>
                    handleChange("rule_escalate_term_absences", parseInt(e.target.value, 10))
                  }
                  className="w-full px-3 py-2 border rounded-md bg-background text-foreground text-sm focus:outline-hidden focus:ring-2 focus:ring-primary"
                />
                <p className="text-xs text-muted-foreground">
                  Escalates case to Level 3 (Sector Education Officer) if term absences reach this mark.
                </p>
              </div>

              <div className="space-y-1.5">
                <label
                  htmlFor="rule_district_escalation_days"
                  className="text-sm font-medium text-foreground"
                >
                  District Escalation Window (School Days)
                </label>
                <input
                  id="rule_district_escalation_days"
                  type="number"
                  min={1}
                  max={60}
                  required
                  value={formData.rule_district_escalation_days ?? 10}
                  onChange={(e) =>
                    handleChange("rule_district_escalation_days", parseInt(e.target.value, 10))
                  }
                  className="w-full px-3 py-2 border rounded-md bg-background text-foreground text-sm focus:outline-hidden focus:ring-2 focus:ring-primary"
                />
                <p className="text-xs text-muted-foreground">
                  Escalates case from Level 3 to Level 4 (District Director) if unresolved after N days.
                </p>
              </div>
            </CardContent>
          </Card>

          {/* Mentor Workflow & SLA SLAs */}
          <Card>
            <CardHeader>
              <CardTitle className="text-base font-semibold">
                Community Mentor & Visit SLAs
              </CardTitle>
              <CardDescription>
                Control mentor case distribution limits and visit verification deadlines.
              </CardDescription>
            </CardHeader>
            <CardContent className="grid grid-cols-1 md:grid-cols-2 gap-6">
              <div className="space-y-1.5">
                <label
                  htmlFor="rule_visit_sla_school_days"
                  className="text-sm font-medium text-foreground"
                >
                  Home Visit SLA (School Days)
                </label>
                <input
                  id="rule_visit_sla_school_days"
                  type="number"
                  min={1}
                  max={30}
                  required
                  value={formData.rule_visit_sla_school_days ?? 5}
                  onChange={(e) =>
                    handleChange("rule_visit_sla_school_days", parseInt(e.target.value, 10))
                  }
                  className="w-full px-3 py-2 border rounded-md bg-background text-foreground text-sm focus:outline-hidden focus:ring-2 focus:ring-primary"
                />
                <p className="text-xs text-muted-foreground">
                  Cases with visits unverified beyond this window appear in the Overdue Visits list.
                </p>
              </div>

              <div className="space-y-1.5">
                <label
                  htmlFor="rule_return_streak_school_days"
                  className="text-sm font-medium text-foreground"
                >
                  Return Streak for Auto-Resolution (School Days)
                </label>
                <input
                  id="rule_return_streak_school_days"
                  type="number"
                  min={1}
                  max={30}
                  required
                  value={formData.rule_return_streak_school_days ?? 10}
                  onChange={(e) =>
                    handleChange("rule_return_streak_school_days", parseInt(e.target.value, 10))
                  }
                  className="w-full px-3 py-2 border rounded-md bg-background text-foreground text-sm focus:outline-hidden focus:ring-2 focus:ring-primary"
                />
                <p className="text-xs text-muted-foreground">
                  Consecutive present attendance days required to mark a visited case as returned.
                </p>
              </div>

              <div className="space-y-1.5">
                <label
                  htmlFor="mentor_max_active_cases"
                  className="text-sm font-medium text-foreground"
                >
                  Max Active Cases per Mentor
                </label>
                <input
                  id="mentor_max_active_cases"
                  type="number"
                  min={1}
                  max={50}
                  required
                  value={formData.mentor_max_active_cases ?? 5}
                  onChange={(e) =>
                    handleChange("mentor_max_active_cases", parseInt(e.target.value, 10))
                  }
                  className="w-full px-3 py-2 border rounded-md bg-background text-foreground text-sm focus:outline-hidden focus:ring-2 focus:ring-primary"
                />
                <p className="text-xs text-muted-foreground">
                  Prevents mentor overload during automated case assignment.
                </p>
              </div>
            </CardContent>
          </Card>

          {/* SMS Dispatch & Quiet Hours */}
          <Card>
            <CardHeader>
              <CardTitle className="text-base font-semibold">
                SMS Delivery & Quiet Hours (Kigali Time)
              </CardTitle>
              <CardDescription>
                Quiet hours prevent disturbing guardians during late evening and early morning hours.
              </CardDescription>
            </CardHeader>
            <CardContent className="grid grid-cols-1 md:grid-cols-2 gap-6">
              <div className="space-y-1.5">
                <label
                  htmlFor="sms_quiet_hours_start"
                  className="text-sm font-medium text-foreground"
                >
                  Quiet Hours Start (HH:MM)
                </label>
                <input
                  id="sms_quiet_hours_start"
                  type="time"
                  required
                  value={formData.sms_quiet_hours_start ?? "20:00"}
                  onChange={(e) => handleChange("sms_quiet_hours_start", e.target.value)}
                  className="w-full px-3 py-2 border rounded-md bg-background text-foreground text-sm focus:outline-hidden focus:ring-2 focus:ring-primary"
                />
                <p className="text-xs text-muted-foreground">
                  Outbound parent notifications hold in queue starting at this hour (UTC+2).
                </p>
              </div>

              <div className="space-y-1.5">
                <label
                  htmlFor="sms_quiet_hours_end"
                  className="text-sm font-medium text-foreground"
                >
                  Quiet Hours End (HH:MM)
                </label>
                <input
                  id="sms_quiet_hours_end"
                  type="time"
                  required
                  value={formData.sms_quiet_hours_end ?? "07:00"}
                  onChange={(e) => handleChange("sms_quiet_hours_end", e.target.value)}
                  className="w-full px-3 py-2 border rounded-md bg-background text-foreground text-sm focus:outline-hidden focus:ring-2 focus:ring-primary"
                />
                <p className="text-xs text-muted-foreground">
                  Queued messages resume automatic dispatch at this morning hour (UTC+2).
                </p>
              </div>
            </CardContent>
          </Card>

          <div className="flex items-center justify-between pt-2">
            <div className="text-xs text-muted-foreground">
              {settings?.updated_at && (
                <span>
                  Last updated:{" "}
                  {new Date(settings.updated_at).toLocaleString("en-GB", {
                    timeZone: "Africa/Kigali",
                  })}{" "}
                  CAT
                </span>
              )}
            </div>
            <Button type="submit" disabled={saving || loading}>
              <Save className="h-4 w-4 mr-1.5" />
              {saving ? "Saving Changes..." : "Save Settings"}
            </Button>
          </div>
        </form>
      )}
    </div>
  );
}
