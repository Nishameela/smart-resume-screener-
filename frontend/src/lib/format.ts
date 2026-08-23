export function formatScore(score: number): string {
  return Math.round(score).toString();
}

export function formatConfidence(confidence: number): string {
  return `${Math.round(confidence * 100)}%`;
}

export function scoreTone(score: number): "strong" | "medium" | "weak" {
  if (score >= 70) return "strong";
  if (score >= 40) return "medium";
  return "weak";
}
