import { formatScore, scoreTone } from "../lib/format";

// Tailwind's scanner needs literal class strings in source -- never
// build class names via string concatenation/replace at runtime, or
// they silently won't be included in the generated CSS.
const TONE_STYLES: Record<string, { ring: string; text: string; track: string; bar: string }> = {
  strong: {
    ring: "stroke-emerald-500",
    text: "text-emerald-700",
    track: "stroke-emerald-100",
    bar: "bg-emerald-500",
  },
  medium: {
    ring: "stroke-amber-500",
    text: "text-amber-700",
    track: "stroke-amber-100",
    bar: "bg-amber-500",
  },
  weak: {
    ring: "stroke-rose-500",
    text: "text-rose-700",
    track: "stroke-rose-100",
    bar: "bg-rose-500",
  },
};

export function ScoreGauge({ score, size = 72 }: { score: number; size?: number }) {
  const tone = TONE_STYLES[scoreTone(score)];
  const radius = (size - 8) / 2;
  const circumference = 2 * Math.PI * radius;
  const offset = circumference * (1 - score / 100);

  return (
    <div className="relative inline-flex items-center justify-center" style={{ width: size, height: size }}>
      <svg width={size} height={size} className="-rotate-90">
        <circle cx={size / 2} cy={size / 2} r={radius} strokeWidth={6} fill="none" className={tone.track} />
        <circle
          cx={size / 2}
          cy={size / 2}
          r={radius}
          strokeWidth={6}
          fill="none"
          strokeLinecap="round"
          strokeDasharray={circumference}
          strokeDashoffset={offset}
          className={`${tone.ring} transition-[stroke-dashoffset] duration-500`}
        />
      </svg>
      <span className={`absolute text-lg font-semibold ${tone.text}`}>{formatScore(score)}</span>
    </div>
  );
}

export function ScoreBar({ label, score }: { label: string; score: number | null }) {
  const tone = score === null ? null : TONE_STYLES[scoreTone(score)];
  return (
    <div>
      <div className="mb-1 flex items-center justify-between text-sm">
        <span className="text-slate-600">{label}</span>
        <span className="font-medium text-slate-800">{score === null ? "N/A" : formatScore(score)}</span>
      </div>
      <div className="h-2 w-full overflow-hidden rounded-full bg-slate-100">
        {score !== null && tone && (
          <div className={`h-full rounded-full ${tone.bar}`} style={{ width: `${score}%` }} />
        )}
      </div>
    </div>
  );
}
