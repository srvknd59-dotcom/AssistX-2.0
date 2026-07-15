export type ContentType = "text" | "table" | "image";

export interface Source {
  label: string;
  snippet: string;
  score: number;
  content_type: ContentType;
  page: number | null;
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
  tables_indexed: number;
  images_indexed: number;
}

export interface DocumentInfo {
  name: string;
  chunk_count: number;
}

export interface IngestStats {
  documents_indexed: number;
  chunks_indexed: number;
  tables_indexed: number;
  images_captioned: number;
}

export interface UploadResponse {
  filename: string;
  message: string;
}
