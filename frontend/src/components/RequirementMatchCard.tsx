import { Quote } from "lucide-react";
import type { RequirementMatchOut } from "../api/types";
import { MatchLevelBadge, PriorityBadge } from "./badges";
import { formatConfidence } from "../lib/format";

export function RequirementMatchCard({ match }: { match: RequirementMatchOut }) {
  return (
    <div className="rounded-lg border border-slate-200 p-4">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <div className="flex flex-wrap items-center gap-2">
          <PriorityBadge priority={match.priority} />
          <span className="text-xs uppercase tracking-wide text-slate-400">{match.category}</span>
        </div>
        <MatchLevelBadge level={match.match_level} />
      </div>

      <p className="mt-2 font-medium text-slate-900">{match.requirement_text}</p>

      {match.evidence.length > 0 && (
        <div className="mt-3 space-y-1.5">
          {match.evidence.map((quote, i) => (
            <div key={i} className="flex items-start gap-2 rounded-md bg-slate-50 px-3 py-2 text-sm text-slate-700">
              <Quote className="mt-0.5 h-3.5 w-3.5 shrink-0 text-slate-400" />
              <span className="italic">"{quote}"</span>
            </div>
          ))}
        </div>
      )}

      <p className="mt-2 text-sm text-slate-600">{match.reasoning}</p>
      <p className="mt-1.5 text-xs text-slate-400">Confidence: {formatConfidence(match.confidence)}</p>
    </div>
  );
}
