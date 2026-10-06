// Typed API client for the web app. Types come only from the generated schema (ADR-019).
import createClient from "openapi-fetch";

import type { components, paths } from "./schema";

export * from "./vocabulary";
export type { components, paths };

export type ErrorResponse = components["schemas"]["ErrorResponse"];
export type MeResponse = components["schemas"]["MeResponse"];
export type QuestionSet = components["schemas"]["QuestionSetDefinition"];
export type Question = components["schemas"]["Question"];
export type ProjectDetail = components["schemas"]["ProjectDetail"];
export type ProjectSummary = components["schemas"]["ProjectSummary"];
export type FileView = components["schemas"]["FileView"];
export type EstimateResponse = components["schemas"]["EstimateResponse"];

/** Required on every state-changing request made with a session cookie (API_ARCHITECTURE 1). */
export const CSRF_HEADERS = { "X-Requested-With": "plan2build" } as const;

export interface ApiClientOptions {
  baseUrl: string;
  headers?: Record<string, string>;
  fetch?: typeof globalThis.fetch;
}

export function createApiClient({ baseUrl, headers, fetch }: ApiClientOptions) {
  return createClient<paths>({ baseUrl, headers: { ...CSRF_HEADERS, ...headers }, fetch });
}

export type ApiClient = ReturnType<typeof createApiClient>;
