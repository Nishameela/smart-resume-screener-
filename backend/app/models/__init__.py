"""
Importing this package registers every ORM model on Base.metadata, so
`Base.metadata.create_all(engine)` (see app/core/database.py usage in
main.py's startup) creates the full schema in one call.
"""
from app.models.evaluation import Evaluation, RequirementMatch  # noqa: F401
from app.models.job_description import JDRequirement, JobDescription  # noqa: F401
from app.models.resume import (  # noqa: F401
    EducationEntry,
    ExperienceEntry,
    Resume,
    ResumeSkill,
)

__all__ = [
    "Resume",
    "ExperienceEntry",
    "EducationEntry",
    "ResumeSkill",
    "JobDescription",
    "JDRequirement",
    "Evaluation",
    "RequirementMatch",
]
