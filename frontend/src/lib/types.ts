export type DiffMode = "text" | "file";

export type PreprocessOptions = {
  normalize_width: boolean;
  normalize_punctuation: boolean;
  case_sensitive: boolean;
};

export type DiffStats = {
  reference_length: number;
  delete_count: number;
  insert_count: number;
  replace_count: number;
  error_count: number;
  accuracy: number;
};

export type DiffResponse = {
  reference_text: string;
  ocr_text: string;
  stats: DiffStats;
  report_url: string;
};