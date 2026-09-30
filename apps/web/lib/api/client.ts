import type { paths } from "./schema";

const API_BASE_URL =
  process.env.NEXT_PUBLIC_API_BASE_URL || "http://localhost:8000/api/v1";

function authHeaders(token?: string | null): Record<string, string> {
  const headers: Record<string, string> = { "Content-Type": "application/json" };
  const effectiveToken = token || (typeof window !== "undefined" ? localStorage.getItem("garuka_token") : null);
  if (effectiveToken) {
    headers["Authorization"] = `Bearer ${effectiveToken}`;
  }
  return headers;
}

export async function fetchHealth(): Promise<
  paths["/api/v1/health"]["get"]["responses"]["200"]["content"]["application/json"]
> {
  const res = await fetch(`${API_BASE_URL}/health`, {
    headers: { "Content-Type": "application/json" },
    cache: "no-store",
  });
  if (!res.ok) {
    throw new Error(`Failed to fetch health: ${res.statusText}`);
  }
  return res.json();
}

export async function fetchSchools(): Promise<
  paths["/api/v1/schools"]["get"]["responses"]["200"]["content"]["application/json"]
> {
  const res = await fetch(`${API_BASE_URL}/schools`, {
    headers: authHeaders(),
  });
  if (!res.ok) throw new Error("Failed to fetch schools");
  return res.json();
}

export async function createSchool(data: {
  sector_id: string;
  name: string;
  code?: string;
  level?: "primary" | "secondary" | "both";
}): Promise<paths["/api/v1/schools"]["post"]["responses"]["201"]["content"]["application/json"]> {
  const res = await fetch(`${API_BASE_URL}/schools`, {
    method: "POST",
    headers: authHeaders(),
    body: JSON.stringify(data),
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({}));
    throw new Error(err.detail || "Failed to create school");
  }
  return res.json();
}

export async function fetchDistricts(): Promise<
  paths["/api/v1/districts"]["get"]["responses"]["200"]["content"]["application/json"]
> {
  const res = await fetch(`${API_BASE_URL}/districts`, {
    headers: authHeaders(),
  });
  if (!res.ok) throw new Error("Failed to fetch districts");
  return res.json();
}

export async function fetchSectors(districtId?: string): Promise<
  paths["/api/v1/sectors"]["get"]["responses"]["200"]["content"]["application/json"]
> {
  const url = new URL(`${API_BASE_URL}/sectors`);
  if (districtId) url.searchParams.append("district_id", districtId);
  const res = await fetch(url.toString(), {
    headers: authHeaders(),
  });
  if (!res.ok) throw new Error("Failed to fetch sectors");
  return res.json();
}

export async function fetchUsers(role?: string): Promise<
  paths["/api/v1/users"]["get"]["responses"]["200"]["content"]["application/json"]
> {
  const url = new URL(`${API_BASE_URL}/users`);
  if (role) url.searchParams.append("role", role);
  const res = await fetch(url.toString(), {
    headers: authHeaders(),
  });
  if (!res.ok) throw new Error("Failed to fetch users");
  return res.json();
}

export async function createUser(data: {
  full_name: string;
  email?: string;
  phone_e164?: string;
  role: string;
  password?: string;
  school_id?: string;
  sector_id?: string;
  district_id?: string;
}): Promise<paths["/api/v1/users"]["post"]["responses"]["201"]["content"]["application/json"]> {
  const res = await fetch(`${API_BASE_URL}/users`, {
    method: "POST",
    headers: authHeaders(),
    body: JSON.stringify(data),
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({}));
    throw new Error(err.detail || "Failed to create user");
  }
  return res.json();
}

export async function resetUserPin(userId: string): Promise<{ id: string; message: string }> {
  const res = await fetch(`${API_BASE_URL}/users/${userId}/reset-pin`, {
    method: "POST",
    headers: authHeaders(),
  });
  if (!res.ok) throw new Error("Failed to reset PIN");
  return res.json();
}

export async function fetchStudents(params?: {
  school_id?: string;
  class_id?: string;
  q?: string;
}): Promise<paths["/api/v1/students"]["get"]["responses"]["200"]["content"]["application/json"]> {
  const url = new URL(`${API_BASE_URL}/students`);
  if (params?.school_id) url.searchParams.append("school_id", params.school_id);
  if (params?.class_id) url.searchParams.append("class_id", params.class_id);
  if (params?.q) url.searchParams.append("q", params.q);

  const res = await fetch(url.toString(), {
    headers: authHeaders(),
  });
  if (!res.ok) throw new Error("Failed to fetch students");
  return res.json();
}

export async function uploadStudentsCSV(
  file: File,
  schoolId?: string,
  dryRun: boolean = false
): Promise<paths["/api/v1/students/import"]["post"]["responses"]["200"]["content"]["application/json"]> {
  const formData = new FormData();
  formData.append("file", file);

  const url = new URL(`${API_BASE_URL}/students/import`);
  if (schoolId) url.searchParams.append("school_id", schoolId);
  url.searchParams.append("dry_run", String(dryRun));

  const effectiveToken = typeof window !== "undefined" ? localStorage.getItem("garuka_token") : null;
  const headers: Record<string, string> = {};
  if (effectiveToken) {
    headers["Authorization"] = `Bearer ${effectiveToken}`;
  }

  const res = await fetch(url.toString(), {
    method: "POST",
    headers,
    body: formData,
  });

  if (!res.ok) {
    const err = await res.json().catch(() => ({}));
    throw new Error(err.detail || "CSV import request failed");
  }

  return res.json();
}
