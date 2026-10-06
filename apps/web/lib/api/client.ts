import type { paths } from "./schema";

const API_BASE_URL =
  process.env.NEXT_PUBLIC_API_BASE_URL || "http://localhost:8000/api/v1";

export class ApiError extends Error {
  status: number;
  detail?: string;

  constructor(status: number, message: string, detail?: string) {
    super(message);
    this.name = "ApiError";
    this.status = status;
    this.detail = detail;
  }
}

function authHeaders(extra?: HeadersInit): Headers {
  const headers = new Headers(extra || {});
  const effectiveToken =
    typeof window !== "undefined" ? localStorage.getItem("garuka_token") : null;
  if (effectiveToken && !headers.has("Authorization")) {
    headers.set("Authorization", `Bearer ${effectiveToken}`);
  }
  return headers;
}

export async function apiFetch<T>(
  endpoint: string,
  options: RequestInit = {}
): Promise<T> {
  const url = endpoint.startsWith("http")
    ? endpoint
    : `${API_BASE_URL}${endpoint.startsWith("/") ? "" : "/"}${endpoint}`;

  const headers = authHeaders(options.headers);
  if (!(options.body instanceof FormData) && !headers.has("Content-Type")) {
    headers.set("Content-Type", "application/json");
  }

  const res = await fetch(url, {
    ...options,
    headers,
  });

  if (!res.ok) {
    let errorDetail: string | undefined;
    try {
      const errJson = await res.json();
      if (typeof errJson.detail === "string") {
        errorDetail = errJson.detail;
      } else if (Array.isArray(errJson.detail)) {
        errorDetail = errJson.detail.map((d: any) => d.msg || JSON.stringify(d)).join(", ");
      } else if (errJson.message) {
        errorDetail = errJson.message;
      }
    } catch {
      // response wasn't JSON
    }

    const message = errorDetail || `Request failed with status ${res.status}: ${res.statusText}`;
    throw new ApiError(res.status, message, errorDetail);
  }

  // Handle 204 No Content
  if (res.status === 204) {
    return {} as T;
  }

  return res.json();
}

// ---------------------------------------------------------------------------
// Typed Domain Models
// ---------------------------------------------------------------------------

export interface ScopeInfo {
  level: "national" | "district" | "sector" | "school" | "user";
  name: string;
}

export interface OverviewKPIs {
  students_active: number;
  absent_today: number;
  open_cases: number;
  new_cases_7d: number;
  visits_overdue: number;
  returned_30d: number;
  attendance_compliance_pct: number;
  classes_missing_today: number;
  recent_escalations_count: number;
  pending_help_requests_count: number;
  mentor_cases_active: number;
}

export interface ActiveTermInfo {
  academic_year: number;
  term_no: number;
  name: string;
}

export interface OverdueCaseItem {
  id: string;
  ref: string;
  student_name: string;
  school_name: string;
  level: number;
  opened_at: string;
  days_open: number;
}

export interface ReportingGapItem {
  class_name: string;
  school_name: string;
  missing_dates: string[];
}

export interface RecentEscalationItem {
  id: string;
  ref: string;
  student_name: string;
  school_name: string;
  level: number;
  status: string;
  escalated_at: string;
}

export interface PendingHelpRequestItem {
  id: string;
  student_name: string;
  school_name: string;
  barrier_code: string;
  status: string;
  created_at: string;
}

export interface MissingClassItem {
  class_id: string;
  class_name: string;
  school_name: string;
}

export interface DailyAttendanceTrendItem {
  date: string;
  present: number;
  absent: number;
  enrolled: number;
  cases: number;
}

export interface AnalyticsOverview {
  as_of: string;
  timezone: string;
  kigali_today: string;
  scope: ScopeInfo;
  kpis: OverviewKPIs;
  cases_by_level: Record<string, number>;
  active_term?: ActiveTermInfo | null;
  overdue_cases: OverdueCaseItem[];
  reporting_gaps: ReportingGapItem[];
  classes_missing_today: MissingClassItem[];
  recent_escalations: RecentEscalationItem[];
  pending_help_requests: PendingHelpRequestItem[];
  attendance_trend: DailyAttendanceTrendItem[];
}

export interface SchoolCompareItem {
  school_id: string;
  school_name: string;
  sector_name: string;
  students_active: number;
  absent_today: number;
  absence_rate_pct: number;
  open_cases: number;
  returned_30d: number;
  attendance_compliance_pct: number;
}

export interface HelpRequestItem {
  id: string;
  student_id: string;
  student_name: string;
  class_name?: string | null;
  school_id: string;
  school_name: string;
  guardian_id: string;
  guardian_name: string;
  guardian_phone: string;
  barrier_code: "COST" | "HUNGER" | "HEALTH" | "DISTANCE" | "FAMILY" | "OTHER";
  status: "new" | "seen" | "in_progress" | "closed";
  created_at: string;
}

export interface AppSettings {
  rule_consecutive_days: number;
  rule_monthly_absences: number;
  rule_escalate_term_absences: number;
  rule_visit_sla_school_days: number;
  rule_return_streak_school_days: number;
  rule_district_escalation_days: number;
  mentor_max_active_cases: number;
  sms_quiet_hours_start: string;
  sms_quiet_hours_end: string;
  updated_at?: string | null;
  updated_by?: string | null;
}

export interface SmsOutboxItem {
  id: string;
  to_e164: string;
  template_key: string;
  body: string;
  status: "pending" | "sent" | "delivered" | "failed" | "skipped";
  attempts: number;
  last_error?: string | null;
  scheduled_at: string;
  sent_at?: string | null;
  related_student_id?: string | null;
  related_case_id?: string | null;
}

export interface AuditLogItem {
  id: string;
  actor_user_id?: string | null;
  actor_role: string;
  action: string;
  entity_type: string;
  entity_id?: string | null;
  ip?: string | null;
  meta: Record<string, any>;
  created_at: string;
}

// ---------------------------------------------------------------------------
// API Methods
// ---------------------------------------------------------------------------

export async function fetchHealth(signal?: AbortSignal): Promise<
  paths["/api/v1/health"]["get"]["responses"]["200"]["content"]["application/json"]
> {
  return apiFetch("/health", { signal, cache: "no-store" });
}

export async function fetchSchools(signal?: AbortSignal): Promise<
  paths["/api/v1/schools"]["get"]["responses"]["200"]["content"]["application/json"]
> {
  return apiFetch("/schools", { signal });
}

export async function createSchool(data: {
  sector_id: string;
  name: string;
  code?: string;
  level?: "primary" | "secondary" | "both";
}): Promise<paths["/api/v1/schools"]["post"]["responses"]["201"]["content"]["application/json"]> {
  return apiFetch("/schools", {
    method: "POST",
    body: JSON.stringify(data),
  });
}

export async function fetchDistricts(signal?: AbortSignal): Promise<
  paths["/api/v1/districts"]["get"]["responses"]["200"]["content"]["application/json"]
> {
  return apiFetch("/districts", { signal });
}

export async function fetchSectors(districtId?: string, signal?: AbortSignal): Promise<
  paths["/api/v1/sectors"]["get"]["responses"]["200"]["content"]["application/json"]
> {
  const query = districtId ? `?district_id=${encodeURIComponent(districtId)}` : "";
  return apiFetch(`/sectors${query}`, { signal });
}

export interface UserAssignedClass {
  id: string;
  name: string;
  grade: number;
  academic_year?: number | null;
}

export interface UserItem {
  id: string;
  full_name: string;
  email?: string | null;
  phone_masked?: string | null;
  phone_e164?: string | null;
  role: string;
  language: string;
  school_id?: string | null;
  sector_id?: string | null;
  district_id?: string | null;
  is_active: boolean;
  assigned_classes?: UserAssignedClass[];
}

export async function fetchUsers(role?: string, signal?: AbortSignal): Promise<UserItem[]> {
  const query = role ? `?role=${encodeURIComponent(role)}` : "";
  return apiFetch<UserItem[]>(`/users${query}`, { signal });
}

export async function createUser(data: {
  full_name: string;
  email?: string;
  phone_e164?: string;
  role: string;
  password?: string;
  language?: string;
  school_id?: string;
  sector_id?: string;
  district_id?: string;
  class_ids?: string[];
}): Promise<UserItem> {
  return apiFetch<UserItem>("/users", {
    method: "POST",
    body: JSON.stringify(data),
  });
}

export async function updateUser(
  userId: string,
  data: {
    full_name?: string;
    email?: string;
    phone_e164?: string;
    language?: string;
    is_active?: boolean;
    class_ids?: string[];
  }
): Promise<UserItem> {
  return apiFetch<UserItem>(`/users/${userId}`, {
    method: "PATCH",
    body: JSON.stringify(data),
  });
}

export async function resetUserPin(userId: string): Promise<{ id: string; message: string }> {
  return apiFetch(`/users/${userId}/reset-pin`, {
    method: "POST",
  });
}

export async function fetchStudents(
  params?: { school_id?: string; class_id?: string; q?: string },
  signal?: AbortSignal
): Promise<paths["/api/v1/students"]["get"]["responses"]["200"]["content"]["application/json"]> {
  const sp = new URLSearchParams();
  if (params?.school_id) sp.append("school_id", params.school_id);
  if (params?.class_id) sp.append("class_id", params.class_id);
  if (params?.q) sp.append("q", params.q);
  const qStr = sp.toString() ? `?${sp.toString()}` : "";
  return apiFetch(`/students${qStr}`, { signal });
}

export async function uploadStudentsCSV(
  file: File,
  schoolId?: string,
  dryRun: boolean = false
): Promise<paths["/api/v1/students/import"]["post"]["responses"]["200"]["content"]["application/json"]> {
  const formData = new FormData();
  formData.append("file", file);

  const sp = new URLSearchParams();
  if (schoolId) sp.append("school_id", schoolId);
  sp.append("dry_run", String(dryRun));

  return apiFetch(`/students/import?${sp.toString()}`, {
    method: "POST",
    body: formData,
  });
}

export async function fetchSchoolClasses(schoolId: string, signal?: AbortSignal): Promise<
  Array<{
    id: string;
    name: string;
    grade: number;
    academic_year: number;
    school_id: string;
    class_teacher_id?: string | null;
  }>
> {
  return apiFetch(`/schools/${schoolId}/classes`, { signal });
}

export async function fetchAttendanceCompliance(
  schoolId: string,
  fromDate?: string,
  toDate?: string,
  signal?: AbortSignal
): Promise<{
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
}> {
  const sp = new URLSearchParams({ school_id: schoolId });
  if (fromDate) sp.append("from", fromDate);
  if (toDate) sp.append("to", toDate);
  return apiFetch(`/attendance/compliance?${sp.toString()}`, { signal });
}

export async function fetchClassAttendance(
  classId: string,
  date?: string,
  signal?: AbortSignal
): Promise<{
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
}> {
  const sp = date ? `?date=${encodeURIComponent(date)}` : "";
  return apiFetch(`/classes/${classId}/attendance${sp}`, { signal });
}

export async function submitClassAttendance(
  classId: string,
  data: { date: string; absent_student_ids: string[] }
): Promise<any> {
  return apiFetch(`/classes/${classId}/attendance`, {
    method: "POST",
    body: JSON.stringify(data),
  });
}

export async function voidAbsence(absenceId: string): Promise<any> {
  return apiFetch(`/absences/${absenceId}`, {
    method: "DELETE",
  });
}

export function getComplianceCSVUrl(schoolId: string, fromDate?: string, toDate?: string): string {
  const sp = new URLSearchParams({ school_id: schoolId, format: "csv" });
  if (fromDate) sp.append("from", fromDate);
  if (toDate) sp.append("to", toDate);
  const effectiveToken =
    typeof window !== "undefined" ? localStorage.getItem("garuka_token") : null;
  if (effectiveToken) {
    sp.append("token", effectiveToken);
  }
  return `${API_BASE_URL}/attendance/compliance?${sp.toString()}`;
}

export async function downloadComplianceCSV(
  schoolId: string,
  fromDate?: string,
  toDate?: string,
  schoolName?: string
): Promise<void> {
  const sp = new URLSearchParams({ school_id: schoolId, format: "csv" });
  if (fromDate) sp.append("from", fromDate);
  if (toDate) sp.append("to", toDate);

  const url = `${API_BASE_URL}/attendance/compliance?${sp.toString()}`;
  const effectiveToken =
    typeof window !== "undefined" ? localStorage.getItem("garuka_token") : null;
  const headers: HeadersInit = {};
  if (effectiveToken) {
    headers["Authorization"] = `Bearer ${effectiveToken}`;
  }

  const res = await fetch(url, { headers });
  if (!res.ok) {
    let errorDetail: string | undefined;
    try {
      const errJson = await res.json();
      errorDetail = errJson.detail;
    } catch {
      // not json
    }
    throw new ApiError(
      res.status,
      errorDetail || `Failed to download CSV (${res.status})`,
      errorDetail
    );
  }

  const blob = await res.blob();
  const blobUrl = window.URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = blobUrl;
  const safeName = (schoolName || "compliance").replace(/[^a-zA-Z0-9_-]/g, "_");
  a.download = `compliance_${safeName}_${fromDate || "14d"}_${toDate || "today"}.csv`;
  document.body.appendChild(a);
  a.click();
  a.remove();
  window.URL.revokeObjectURL(blobUrl);
}

export async function fetchCases(
  params?: {
    status?: string;
    level?: number;
    school_id?: string;
    sector_id?: string;
    mentor_id?: string;
    q?: string;
  },
  signal?: AbortSignal
): Promise<any[]> {
  const sp = new URLSearchParams();
  if (params?.status) sp.append("status", params.status);
  if (params?.level) sp.append("level", String(params.level));
  if (params?.school_id) sp.append("school_id", params.school_id);
  if (params?.sector_id) sp.append("sector_id", params.sector_id);
  if (params?.mentor_id) sp.append("mentor_id", params.mentor_id);
  if (params?.q) sp.append("q", params.q);
  const qStr = sp.toString() ? `?${sp.toString()}` : "";
  return apiFetch(`/cases${qStr}`, { signal });
}

export async function fetchCaseDetail(caseId: string, signal?: AbortSignal): Promise<any> {
  return apiFetch(`/cases/${caseId}`, { signal });
}

export async function assignCaseMentor(caseId: string, mentorId: string): Promise<any> {
  return apiFetch(`/cases/${caseId}/assign`, {
    method: "PATCH",
    body: JSON.stringify({ mentor_id: mentorId }),
  });
}

export async function escalateCase(
  caseId: string,
  toLevel: number,
  note?: string
): Promise<any> {
  return apiFetch(`/cases/${caseId}/escalate`, {
    method: "POST",
    body: JSON.stringify({ to_level: toLevel, note }),
  });
}

export async function addCaseNote(caseId: string, text: string): Promise<any> {
  return apiFetch(`/cases/${caseId}/notes`, {
    method: "POST",
    body: JSON.stringify({ text }),
  });
}

export async function resolveCase(
  caseId: string,
  outcome: string,
  note?: string
): Promise<any> {
  return apiFetch(`/cases/${caseId}/resolve`, {
    method: "POST",
    body: JSON.stringify({ outcome, note }),
  });
}

export async function fetchMentors(sectorId?: string, signal?: AbortSignal): Promise<any[]> {
  const sp = sectorId ? `?sector_id=${encodeURIComponent(sectorId)}` : "";
  return apiFetch(`/mentors${sp}`, { signal });
}

export async function fetchHelpRequests(
  params?: {
    status?: string;
    school_id?: string;
    barrier_code?: string;
  },
  signal?: AbortSignal
): Promise<HelpRequestItem[]> {
  const sp = new URLSearchParams();
  if (params?.status) sp.append("status", params.status);
  if (params?.school_id) sp.append("school_id", params.school_id);
  if (params?.barrier_code) sp.append("barrier_code", params.barrier_code);
  const qStr = sp.toString() ? `?${sp.toString()}` : "";
  return apiFetch(`/help-requests${qStr}`, { signal });
}

export async function updateHelpRequestStatus(
  id: string,
  status: "new" | "seen" | "in_progress" | "closed"
): Promise<HelpRequestItem> {
  return apiFetch(`/help-requests/${id}`, {
    method: "PATCH",
    body: JSON.stringify({ status }),
  });
}

export async function fetchAnalyticsOverview(
  daysOrSignal?: number | AbortSignal,
  signal?: AbortSignal
): Promise<AnalyticsOverview> {
  let days: number | undefined;
  let effectiveSignal: AbortSignal | undefined;

  if (typeof daysOrSignal === "number") {
    days = daysOrSignal;
    effectiveSignal = signal;
  } else if (typeof daysOrSignal === "object" && daysOrSignal !== null) {
    effectiveSignal = daysOrSignal as AbortSignal;
  } else {
    effectiveSignal = signal;
  }

  const query = days ? `?days=${days}` : "";
  return apiFetch(`/analytics/overview${query}`, { signal: effectiveSignal });
}

export async function fetchAttendanceTrends(
  days = 90,
  signal?: AbortSignal
): Promise<DailyAttendanceTrendItem[]> {
  return apiFetch<DailyAttendanceTrendItem[]>(`/analytics/trends?days=${days}`, {
    signal,
  });
}

export async function fetchSchoolsCompare(signal?: AbortSignal): Promise<SchoolCompareItem[]> {
  return apiFetch("/analytics/schools-compare", { signal });
}

export async function fetchSettings(signal?: AbortSignal): Promise<AppSettings> {
  return apiFetch("/settings", { signal });
}

export async function updateSettings(data: Partial<AppSettings>): Promise<AppSettings> {
  return apiFetch("/settings", {
    method: "PATCH",
    body: JSON.stringify(data),
  });
}

export async function fetchSmsOutbox(
  params?: {
    status?: string;
    template_key?: string;
    limit?: number;
  },
  signal?: AbortSignal
): Promise<SmsOutboxItem[]> {
  const sp = new URLSearchParams();
  if (params?.status) sp.append("status", params.status);
  if (params?.template_key) sp.append("template_key", params.template_key);
  if (params?.limit) sp.append("limit", String(params.limit));
  const qStr = sp.toString() ? `?${sp.toString()}` : "";
  return apiFetch(`/sms/outbox${qStr}`, { signal });
}

export async function retrySms(id: string): Promise<SmsOutboxItem> {
  return apiFetch(`/sms/outbox/${id}/retry`, {
    method: "POST",
  });
}

export async function fetchAuditLogs(
  params?: {
    action?: string;
    entity_type?: string;
    limit?: number;
  },
  signal?: AbortSignal
): Promise<AuditLogItem[]> {
  const sp = new URLSearchParams();
  if (params?.action) sp.append("action", params.action);
  if (params?.entity_type) sp.append("entity_type", params.entity_type);
  if (params?.limit) sp.append("limit", String(params.limit));
  const qStr = sp.toString() ? `?${sp.toString()}` : "";
  return apiFetch(`/audit${qStr}`, { signal });
}

// ---------------------------------------------------------------------------
// Account & Profile Management
// ---------------------------------------------------------------------------

export type UserMeResponse = paths["/api/v1/auth/me"]["get"]["responses"]["200"]["content"]["application/json"];
export type UpdateProfileRequest = paths["/api/v1/auth/me"]["patch"]["requestBody"]["content"]["application/json"];
export type ChangePasswordRequest = paths["/api/v1/auth/change-password"]["post"]["requestBody"]["content"]["application/json"];
export type ChangePinRequest = paths["/api/v1/auth/change-pin"]["post"]["requestBody"]["content"]["application/json"];
export type AvatarUploadResponse = paths["/api/v1/auth/avatar"]["post"]["responses"]["200"]["content"]["application/json"];

export async function fetchMe(signal?: AbortSignal): Promise<UserMeResponse> {
  return apiFetch("/auth/me", { signal });
}

export async function updateProfile(
  data: UpdateProfileRequest,
  signal?: AbortSignal
): Promise<UserMeResponse> {
  return apiFetch("/auth/me", {
    method: "PATCH",
    body: JSON.stringify(data),
    signal,
  });
}

export async function changePassword(
  data: ChangePasswordRequest,
  signal?: AbortSignal
): Promise<{ message: string }> {
  return apiFetch("/auth/change-password", {
    method: "POST",
    body: JSON.stringify(data),
    signal,
  });
}

export async function changePin(
  data: ChangePinRequest,
  signal?: AbortSignal
): Promise<{ message: string }> {
  return apiFetch("/auth/change-pin", {
    method: "POST",
    body: JSON.stringify(data),
    signal,
  });
}

export async function uploadAvatar(
  file: File,
  signal?: AbortSignal
): Promise<AvatarUploadResponse> {
  const formData = new FormData();
  formData.append("file", file);
  return apiFetch("/auth/avatar", {
    method: "POST",
    body: formData,
    signal,
  });
}

