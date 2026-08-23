import { useRef, useState } from "react";
import { CheckCircle2, FileText, Upload, XCircle } from "lucide-react";
import { ApiError, createEvaluation, createJobDescription, uploadResume } from "../api/client";
import { Card, ErrorBanner, Spinner } from "./StatusPrimitives";

type FileStatus = "queued" | "uploading" | "evaluating" | "done" | "error";

interface FileEntry {
  id: string;
  file: File;
  status: FileStatus;
  candidateName?: string;
  error?: string;
}

const MIN_JD_LENGTH = 20;

export function SetupScreen({ onAnalysisComplete }: { onAnalysisComplete: (jdId: number) => void }) {
  const [jdText, setJdText] = useState("");
  const [entries, setEntries] = useState<FileEntry[]>([]);
  const [isRunning, setIsRunning] = useState(false);
  const [runError, setRunError] = useState<string | null>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);

  const jdValid = jdText.trim().length >= MIN_JD_LENGTH;
  const canAnalyze = jdValid && entries.length > 0 && !isRunning;

  function addFiles(fileList: FileList | null) {
    if (!fileList) return;
    const accepted = Array.from(fileList).filter((f) => /\.(pdf|txt)$/i.test(f.name));
    const newEntries: FileEntry[] = accepted.map((file) => ({
      id: `${file.name}-${file.size}-${crypto.randomUUID()}`,
      file,
      status: "queued",
    }));
    setEntries((prev) => [...prev, ...newEntries]);
  }

  function removeEntry(id: string) {
    setEntries((prev) => prev.filter((e) => e.id !== id));
  }

  function updateEntry(id: string, patch: Partial<FileEntry>) {
    setEntries((prev) => prev.map((e) => (e.id === id ? { ...e, ...patch } : e)));
  }

  async function runAnalysis() {
    setRunError(null);
    setIsRunning(true);
    try {
      const jd = await createJobDescription(jdText.trim());

      // Sequential, not parallel: keeps per-file status updates legible in
      // the UI and avoids bursting the LLM provider with concurrent calls
      // for what is, in the demo, a handful of resumes.
      for (const entry of entries) {
        if (entry.status === "done") continue;
        updateEntry(entry.id, { status: "uploading", error: undefined });
        try {
          const resume = await uploadResume(entry.file);
          if (resume.processing_status === "failed") {
            updateEntry(entry.id, {
              status: "error",
              error: resume.error_message ?? "Resume processing failed.",
            });
            continue;
          }
          updateEntry(entry.id, { status: "evaluating", candidateName: resume.candidate_name ?? undefined });
          await createEvaluation(resume.id, jd.id);
          updateEntry(entry.id, { status: "done" });
        } catch (err) {
          const message = err instanceof ApiError ? err.message : "Unexpected error processing this file.";
          updateEntry(entry.id, { status: "error", error: message });
        }
      }

      onAnalysisComplete(jd.id);
    } catch (err) {
      const message = err instanceof ApiError ? err.message : "Failed to analyze the job description.";
      setRunError(message);
    } finally {
      setIsRunning(false);
    }
  }

  return (
    <div className="mx-auto max-w-5xl px-6 py-10">
      <header className="mb-8">
        <h1 className="text-2xl font-semibold text-slate-900">Smart Resume Screener</h1>
        <p className="mt-1 text-slate-500">
          Upload a job description and candidate resumes for evidence-based, requirement-by-requirement
          matching -- not just a keyword score.
        </p>
      </header>

      <div className="grid grid-cols-1 gap-6 md:grid-cols-2">
        <Card className="p-5">
          <label htmlFor="jd-text" className="mb-2 block text-sm font-medium text-slate-700">
            Job Description
          </label>
          <textarea
            id="jd-text"
            value={jdText}
            onChange={(e) => setJdText(e.target.value)}
            placeholder="Paste the full job description here..."
            rows={14}
            className="w-full resize-none rounded-lg border border-slate-300 p-3 text-sm text-slate-800 focus:border-indigo-500 focus:outline-none focus:ring-1 focus:ring-indigo-500"
          />
          <p className={`mt-1 text-xs ${jdValid ? "text-slate-400" : "text-rose-500"}`}>
            {jdText.trim().length} characters {jdValid ? "" : `(minimum ${MIN_JD_LENGTH})`}
          </p>
        </Card>

        <Card className="p-5">
          <div className="mb-2 flex items-center justify-between">
            <span className="block text-sm font-medium text-slate-700">Candidate Resumes</span>
            <button
              type="button"
              onClick={() => fileInputRef.current?.click()}
              className="inline-flex items-center gap-1.5 rounded-lg border border-slate-300 px-3 py-1.5 text-sm font-medium text-slate-700 hover:bg-slate-50"
            >
              <Upload className="h-4 w-4" /> Add files
            </button>
            <input
              ref={fileInputRef}
              type="file"
              accept=".pdf,.txt"
              multiple
              className="hidden"
              onChange={(e) => {
                addFiles(e.target.files);
                e.target.value = "";
              }}
            />
          </div>

          {entries.length === 0 ? (
            <div
              onDragOver={(e) => e.preventDefault()}
              onDrop={(e) => {
                e.preventDefault();
                addFiles(e.dataTransfer.files);
              }}
              className="flex h-56 flex-col items-center justify-center gap-2 rounded-lg border-2 border-dashed border-slate-300 text-slate-400"
            >
              <FileText className="h-8 w-8" />
              <p className="text-sm">Drag PDF or .txt resumes here, or click "Add files"</p>
            </div>
          ) : (
            <ul className="max-h-56 space-y-2 overflow-y-auto">
              {entries.map((entry) => (
                <li
                  key={entry.id}
                  className="flex items-center justify-between rounded-lg border border-slate-200 px-3 py-2 text-sm"
                >
                  <div className="min-w-0 flex-1">
                    <p className="truncate font-medium text-slate-800">
                      {entry.candidateName ?? entry.file.name}
                    </p>
                    {entry.status === "error" && entry.error && (
                      <p className="truncate text-xs text-rose-600">{entry.error}</p>
                    )}
                  </div>
                  <FileStatusIcon status={entry.status} onRemove={() => removeEntry(entry.id)} />
                </li>
              ))}
            </ul>
          )}
        </Card>
      </div>

      {runError && (
        <div className="mt-6">
          <ErrorBanner message={runError} />
        </div>
      )}

      <div className="mt-8 flex justify-end">
        <button
          type="button"
          disabled={!canAnalyze}
          onClick={runAnalysis}
          className="inline-flex items-center gap-2 rounded-lg bg-indigo-600 px-5 py-2.5 text-sm font-semibold text-white shadow-sm hover:bg-indigo-500 disabled:cursor-not-allowed disabled:bg-slate-300"
        >
          {isRunning && <Spinner className="h-4 w-4" />}
          {isRunning ? "Analyzing candidates..." : "Analyze Candidates"}
        </button>
      </div>
    </div>
  );
}

function FileStatusIcon({ status, onRemove }: { status: FileStatus; onRemove: () => void }) {
  if (status === "queued") {
    return (
      <button type="button" onClick={onRemove} className="text-slate-400 hover:text-slate-600">
        <XCircle className="h-4 w-4" />
      </button>
    );
  }
  if (status === "uploading" || status === "evaluating") {
    return (
      <span className="flex items-center gap-1.5 text-xs text-indigo-600">
        <Spinner className="h-3.5 w-3.5" />
        {status === "uploading" ? "Extracting..." : "Evaluating..."}
      </span>
    );
  }
  if (status === "done") {
    return <CheckCircle2 className="h-4 w-4 text-emerald-500" />;
  }
  return <XCircle className="h-4 w-4 text-rose-500" />;
}
