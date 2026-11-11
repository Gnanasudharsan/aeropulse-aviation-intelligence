import { z } from "zod";

import { envelope } from "./schemas";

/**
 * API origin. In production it must be configured explicitly; an unset value means
 * "no live API connected" (never a guessed host, never the visitor's localhost).
 */
export const API_BASE_URL = (
  process.env.NEXT_PUBLIC_API_BASE_URL ?? (process.env.NODE_ENV === "production" ? "" : "http://localhost:8000")
).replace(/\/$/, "");
export const API_CONFIGURED = API_BASE_URL !== "";

export class ApiError extends Error {
  constructor(
    message: string,
    readonly status: number | null,
    readonly code: string,
  ) {
    super(message);
    this.name = "ApiError";
  }
}

type Params = Record<string, string | number | boolean | string[] | undefined | null>;

export function buildUrl(path: string, params?: Params): string {
  const url = new URL(`${API_BASE_URL}${path}`);
  for (const [key, value] of Object.entries(params ?? {})) {
    if (value === undefined || value === null || value === "") continue;
    if (Array.isArray(value)) value.forEach((v) => url.searchParams.append(key, v));
    else url.searchParams.set(key, String(value));
  }
  return url.toString();
}

/** Fetch + validate an enveloped API response. */
export async function apiGet<T extends z.ZodType>(
  path: string,
  schema: T,
  params?: Params,
  signal?: AbortSignal,
): Promise<{ data: z.infer<T>; meta: z.infer<ReturnType<typeof envelope>>["meta"] }> {
  if (!API_CONFIGURED) {
    throw new ApiError("This deployment is not connected to a live AeroPulse API", null, "not_configured");
  }
  let res: Response;
  try {
    res = await fetch(buildUrl(path, params), { signal, headers: { Accept: "application/json" } });
  } catch (err) {
    if ((err as Error).name === "AbortError") throw err;
    throw new ApiError("The AeroPulse API is unreachable", null, "network_error");
  }
  if (!res.ok) {
    let code = "http_error";
    let message = `Request failed (${res.status})`;
    try {
      const body = (await res.json()) as { error?: { code?: string; message?: string } };
      code = body.error?.code ?? code;
      message = body.error?.message ?? message;
    } catch {
      /* non-JSON error body */
    }
    throw new ApiError(message, res.status, code);
  }
  const json: unknown = await res.json();
  const parsed = envelope(schema).safeParse(json);
  if (!parsed.success) {
    console.error("API contract mismatch", path, parsed.error.issues.slice(0, 5));
    throw new ApiError("Unexpected response from the API", res.status, "contract_mismatch");
  }
  return parsed.data as { data: z.infer<T>; meta: z.infer<ReturnType<typeof envelope>>["meta"] };
}
