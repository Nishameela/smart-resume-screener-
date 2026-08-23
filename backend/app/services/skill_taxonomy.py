"""
Curated skill alias taxonomy: canonical name -> known alternate spellings
that refer to the *same* skill (e.g. "ReactJS" and "React" are the same
technology). This is deliberately a plain, versioned, unit-tested Python
config rather than a database table -- it's static reference data, not
per-run state (see README architecture section for the reasoning).

Deliberately does NOT include "related but not equivalent" pairs (e.g.
TensorFlow -> Machine Learning): conflating those with true aliases
would create unsafe false equivalences. Related-skill credit is a
semantic judgment the grounded LLM evaluation stage makes explicitly,
never the deterministic normalizer.

Not exhaustive -- extending it is just adding an entry here. See README
"Limitations" for how this could grow (e.g. sourced from O*NET/ESCO).
"""

SKILL_ALIASES: dict[str, list[str]] = {
    "React": ["reactjs", "react.js"],
    "JavaScript": ["js"],
    "TypeScript": ["ts"],
    "Node.js": ["node", "nodejs", "node js"],
    "PostgreSQL": ["postgres", "psql"],
    "Python": [],
    "FastAPI": ["fast api"],
    "Machine Learning": ["ml"],
    "AWS": ["amazon web services"],
    "Kubernetes": ["k8s"],
    "Docker": [],
    "CI/CD": ["continuous integration/continuous deployment", "continuous integration and deployment", "cicd"],
    "SQL": ["structured query language"],
    "MongoDB": ["mongo"],
    "C++": ["cpp", "c plus plus"],
    "C#": ["csharp", "c sharp"],
    ".NET": ["dotnet", "dot net"],
    "Java": [],
    "REST API": ["rest apis", "restful api", "restful apis", "rest"],
    "GraphQL": [],
    "Redis": [],
    "Git": [],
    "TensorFlow": ["tf"],
    "PyTorch": [],
    "NumPy": [],
    "Pandas": [],
    "Django": [],
    "Flask": [],
    "HTML": ["html5"],
    "CSS": ["css3"],
    "Vue.js": ["vue", "vuejs", "vue js"],
    "Angular": ["angularjs", "angular.js"],
    "MySQL": [],
    "SQLite": [],
    "Linux": [],
    "Bash": ["shell scripting", "shell"],
    "GCP": ["google cloud platform", "google cloud"],
    "Azure": ["microsoft azure"],
    "Express": ["express.js", "expressjs"],
    "Spring Boot": ["springboot"],
    "GitHub Actions": [],
    "Terraform": [],
    "Jenkins": [],
    "Agile": [],
    "Scrum": [],
    "R": [],
    "Scala": [],
    "Go": ["golang"],
    "Rust": [],
    "Swift": [],
    "Kotlin": [],
}
