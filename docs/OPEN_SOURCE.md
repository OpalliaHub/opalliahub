# Open-source scope and data provenance

The original JobCompass application code and project-authored documentation are offered under the **MIT License** in the repository's `LICENSE`. The license is the standard [MIT template published by the Open Source Initiative](https://opensource.org/license/mit). Copyright attribution uses “JobCompass contributors”; actual contributions and AI assistance should be described accurately.

The following distinctions matter when reusing or publishing this project:

| Material | Treatment |
|---|---|
| Original Python/JavaScript/CSS, build configuration and project-authored documentation | MIT, with the repository notice retained |
| Third-party Python/JavaScript dependencies and server/proxy software | Their respective upstream licenses; installing or vendoring them does not relicense them under this project's MIT file |
| `data/demo_jobs.json` and demo resume | Clearly fictional demonstration fixtures; do not present them as actual job openings or a real candidate |
| Existing selected JobsDB historical snapshot and manifest | Source-derived benchmark material, not original application code; the project's MIT license does not grant rights over third-party job advertisements |
| Large research database, raw crawls and visitor resumes/notes/results | Private runtime/research data; excluded from the source build context and public delivery |
| API credentials and local configuration | Runtime secrets; not source assets |

The selected snapshot is historical and preserves its existing provenance manifest. This iteration did not establish a new redistribution license for the source advertisements. Anyone republishing data should use the applicable source permissions and provenance; code availability by itself does not settle data rights. No claim of human-labelled ground truth, current vacancy availability or labour-market representativeness follows from including a benchmark sample.

The Docker build configuration uses an explicit allowlist, including only the existing selected snapshot and fictional fixtures. A custom source-only distribution can omit the selected snapshot and initialize with synthetic demo data using `--demo`; it must describe that change so users do not confuse a demo with live recruitment information.

Contributions should identify the problem, include reproducible validation, disclose relevant AI assistance and retain data-source caveats. Do not submit personal resumes, account tokens, local databases, raw research archives or fabricated peer-review records. [QUALITY_WORKFLOW.md](QUALITY_WORKFLOW.md), the PR template and [AGENTS.md](../AGENTS.md) describe the project's engineering process.
