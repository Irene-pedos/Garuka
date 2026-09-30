import type { paths } from "./schema";

const API_BASE_URL =
  process.env.NEXT_PUBLIC_API_BASE_URL || "http://localhost:8000/api/v1";

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
