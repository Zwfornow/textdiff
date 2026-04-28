import type { DiffResponse, PreprocessOptions, ReportListItem } from "@/lib/types";

const API_BASE_URL = process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://127.0.0.1:8000";

type SubmitTextDiffArgs = {
  reference: string;
  ocr: string;
  referenceLabel: string;
  ocrLabel: string;
  referenceReportName: string;
  ocrReportName: string;
  options: PreprocessOptions;
};

type SubmitFileDiffArgs = {
  referenceFile: File | null;
  ocrFile: File | null;
  options: PreprocessOptions;
};

export async function submitTextDiff(args: SubmitTextDiffArgs): Promise<DiffResponse> {
  if (!args.reference.trim() || !args.ocr.trim()) {
    throw new Error("文本输入不能为空。请先填写参考文本和 OCR 文本。");
  }

  const response = await fetch(`${API_BASE_URL}/api/diff`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
    },
    body: JSON.stringify({
      reference: args.reference,
      ocr: args.ocr,
      reference_label: args.referenceLabel,
      ocr_label: args.ocrLabel,
      reference_report_name: args.referenceReportName,
      ocr_report_name: args.ocrReportName,
      preprocess_options: args.options,
    }),
  });

  return parseResponse(response);
}

export async function submitFileDiff(args: SubmitFileDiffArgs): Promise<DiffResponse> {
  if (!args.referenceFile || !args.ocrFile) {
    throw new Error("文件上传模式下必须同时选择参考文件和 OCR 文件。");
  }

  const formData = new FormData();
  formData.append("reference_file", args.referenceFile);
  formData.append("ocr_file", args.ocrFile);
  formData.append("preprocess_options", JSON.stringify(args.options));

  const response = await fetch(`${API_BASE_URL}/api/diff`, {
    method: "POST",
    body: formData,
  });

  return parseResponse(response);
}

async function parseResponse(response: Response): Promise<DiffResponse> {
  const payload = (await response.json()) as DiffResponse | { detail?: string; error?: string };
  if (!response.ok) {
    const message = "detail" in payload && payload.detail ? payload.detail : "请求失败，请检查后端服务日志。";
    throw new Error(message);
  }
  return payload as DiffResponse;
}

export async function fetchReportList(): Promise<ReportListItem[]> {
  const response = await fetch(`${API_BASE_URL}/api/reports`);
  if (!response.ok) {
    throw new Error("获取报告列表失败。");
  }
  const data = (await response.json()) as { reports: ReportListItem[] };
  return data.reports;
}