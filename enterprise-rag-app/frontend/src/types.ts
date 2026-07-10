export interface Source {
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
  chunks_indexed: number;
}

export interface DocumentInfo {
  name: string;
  chunk_count: number;
}

export interface IngestStats {
  documents_indexed: number;
  chunks_indexed: number;
}

export interface UploadResponse {
  filename: string;
  message: string;
}
