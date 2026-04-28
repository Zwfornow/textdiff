"use client";

import { FormEvent, useCallback, useEffect, useRef, useState } from "react";

import { fetchReportList, submitTextDiff } from "@/lib/api";
import type { DiffResponse, PreprocessOptions, ReportListItem } from "@/lib/types";

const DEFAULT_OPTIONS: PreprocessOptions = {
  normalize_width: true,
  normalize_punctuation: true,
  case_sensitive: false,
  diff_mode: "text_only",
};

const API_BASE_URL = process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://127.0.0.1:8000";

/** 上传确认弹窗的状态：记录目标文本框、新内容、文件名 */
type ConfirmState = {
  target: "reference" | "ocr";
  newContent: string;
  filename: string;
} | null;

/** 文本来源：手动输入 or 来自文件 */
type SourceState = { type: "text" } | { type: "file"; stem: string };

/** 从报告文件名中提取可读的显示名称。
 *  例：diff_20240427_123456_ref_vs_ocr.html → ref vs ocr
 */
function parseReportDisplayName(filename: string): string {
  // 去掉扩展名
  const base = filename.replace(/\.html$/, "");
  // 去掉 diff_YYYYMMDD_HHMMSS_ 前缀（约 20 字符）
  const withoutPrefix = base.replace(/^diff_\d{8}_\d{6}_/, "");
  // 将下划线替换为空格
  return withoutPrefix.replace(/_/g, " ") || base;
}

/** 带行号的文本框 */
function LineNumberedTextarea({
  value,
  onChange,
  placeholder,
}: {
  value: string;
  onChange: (v: string) => void;
  placeholder?: string;
}) {
  const textareaRef = useRef<HTMLTextAreaElement>(null);
  const lineNumRef = useRef<HTMLDivElement>(null);
  const [activeLine, setActiveLine] = useState<number | null>(null);
  const lineCount = value ? value.split("\n").length : 1;

  // 行高常量，必须与 CSS .lined-textarea 的 font-size × line-height 保持一致
  const LINE_HEIGHT_PX = 16 * 1.7; // 27.2px

  function syncScroll() {
    if (lineNumRef.current && textareaRef.current) {
      lineNumRef.current.scrollTop = textareaRef.current.scrollTop;
    }
  }

  function handleLineClick(lineNum: number) {
    setActiveLine(lineNum);
    const ta = textareaRef.current;
    if (!ta) return;
    const paddingTop = 16; // .lined-textarea padding-top
    const targetTop = paddingTop + (lineNum - 1) * LINE_HEIGHT_PX;
    ta.scrollTop = Math.max(0, targetTop - ta.clientHeight / 3);
  }

  return (
    <div className="lined-textarea-wrapper">
      <div ref={lineNumRef} className="line-numbers">
        {Array.from({ length: lineCount }, (_, i) => (
          <div
            key={i + 1}
            className={`line-num-item${activeLine === i + 1 ? " line-num-active" : ""}`}
            onClick={() => handleLineClick(i + 1)}
          >
            {i + 1}
          </div>
        ))}
      </div>
      <textarea
        ref={textareaRef}
        className="lined-textarea"
        value={value}
        onChange={(e) => onChange(e.target.value)}
        onScroll={syncScroll}
        placeholder={placeholder}
      />
    </div>
  );
}

export function DiffWorkbench() {
  const [referenceText, setReferenceText] = useState("");
  const [ocrText, setOcrText] = useState("");
  const [options, setOptions] = useState<PreprocessOptions>(DEFAULT_OPTIONS);
  const [result, setResult] = useState<DiffResponse | null>(null);
  const [errorMessage, setErrorMessage] = useState("");
  const [isSubmitting, setIsSubmitting] = useState(false);

  // 文本来源（用于生成报告文件名）
  const [referenceSource, setReferenceSource] = useState<SourceState>({ type: "text" });
  const [ocrSource, setOcrSource] = useState<SourceState>({ type: "text" });

  // 侧边栏状态
  const [sidebarOpen, setSidebarOpen] = useState(false);
  const [reports, setReports] = useState<ReportListItem[]>([]);
  const [reportsLoading, setReportsLoading] = useState(false);

  // 上传替换确认弹窗状态
  const [confirmState, setConfirmState] = useState<ConfirmState>(null);

  // 隐藏的 file input 引用
  const referenceFileRef = useRef<HTMLInputElement>(null);
  const ocrFileRef = useRef<HTMLInputElement>(null);

  const loadReports = useCallback(async () => {
    setReportsLoading(true);
    try {
      const data = await fetchReportList();
      setReports(data);
    } catch {
      // 侧边栏静默失败，不影响主流程
    } finally {
      setReportsLoading(false);
    }
  }, []);

  // 每次打开侧边栏时刷新报告列表
  useEffect(() => {
    if (sidebarOpen) {
      loadReports();
    }
  }, [sidebarOpen, loadReports]);

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setErrorMessage("");
    setIsSubmitting(true);

    // 报告文件名组件：文件来源用文件名，文本来源用前5字符
    const referenceReportName =
      referenceSource.type === "file"
        ? referenceSource.stem
        : referenceText.trim().slice(0, 5) || "参考文本";
    const ocrReportName =
      ocrSource.type === "file"
        ? ocrSource.stem
        : ocrText.trim().slice(0, 5) || "OCR文本";

    try {
      const nextResult = await submitTextDiff({
        reference: referenceText,
        ocr: ocrText,
        referenceLabel: "参考文本",
        ocrLabel: "OCR文本",
        referenceReportName,
        ocrReportName,
        options,
      });
      setResult(nextResult);
    } catch (error) {
      setResult(null);
      setErrorMessage(error instanceof Error ? error.message : "提交失败，请稍后再试。");
    } finally {
      setIsSubmitting(false);
    }
  }

  function handleOptionChange(event: React.ChangeEvent<HTMLInputElement>) {
    const { name, checked } = event.target;
    setOptions((current) => ({ ...current, [name]: checked }));
  }

  function handleDiffModeChange(mode: "text_only" | "text_and_format") {
    setOptions((current) => ({ ...current, diff_mode: mode }));
  }

  /** 读取上传文件内容；若目标文本框已有内容则弹窗确认 */
  async function handleFileSelect(
    target: "reference" | "ocr",
    file: File,
    currentText: string,
    setter: (text: string) => void,
  ) {
    const content = await file.text();
    if (currentText.trim()) {
      setConfirmState({ target, newContent: content, filename: file.name });
    } else {
      setter(content);
      const stem = file.name.replace(/\.[^.]+$/, "");
      if (target === "reference") setReferenceSource({ type: "file", stem });
      else setOcrSource({ type: "file", stem });
    }
  }

  function handleReferenceUpload(e: React.ChangeEvent<HTMLInputElement>) {
    const file = e.target.files?.[0];
    if (!file) return;
    handleFileSelect("reference", file, referenceText, setReferenceText);
    // 清空 input，允许重复选同一文件
    e.target.value = "";
  }

  function handleOcrUpload(e: React.ChangeEvent<HTMLInputElement>) {
    const file = e.target.files?.[0];
    if (!file) return;
    handleFileSelect("ocr", file, ocrText, setOcrText);
    e.target.value = "";
  }

  /** 确认替换文本框内容 */
  function confirmReplace() {
    if (!confirmState) return;
    const stem = confirmState.filename.replace(/\.[^.]+$/, "");
    if (confirmState.target === "reference") {
      setReferenceText(confirmState.newContent);
      setReferenceSource({ type: "file", stem });
    } else {
      setOcrText(confirmState.newContent);
      setOcrSource({ type: "file", stem });
    }
    setConfirmState(null);
  }

  const reportUrl = result ? new URL(result.report_url, API_BASE_URL).toString() : "";

  return (
    <>
      {/* ───── 侧边栏 ───── */}
      {sidebarOpen && (
        <div className="sidebar-overlay" onClick={() => setSidebarOpen(false)} />
      )}
      <aside className={`sidebar${sidebarOpen ? " sidebar--open" : ""}`} aria-label="历史报告">
        <div className="sidebar-header">
          <span className="sidebar-title">历史报告</span>
          <button
            className="sidebar-close"
            onClick={() => setSidebarOpen(false)}
            type="button"
            aria-label="关闭侧边栏"
          >
            ✕
          </button>
        </div>
        <div className="sidebar-body">
          {reportsLoading ? (
            <p className="sidebar-hint">加载中…</p>
          ) : reports.length === 0 ? (
            <p className="sidebar-hint">暂无报告</p>
          ) : (
            <ul className="report-list">
              {reports.map((r) => (
                <li key={r.filename} className="report-list-item">
                  <a
                    href={new URL(r.url, API_BASE_URL).toString()}
                    target="_blank"
                    rel="noreferrer"
                    className="report-list-link"
                  >
                    <span className="report-list-name">{parseReportDisplayName(r.filename)}</span>
                    <span className="report-list-time">{r.created_at}</span>
                  </a>
                </li>
              ))}
            </ul>
          )}
        </div>
      </aside>

      {/* ───── 主内容 ───── */}
      <main className="page-shell">
        {/* 侧边栏打开按钮 */}
        <button
          className="sidebar-toggle"
          onClick={() => setSidebarOpen((v) => !v)}
          type="button"
          aria-label="查看历史报告"
        >
          历史报告
        </button>

        <section className="hero">
          <p className="eyebrow">可视化文本对比工具</p>
          <h1>TextDiff</h1>
          <p className="hero-copy">
            TextDiff 帮你生成详细的文本差异报告。支持直接粘贴文本或上传文件，并提供多种预处理选项。
          </p>
        </section>

        <section className="workspace-card">
          <form className="diff-form" onSubmit={handleSubmit}>
            {/* 对比模式选择 */}
            <div className="diff-mode-row">
              <span className="diff-mode-label">对比模式：</span>
              <label className="diff-mode-option">
                <input
                  type="radio"
                  name="diffMode"
                  value="text_only"
                  checked={options.diff_mode === "text_only"}
                  onChange={() => handleDiffModeChange("text_only")}
                />
                仅对比文本
              </label>
              <label className="diff-mode-option">
                <input
                  type="radio"
                  name="diffMode"
                  value="text_and_format"
                  checked={options.diff_mode === "text_and_format"}
                  onChange={() => handleDiffModeChange("text_and_format")}
                />
                对比文本与格式（逐行）
              </label>
            </div>

            {/* 双文本框，每框上方有上传按钮 */}
            <div className="input-grid">
              <div className="panel">
                <div className="panel-header">
                  <span className="panel-title">参考文本</span>
                  <button
                    type="button"
                    className="upload-btn"
                    onClick={() => referenceFileRef.current?.click()}
                  >
                    上传文件
                  </button>
                  <input
                    ref={referenceFileRef}
                    type="file"
                    accept=".md,.txt,.docx"
                    className="hidden-file-input"
                    onChange={handleReferenceUpload}
                  />
                </div>
                <LineNumberedTextarea
                  value={referenceText}
                  onChange={(v) => {
                    setReferenceText(v);
                    setReferenceSource({ type: "text" });
                  }}
                  placeholder="粘贴参考文本，或点击上方按钮上传 .md / .txt / .docx 文件"
                />
              </div>

              <div className="panel">
                <div className="panel-header">
                  <span className="panel-title">对比文本</span>
                  <button
                    type="button"
                    className="upload-btn"
                    onClick={() => ocrFileRef.current?.click()}
                  >
                    上传文件
                  </button>
                  <input
                    ref={ocrFileRef}
                    type="file"
                    accept=".md,.txt,.docx"
                    className="hidden-file-input"
                    onChange={handleOcrUpload}
                  />
                </div>
                <LineNumberedTextarea
                  value={ocrText}
                  onChange={(v) => {
                    setOcrText(v);
                    setOcrSource({ type: "text" });
                  }}
                  placeholder="粘贴需要对比的文本，或点击上方按钮上传 .md / .txt / .docx 文件"
                />
              </div>
            </div>

            {/* 预处理选项 */}
            <section className="panel options-panel">
              <div>
                <h2 className="panel-title">预处理选项</h2>
                <p className="panel-copy">选择你所需要的预处理策略</p>
              </div>
              <div className="option-grid">
                <label className="checkbox-row">
                  <input
                    checked={options.normalize_width}
                    name="normalize_width"
                    onChange={handleOptionChange}
                    type="checkbox"
                  />
                  统一全角/半角
                </label>
                <label className="checkbox-row">
                  <input
                    checked={options.normalize_punctuation}
                    name="normalize_punctuation"
                    onChange={handleOptionChange}
                    type="checkbox"
                  />
                  统一常见中英文标点
                </label>
                <label className="checkbox-row">
                  <input
                    checked={options.case_sensitive}
                    name="case_sensitive"
                    onChange={handleOptionChange}
                    type="checkbox"
                  />
                  区分英文字母大小写
                </label>
              </div>
            </section>

            {/* 居中对比按钮 */}
            <div className="action-row">
              <button className="submit-button" disabled={isSubmitting} type="submit">
                {isSubmitting ? "对比中…" : "开始对比"}
              </button>
            </div>
          </form>
        </section>

        {errorMessage ? <section className="feedback error">{errorMessage}</section> : null}

        {result ? (
          <section className="results-shell">
            <h2>对比结果</h2>
            <div className="stats-grid">
              <StatsCard label="准确率" value={`${result.stats.accuracy.toFixed(2)}%`} />
              <StatsCard label="参考文本总字数" value={`${result.stats.reference_length}`} />
              <StatsCard label="错误字符数" value={`${result.stats.error_count}`} />
              <StatsCard
                label="缺字 / 多字 / 错字"
                value={`${result.stats.delete_count} / ${result.stats.insert_count} / ${result.stats.replace_count}`}
              />
            </div>
            {/* 报告链接（不使用 iframe） */}
            <div className="report-link-row">
              <a className="report-full-link" href={reportUrl} rel="noreferrer" target="_blank">
                查看 HTML 差异报告 →
              </a>
            </div>
          </section>
        ) : null}
      </main>

      {/* ───── 上传替换确认弹窗 ───── */}
      {confirmState ? (
        <div className="dialog-overlay">
          <div className="dialog" role="dialog" aria-modal="true">
            <p className="dialog-message">
              当前文本框已有内容，是否用「{confirmState.filename}」的内容替换？
            </p>
            <div className="dialog-actions">
              <button
                className="dialog-btn dialog-btn--cancel"
                type="button"
                onClick={() => setConfirmState(null)}
              >
                取消
              </button>
              <button
                className="dialog-btn dialog-btn--confirm"
                type="button"
                onClick={confirmReplace}
              >
                替换
              </button>
            </div>
          </div>
        </div>
      ) : null}
    </>
  );
}

type StatsCardProps = {
  label: string;
  value: string;
};

function StatsCard({ label, value }: StatsCardProps) {
  return (
    <article className="stats-card">
      <span className="stats-label">{label}</span>
      <strong className="stats-value">{value}</strong>
    </article>
  );
}
