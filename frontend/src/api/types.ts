// Mirrors backend/app/schemas/*.py -- keep in sync manually (no codegen
// step for a project this size; see README "Trade-offs").

export type ProcessingStatus = "pending" | "processing" | "completed" | "failed";
export type SkillMatchType = "exact" | "normalized" | "unmatched";
export type RequirementPriority = "must_have" | "preferred";
export type RequirementCategory = "skill" | "experience" | "education" | "responsibility";
export type MatchLevel = "strong" | "partial" | "weak" | "not_demonstrated";
export type LLMStatus = "success" | "fallback" | "failed";

export interface SkillOut {
  raw_text: string;
  canonical_name: string;
  category: string | null;
  match_type: SkillMatchType;
}

export interface ExperienceOut {
  title: string | null;
  company: string | null;
  start_date: string | null;
  end_date: string | null;
  is_current: boolean;
  description: string | null;
}

export interface EducationOut {
  degree: string | null;
  institution: string | null;
  field_of_study: string | null;
  graduation_year: string | null;
}

export interface ResumeOut {
  id: number;
  filename: string;
  file_type: string;
  candidate_name: string | null;
  candidate_email: string | null;
  processing_status: ProcessingStatus;
  error_message: string | null;
  created_at: string;
  skills: SkillOut[];
  experience_entries: ExperienceOut[];
  education_entries: EducationOut[];
}

export interface JDRequirementOut {
  id: number;
  requirement_text: string;
  priority: RequirementPriority;
  category: RequirementCategory;
}

export interface JobDescriptionOut {
  id: number;
  job_title: string | null;
  created_at: string;
  requirements: JDRequirementOut[];
}

export interface RequirementMatchOut {
  requirement_text: string;
  priority: RequirementPriority;
  category: RequirementCategory;
  match_level: MatchLevel;
  evidence: string[];
  reasoning: string;
  confidence: number;
}

export interface EvaluationOut {
  id: number;
  resume_id: number;
  jd_id: number;
  overall_score: number;
  deterministic_component: number | null;
  llm_component: number;
  confidence: number;
  ai_summary: string | null;
  strengths: string[];
  gaps: string[];
  interview_focus_areas: string[];
  llm_status: LLMStatus;
  created_at: string;
  requirement_matches: RequirementMatchOut[];
}

export interface EvaluationSummaryOut {
  id: number;
  resume_id: number;
  candidate_name: string | null;
  filename: string;
  overall_score: number;
  confidence: number;
  llm_status: LLMStatus;
  top_strength: string | null;
  biggest_gap: string | null;
  created_at: string;
}

export interface ApiErrorBody {
  error: { code: string; message: string };
}
