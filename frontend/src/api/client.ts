import type {
  ApiErrorBody,
  EvaluationOut,
  EvaluationSummaryOut,
  JobDescriptionOut,
  ResumeOut,
} from "./types";

const BASE_URL = import.meta.env.VITE_API_BASE_URL ?? "http://localhost:8000/api";

export class ApiError extends Error {
  code: string;
  status: number;

  constructor(status: number, code: string, message: string) {
    super(message);
    this.status = status;
    this.code = code;
  }
}

async function handleResponse<T>(response: Response): Promise<T> {
  if (!response.ok) {
    let body: ApiErrorBody | null = null;
    try {
      body = await response.json();
    } catch {
      // response body wasn't JSON -- fall through to generic message below
    }
    const message = body?.error?.message ?? `Request failed with status ${response.status}`;
    const code = body?.error?.code ?? "unknown_error";
    throw new ApiError(response.status, code, message);
  }
  return response.json() as Promise<T>;
}

export async function uploadResume(file: File): Promise<ResumeOut> {
  const formData = new FormData();
  formData.append("file", file);
  const response = await fetch(`${BASE_URL}/resumes`, { method: "POST", body: formData });
  return handleResponse<ResumeOut>(response);
}

export async function createJobDescription(rawText: string): Promise<JobDescriptionOut> {
  const response = await fetch(`${BASE_URL}/job-descriptions`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ raw_text: rawText }),
  });
  return handleResponse<JobDescriptionOut>(response);
}

export async function createEvaluation(resumeId: number, jdId: number): Promise<EvaluationOut> {
  const response = await fetch(`${BASE_URL}/evaluations`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ resume_id: resumeId, jd_id: jdId }),
  });
  return handleResponse<EvaluationOut>(response);
}

export async function listEvaluations(jdId: number): Promise<EvaluationSummaryOut[]> {
  const response = await fetch(`${BASE_URL}/evaluations?jd_id=${jdId}`);
  return handleResponse<EvaluationSummaryOut[]>(response);
}

export async function getEvaluation(evaluationId: number): Promise<EvaluationOut> {
  const response = await fetch(`${BASE_URL}/evaluations/${evaluationId}`);
  return handleResponse<EvaluationOut>(response);
}

export async function getResume(resumeId: number): Promise<ResumeOut> {
  const response = await fetch(`${BASE_URL}/resumes/${resumeId}`);
  return handleResponse<ResumeOut>(response);
}
