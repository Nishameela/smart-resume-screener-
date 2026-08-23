import { useEffect, useState } from "react";
import { ArrowLeft, ChevronRight } from "lucide-react";
import { ApiError, listEvaluations } from "../api/client";
import type { EvaluationSummaryOut } from "../api/types";
import { LLMStatusBadge } from "./badges";
import { Card, ErrorBanner, Spinner } from "./StatusPrimitives";
import { ScoreGauge } from "./ScoreGauge";
import { formatConfidence } from "../lib/format";

export function RankingsScreen({
  jdId,
  onSelectEvaluation,
  onBack,
}: {
  jdId: number;
  onSelectEvaluation: (evaluationId: number) => void;
  onBack: () => void;
}) {
  const [evaluations, setEvaluations] = useState<EvaluationSummaryOut[] | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    setEvaluations(null);
    setError(null);
    listEvaluations(jdId)
      .then((data) => {
        if (!cancelled) setEvaluations(data);
      })
      .catch((err) => {
        if (cancelled) return;
        setError(err instanceof ApiError ? err.message : "Failed to load candidate rankings.");
      });
    return () => {
      cancelled = true;
    };
  }, [jdId]);

  return (
    <div className="mx-auto max-w-5xl px-6 py-10">
      <button
        type="button"
        onClick={onBack}
        className="mb-4 inline-flex items-center gap-1.5 text-sm font-medium text-slate-500 hover:text-slate-700"
      >
        <ArrowLeft className="h-4 w-4" /> New analysis
      </button>

      <header className="mb-6">
        <h1 className="text-2xl font-semibold text-slate-900">Candidate Rankings</h1>
        <p className="mt-1 text-slate-500">Ranked by overall match score. Click a candidate for the full evidence breakdown.</p>
      </header>

      {error && <ErrorBanner message={error} />}

      {!error && evaluations === null && (
        <div className="flex items-center gap-2 py-10 text-slate-500">
          <Spinner className="h-5 w-5" /> Loading rankings...
        </div>
      )}

      {evaluations !== null && evaluations.length === 0 && (
        <Card className="p-8 text-center text-slate-500">No candidates have been evaluated for this job yet.</Card>
      )}

      {evaluations !== null && evaluations.length > 0 && (
        <div className="space-y-3">
          {evaluations.map((evaluation, index) => (
            <Card
              key={evaluation.id}
              className="cursor-pointer p-4 transition hover:border-indigo-300 hover:shadow-md"
            >
              <button
                type="button"
                onClick={() => onSelectEvaluation(evaluation.id)}
                className="flex w-full items-center gap-4 text-left"
              >
                <span className="w-6 shrink-0 text-center text-sm font-semibold text-slate-400">
                  #{index + 1}
                </span>
                <ScoreGauge score={evaluation.overall_score} size={56} />
                <div className="min-w-0 flex-1">
                  <div className="flex items-center gap-2">
                    <h3 className="truncate font-semibold text-slate-900">
                      {evaluation.candidate_name ?? evaluation.filename}
                    </h3>
                    <LLMStatusBadge status={evaluation.llm_status} />
                  </div>
                  <p className="mt-0.5 truncate text-sm text-slate-500">
                    Confidence {formatConfidence(evaluation.confidence)}
                  </p>
                  <div className="mt-1.5 grid grid-cols-1 gap-x-4 gap-y-0.5 text-xs text-slate-600 sm:grid-cols-2">
                    {evaluation.top_strength && (
                      <p className="truncate">
                        <span className="font-medium text-emerald-700">Strength:</span> {evaluation.top_strength}
                      </p>
                    )}
                    {evaluation.biggest_gap && (
                      <p className="truncate">
                        <span className="font-medium text-rose-700">Gap:</span> {evaluation.biggest_gap}
                      </p>
                    )}
                  </div>
                </div>
                <ChevronRight className="h-5 w-5 shrink-0 text-slate-300" />
              </button>
            </Card>
          ))}
        </div>
      )}
    </div>
  );
}
