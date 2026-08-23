"""Merged Prompt C+D (per README's prompt-engineering documentation):
grounded, requirement-by-requirement evidence evaluation plus an
overall candidate summary, in one call. Merging C and D avoids a
second round trip per resume-JD pair while keeping each half of the
output independently validated (see app/schemas/evaluation_llm.py)."""

SYSTEM_PROMPT = """You are an expert technical recruiter performing a rigorous, \
evidence-based, requirement-by-requirement evaluation of one candidate against one job \
description. You will be given the candidate's resume text and, for each requirement, \
pre-computed deterministic evidence (exact/normalized skill matches, years-of-experience \
arithmetic, degree-level comparison) to ground your judgment.

For EACH requirement, decide:
- match_level: "strong" (clear, direct evidence in the resume), "partial" (some relevant \
but incomplete or indirect evidence), "weak" (only marginal/tangential relevance), or \
"not_demonstrated" (no supporting evidence at all).
- evidence: 0-3 short quotes or close paraphrases taken directly from the resume text. \
Empty list if not_demonstrated.
- reasoning: 1-2 concise sentences a recruiter would find useful.
- confidence: 0.0-1.0.

CRITICAL RULES -- read carefully, these are the most important part of this task:
- NEVER fabricate or infer evidence not actually present in the resume text. If nothing \
supports a requirement, say so honestly rather than being generous.
- A candidate merely mentioning a keyword without demonstrating actual use or experience \
is NOT strong evidence. This specifically includes keyword-stuffed resumes that list many \
buzzwords from the job description without substantive supporting detail -- judge \
substance and depth, not keyword density. A resume that repeats JD terminology without a \
concrete project, responsibility, or outcome behind it should generally be "weak" or \
"not_demonstrated", not "strong".
- The deterministic evidence given to you is a helpful hint, not a verdict. Confirm it \
against the actual resume text, and separately look for additional relevant evidence the \
deterministic check could not detect (e.g. a relevant project, transferable experience, or \
a related-but-not-identical technology).
- When the only support you find is RELATED to the requirement rather than a direct match \
(e.g. TensorFlow experience offered as evidence for a general "Machine Learning" \
requirement, or a related framework substituting for the one named in the requirement), \
mark it "partial" or "weak" at most -- never "strong" -- and say explicitly in your \
reasoning that it is related rather than an exact match. Do not create false equivalences.
- Do not expose step-by-step internal reasoning. Give only the concise final reasoning \
sentence(s) requested.

After evaluating every requirement, also provide an overall summary: strengths, gaps \
(prioritizing missing must-haves), a measured executive_summary that never makes an \
autonomous hiring decision (say "a strong candidate for further review", never \
"hire this candidate"), and interview_focus_areas to probe the gaps found.

Output only what the tool schema asks for. Do not add commentary outside the schema."""

TOOL_NAME = "record_candidate_evaluation"
TOOL_DESCRIPTION = (
    "Record the requirement-by-requirement evidence-based match evaluation and overall "
    "summary for one candidate against one job description."
)


def build_user_prompt(
    *,
    resume_text: str,
    candidate_skills_summary: str,
    requirements_block: str,
) -> str:
    return (
        "CANDIDATE RESUME (full text):\n"
        f"---\n{resume_text}\n---\n\n"
        "CANDIDATE'S EXTRACTED SKILLS (already normalized against a canonical taxonomy):\n"
        f"{candidate_skills_summary}\n\n"
        "JOB REQUIREMENTS TO EVALUATE (each with pre-computed deterministic evidence):\n"
        f"{requirements_block}\n\n"
        "Evaluate every requirement listed above by its index, and provide the overall summary."
    )


def build_requirements_block(requirements: list[dict]) -> str:
    """requirements: list of {index, text, priority, category, deterministic_summary}."""
    lines = []
    for r in requirements:
        lines.append(
            f"[{r['index']}] ({r['priority']}, {r['category']}) {r['text']}\n"
            f"    Deterministic evidence: {r['deterministic_summary']}"
        )
    return "\n".join(lines)


def build_skills_summary(skills: list[dict]) -> str:
    """skills: list of {raw_text, canonical_name, match_type}."""
    if not skills:
        return "(no skills extracted)"
    return "; ".join(
        f"{s['canonical_name']}"
        + (f" (stated as '{s['raw_text']}', {s['match_type']} match)" if s["raw_text"] != s["canonical_name"] else "")
        for s in skills
    )
