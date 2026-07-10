import axios from "axios";
import type { DocumentInfo, HealthStatus, IngestStats, Source } from "../types";

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL ?? "http://localhost:8000";

const http = axios.create({ baseURL: API_BASE_URL, timeout: 60_000 });

export async function getHealth(): Promise<HealthStatus> {
  const { data } = await http.get<HealthStatus>("/health");
  return data;
}

export async function runIngest(): Promise<IngestStats> {
  const { data } = await http.post<IngestStats>("/ingest");
  return data;
}

export async function getDocuments(): Promise<DocumentInfo[]> {
  const { data } = await http.get<DocumentInfo[]>("/documents");
  return data;
}

export async function startChatSession(): Promise<string> {
  const { data } = await http.post<{ session_id: string }>("/chat/start");
  return data.session_id;
}

export async function sendChatMessage(
  sessionId: string,
  message: string,
): Promise<{ answer: string; sources: Source[] }> {
  const { data } = await http.post("/chat/send", { session_id: sessionId, message });
  return data;
}

export function apiBaseUrl(): string {
  return API_BASE_URL;
}
