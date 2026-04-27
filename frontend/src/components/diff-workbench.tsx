"use client";

import { ChangeEvent, FormEvent, useState } from "react";

import { submitFileDiff, submitTextDiff } from "@/lib/api";
import type {
  DiffMode,
  DiffResponse,
  DiffStats,
  PreprocessOptions,
} from "@/lib/types";

const DEFAULT_OPTIONS: PreprocessOptions = {
  normalize_width: true,
  normalize_punctuation: true,
  case_sensitive: false,
};

const API_BASE_URL = process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://127.0.0.1:8000";

export function DiffWorkbench() {
  const [mode, setMode] = useState<DiffMode>("text");
  const [referenceText, setReferenceText] = useState("");
  const [ocrText, setOcrText] = useState("");
  const [referenceFile, setReferenceFile] = useState<File | null>(null);
  const [ocrFile, setOcrFile] = useState<File | null>(null);
  const [options, setOptions] = useState<PreprocessOptions>(DEFAULT_OPTIONS);
  const [result, setResult] = useState<DiffResponse | null>(null);
  const [errorMessage, setErrorMessage] = useState("");
  const [isSubmitting, setIsSubmitting] = useState(false);

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setErrorMessage("");
    setIsSubmitting(true);

    try {
      // 这里把文本模式和文件模式都收敛到同一个提交按钮，目的是让页面结构尽量简单。
      // 当前阶段只追求最小可用，因此不拆复杂状态机，而是在提交前做必要校验即可。
      const nextResult =
        mode === "text"
          ? await submitTextDiff({
              reference: referenceText,
              ocr: ocrText,
              referenceLabel: "文本输入-参考文本",
              ocrLabel: "文本输入-OCR文本",
              options,
            })
          : await submitFileDiff({
              referenceFile,
              ocrFile,
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

  function handleOptionChange(event: ChangeEvent<HTMLInputElement>) {
    const { name, checked } = event.target;
    setOptions((current) => ({
      ...current,
      [name]: checked,
    }));
  }

  function handleReferenceFileChange(event: ChangeEvent<HTMLInputElement>) {
    setReferenceFile(event.target.files?.[0] ?? null);
  }

  function handleOcrFileChange(event: ChangeEvent<HTMLInputElement>) {
    setOcrFile(event.target.files?.[0] ?? null);
  }

  const reportUrl = result ? new URL(result.report_url, API_BASE_URL).toString() : "";

  return (
    <main className="page-shell">
      <section className="hero">
        <p className="eyebrow">可视化文本对比工具</p>
        <h1>TextDiff</h1>
        <p className="hero-copy">
          TextDiff 都能帮你生成详细的文本差异报告。支持多种预处理选项，满足不同场景需求
        </p>
      </section>

      <section className="workspace-card">
        <div className="mode-switch" role="tablist" aria-label="输入模式切换">
          <button
            className={mode === "text" ? "mode-button active" : "mode-button"}
            onClick={() => setMode("text")}
            type="button"
          >
            文本输入
          </button>
          <button
            className={mode === "file" ? "mode-button active" : "mode-button"}
            onClick={() => setMode("file")}
            type="button"
          >
            文件上传
          </button>
        </div>

        <form className="diff-form" onSubmit={handleSubmit}>
          {mode === "text" ? (
            <div className="input-grid">
              <label className="panel">
                <span className="panel-title">参考文本</span>
                <textarea
                  className="textarea"
                  value={referenceText}
                  onChange={(event) => setReferenceText(event.target.value)}
                  placeholder="粘贴参考文本"
                />
              </label>
              <label className="panel">
                <span className="panel-title">对比文本</span>
                <textarea
                  className="textarea"
                  value={ocrText}
                  onChange={(event) => setOcrText(event.target.value)}
                  placeholder="粘贴所需要对比的文本"
                />
              </label>
            </div>
          ) : (
            <div className="input-grid">
              <label className="panel file-panel">
                <span className="panel-title">原始参考文件</span>
                <input className="file-input" type="file" accept=".md,.txt" onChange={handleReferenceFileChange} />
                <span className="file-hint">{referenceFile ? referenceFile.name : "请选择 .md 或 .txt 文件"}</span>
              </label>
              <label className="panel file-panel">
                <span className="panel-title">对比文件</span>
                <input className="file-input" type="file" accept=".md,.txt" onChange={handleOcrFileChange} />
                <span className="file-hint">{ocrFile ? ocrFile.name : "请选择 .md 或 .txt 文件"}</span>
              </label>
            </div>
          )}

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

          <div className="action-row flex justify-center">
            <button className="submit-button" disabled={isSubmitting} type="submit">
              {isSubmitting ? "对比中..." : "开始对比"}
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

          <div className="input-grid preview-grid">
            <section className="panel result-panel">
              <h3 className="panel-title">清洗后的参考文本</h3>
              <pre className="result-pre">{result.reference_text}</pre>
            </section>
            <section className="panel result-panel">
              <h3 className="panel-title">清洗后的 OCR 文本</h3>
              <pre className="result-pre">{result.ocr_text}</pre>
            </section>
          </div>

          <section className="panel report-panel">
            <div className="report-header">
              <div>
                <h3 className="panel-title">HTML 报告</h3>
                <p className="panel-copy">当前最小版本直接复用后端生成的单文件 HTML 报告，前端只负责打开和嵌入。</p>
              </div>
              <a className="report-link" href={reportUrl} rel="noreferrer" target="_blank">
                新窗口打开报告
              </a>
            </div>
            <iframe className="report-frame" src={reportUrl} title="OCR HTML 报告预览" />
          </section>
        </section>
      ) : null}
    </main>
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