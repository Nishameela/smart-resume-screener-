import { useEffect, useState } from "react";
import { ArrowLeft, GraduationCap, MessageSquareText } from "lucide-react";
import { ApiError, getEvaluation, getResume } from "../api/client";
import type { EvaluationOut, ResumeOut } from "../api/types";
import { LLMStatusBadge, SkillMatchBadge } from "./badges";
import { Card, ErrorBanner, SectionTitle, Spinner } from "./StatusPrimitives";
import { ScoreBar, ScoreGauge } from "./ScoreGauge";
import { RequirementMatchCard } from "./RequirementMatchCard";
import { formatConfidence } from "../lib/format";

export function CandidateDetailScreen({ evaluationId, onBack }: { evaluationId: number; onBack: () => void }) {
  const [evaluation, setEvaluation] = useState<EvaluationOut | null>(null);
  const [resume, setResume] = useState<ResumeOut | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    setEvaluation(null);
    setResume(null);
    setError(null);

    getEvaluation(evaluationId)
      .then(async (evalData) => {
        if (cancelled) return;
        setEvaluation(evalData);
        const resumeData = await getResume(evalData.resume_id);
        if (!cancelled) setResume(resumeData);
      })
      .catch((err) => {
        if (cancelled) return;
        setError(err instanceof ApiError ? err.message : "Failed to load candidate detail.");
      });

    return () => {
      cancelled = true;
    };
  }, [evaluationId]);

  return (
    <div className="mx-auto max-w-4xl px-6 py-10">
      <button
        type="button"
        onClick={onBack}
        className="mb-4 inline-flex items-center gap-1.5 text-sm font-medium text-slate-500 hover:text-slate-700"
      >
        <ArrowLeft className="h-4 w-4" /> Back to rankings
      </button>

      {error && <ErrorBanner message={error} />}

      {!error && (!evaluation || !resume) && (
        <div className="flex items-center gap-2 py-10 text-slate-500">
          <Spinner className="h-5 w-5" /> Loading candidate...
        </div>
      )}

      {evaluation && resume && (
        <div className="space-y-6">
          <Card className="p-6">
            <div className="flex flex-wrap items-start justify-between gap-4">
              <div>
                <h1 className="text-2xl font-semibold text-slate-900">
                  {resume.candidate_name ?? resume.filename}
                </h1>
                {resume.candidate_email && <p className="text-sm text-slate-500">{resume.candidate_email}</p>}
                <div className="mt-2">
                  <LLMStatusBadge status={evaluation.llm_status} />
                </div>
              </div>
              <ScoreGauge score={evaluation.overall_score} size={88} />
            </div>

            <div className="mt-6 grid grid-cols-1 gap-4 sm:grid-cols-3">
              <ScoreBar label="Overall Score" score={evaluation.overall_score} />
              <ScoreBar label="AI-Grounded Evaluation" score={evaluation.llm_component} />
              <ScoreBar label="Deterministic (Rule-Based) Only" score={evaluation.deterministic_component} />
            </div>
            <p className="mt-3 text-xs text-slate-400">
              Overall confidence: {formatConfidence(evaluation.confidence)}
            </p>

            {evaluation.ai_summary && (
              <div className="mt-5 flex items-start gap-2 rounded-lg bg-indigo-50 px-4 py-3 text-sm text-indigo-900">
                <MessageSquareText className="mt-0.5 h-4 w-4 shrink-0" />
                <p>{evaluation.ai_summary}</p>
              </div>
            )}
          </Card>

          {(evaluation.strengths.length > 0 || evaluation.gaps.length > 0) && (
            <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
              {evaluation.strengths.length > 0 && (
                <Card className="p-5">
                  <SectionTitle>Strengths</SectionTitle>
                  <ul className="space-y-1.5 text-sm text-slate-700">
                    {evaluation.strengths.map((s, i) => (
                      <li key={i} className="flex gap-2">
                        <span className="text-emerald-500">+</span> {s}
                      </li>
                    ))}
                  </ul>
                </Card>
              )}
              {evaluation.gaps.length > 0 && (
                <Card className="p-5">
                  <SectionTitle>Gaps</SectionTitle>
                  <ul className="space-y-1.5 text-sm text-slate-700">
                    {evaluation.gaps.map((g, i) => (
                      <li key={i} className="flex gap-2">
                        <span className="text-rose-500">-</span> {g}
                      </li>
                    ))}
                  </ul>
                </Card>
              )}
            </div>
          )}

          <Card className="p-5">
            <SectionTitle>Requirement-by-Requirement Match</SectionTitle>
            <div className="space-y-3">
              {evaluation.requirement_matches.map((match, i) => (
                <RequirementMatchCard key={i} match={match} />
              ))}
            </div>
          </Card>

          <Card className="p-5">
            <SectionTitle>Skills</SectionTitle>
            {resume.skills.length === 0 ? (
              <p className="text-sm text-slate-400">No skills extracted.</p>
            ) : (
              <div className="flex flex-wrap gap-2">
                {resume.skills.map((skill, i) => (
                  <span
                    key={i}
                    className="inline-flex items-center gap-1.5 rounded-full border border-slate-200 px-3 py-1 text-sm text-slate-700"
                  >
                    {skill.canonical_name}
                    {skill.raw_text !== skill.canonical_name && (
                      <span className="text-xs text-slate-400">("{skill.raw_text}")</span>
                    )}
                    <SkillMatchBadge matchType={skill.match_type} />
                  </span>
                ))}
              </div>
            )}
          </Card>

          {(resume.experience_entries.length > 0 || resume.education_entries.length > 0) && (
            <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
              {resume.experience_entries.length > 0 && (
                <Card className="p-5">
                  <SectionTitle>Experience</SectionTitle>
                  <ul className="space-y-3">
                    {resume.experience_entries.map((exp, i) => (
                      <li key={i} className="text-sm">
                        <p className="font-medium text-slate-800">
                          {exp.title ?? "Role"} {exp.company ? `@ ${exp.company}` : ""}
                        </p>
                        <p className="text-xs text-slate-400">
                          {exp.start_date ?? "?"} - {exp.is_current ? "Present" : exp.end_date ?? "?"}
                        </p>
                        {exp.description && <p className="mt-1 text-slate-600">{exp.description}</p>}
                      </li>
                    ))}
                  </ul>
                </Card>
              )}
              {resume.education_entries.length > 0 && (
                <Card className="p-5">
                  <SectionTitle>Education</SectionTitle>
                  <ul className="space-y-3">
                    {resume.education_entries.map((edu, i) => (
                      <li key={i} className="flex items-start gap-2 text-sm">
                        <GraduationCap className="mt-0.5 h-4 w-4 shrink-0 text-slate-400" />
                        <div>
                          <p className="font-medium text-slate-800">{edu.degree ?? "Degree"}</p>
                          <p className="text-slate-500">
                            {edu.institution}
                            {edu.field_of_study ? `, ${edu.field_of_study}` : ""}
                            {edu.graduation_year ? ` (${edu.graduation_year})` : ""}
                          </p>
                        </div>
                      </li>
                    ))}
                  </ul>
                </Card>
              )}
            </div>
          )}

          {evaluation.interview_focus_areas.length > 0 && (
            <Card className="p-5">
              <SectionTitle>Interview Focus Areas</SectionTitle>
              <ul className="space-y-1.5 text-sm text-slate-700">
                {evaluation.interview_focus_areas.map((topic, i) => (
                  <li key={i} className="flex gap-2">
                    <span className="text-indigo-500">?</span> {topic}
                  </li>
                ))}
              </ul>
            </Card>
          )}
        </div>
      )}
    </div>
  );
}
