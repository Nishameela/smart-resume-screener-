import type { LLMStatus, MatchLevel, RequirementPriority, SkillMatchType } from "../api/types";

const MATCH_LEVEL_STYLES: Record<MatchLevel, string> = {
  strong: "bg-emerald-100 text-emerald-800 ring-emerald-600/20",
  partial: "bg-amber-100 text-amber-800 ring-amber-600/20",
  weak: "bg-orange-100 text-orange-800 ring-orange-600/20",
  not_demonstrated: "bg-slate-100 text-slate-600 ring-slate-500/20",
};

const MATCH_LEVEL_LABELS: Record<MatchLevel, string> = {
  strong: "Strong Match",
  partial: "Partial Match",
  weak: "Weak Match",
  not_demonstrated: "Not Demonstrated",
};

export function MatchLevelBadge({ level }: { level: MatchLevel }) {
  return (
    <span
      className={`inline-flex items-center rounded-full px-2.5 py-1 text-xs font-medium ring-1 ring-inset ${MATCH_LEVEL_STYLES[level]}`}
    >
      {MATCH_LEVEL_LABELS[level]}
    </span>
  );
}

export function PriorityBadge({ priority }: { priority: RequirementPriority }) {
  return priority === "must_have" ? (
    <span className="inline-flex items-center rounded-full bg-indigo-100 px-2.5 py-1 text-xs font-medium text-indigo-800 ring-1 ring-inset ring-indigo-600/20">
      Must Have
    </span>
  ) : (
    <span className="inline-flex items-center rounded-full bg-slate-100 px-2.5 py-1 text-xs font-medium text-slate-600 ring-1 ring-inset ring-slate-500/20">
      Preferred
    </span>
  );
}

const SKILL_MATCH_STYLES: Record<SkillMatchType, string> = {
  exact: "bg-blue-100 text-blue-800 ring-blue-600/20",
  normalized: "bg-purple-100 text-purple-800 ring-purple-600/20",
  unmatched: "bg-slate-100 text-slate-600 ring-slate-500/20",
};

const SKILL_MATCH_LABELS: Record<SkillMatchType, string> = {
  exact: "Exact",
  normalized: "Normalized",
  unmatched: "Unmatched",
};

export function SkillMatchBadge({ matchType }: { matchType: SkillMatchType }) {
  return (
    <span
      className={`inline-flex items-center rounded-full px-2 py-0.5 text-[10px] font-semibold uppercase tracking-wide ring-1 ring-inset ${SKILL_MATCH_STYLES[matchType]}`}
    >
      {SKILL_MATCH_LABELS[matchType]}
    </span>
  );
}

export function LLMStatusBadge({ status }: { status: LLMStatus }) {
  if (status === "success") {
    return (
      <span className="inline-flex items-center gap-1 rounded-full bg-emerald-50 px-2.5 py-1 text-xs font-medium text-emerald-700 ring-1 ring-inset ring-emerald-600/20">
        AI-Evaluated
      </span>
    );
  }
  return (
    <span className="inline-flex items-center gap-1 rounded-full bg-amber-50 px-2.5 py-1 text-xs font-medium text-amber-700 ring-1 ring-inset ring-amber-600/20">
      Deterministic Only
    </span>
  );
}
