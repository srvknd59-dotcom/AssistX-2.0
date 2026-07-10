export type SourceType = "manual" | "ticket";

export interface Source {
  type: SourceType;
  label: string;
  snippet: string;
  score: number;
}

export interface ChatMessage {
  id: string;
  role: "user" | "assistant";
  content: string;
  sources?: Source[];
  pending?: boolean;
}

export interface HealthStatus {
  status: string;
  manuals_indexed: number;
  tickets_indexed: number;
}

export interface DocumentInfo {
  name: string;
  type: SourceType;
  chunk_count: number;
}

export interface IngestStats {
  manuals_indexed: number;
  manual_chunks: number;
  tickets_indexed: number;
}
