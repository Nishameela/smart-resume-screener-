# Demo Dataset

All candidates are clearly fictional, designed to exercise the four scenarios the
assignment brief asks for. Use `job_description.txt` as the JD, then upload all
four resumes together.

| File | Format | Scenario | Expected outcome |
|---|---|---|---|
| `candidate_1_strong_match_alex_chen.pdf` | PDF | Strong match | Directly satisfies nearly every must-have and preferred requirement with concrete, verifiable evidence. Should rank #1. |
| `candidate_2_partial_match_priya_sharma.txt` | Text | Partial match | Relevant Python/backend skills but real gaps: under the required years of experience, uses Django (not FastAPI/Flask), no cloud/Docker exposure. Should rank in the middle with clearly explained gaps. |
| `candidate_3_keyword_trap_sam_rivera.pdf` | PDF | Keyword trap | Skills section lists nearly every JD keyword (FastAPI, AWS, Docker, Kubernetes, PostgreSQL...), but the actual work experience is marketing and customer support with zero backend engineering, and the degree is unrelated. Deterministic skill-overlap alone would score this deceptively high; the grounded LLM evaluation should recognize the keywords aren't backed by real evidence and score it low. This is the core "why naive keyword matching fails" demo moment. |
| `candidate_4_transferable_match_jordan_kim.txt` | Text | Transferable/semantic match | 5+ years of genuine backend Python experience, but with Django REST Framework instead of FastAPI/Flask by name, and Google Cloud instead of AWS. No exact keyword hit on the named frameworks, but the underlying capability (building production REST APIs in Python) is clearly transferable. Should score well via semantic evidence even without exact keyword matches -- proving the system rewards genuine relevance, not just vocabulary overlap. |

Both file formats (PDF and plain text) are represented on purpose, since the
assignment requires accepting both.
