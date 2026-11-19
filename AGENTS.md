# JobCompass contributor instructions

Read `docs/SPECIFICATION.md` before changing behavior. The current release is v2: a workforce-research platform with anonymous public mode and retained personal job tools. Keep changes useful to visitors and researchers. Preserve historical verification evidence without relabeling its version or scope.

## Environment and validation

- Local core: Python 3.8+ and the standard library. Desktop extras are in `requirements.txt`.
- Production configuration: Python 3.12, `requirements-server.txt`, `jobcompass.wsgi:application`, one Gunicorn worker. The anonymous registry is process-local and guarded by a file lock; do not enable multiple workers/replicas without replacing session, task and quota coordination.
- `python -m unittest discover -v` runs offline business, HTTP, public-session and WSGI tests.
- `python scripts/quality_gate.py --help`, `mutation_check.py --help`, and `coverage_report.py --help` describe the existing quality tools.
- `python main.py --demo --db /tmp/jobcompass-demo.db --port 8766 --no-browser` starts an isolated matching demo. Research aggregates intentionally exclude synthetic ads.
- `python scripts/package_project.py` creates the allowlisted source archive. A configured package, CI workflow or container is not proof it was successfully built or deployed.

## Workflow

1. Identify the requirement and affected modules; retain FR01–FR20 meanings and assign new IDs for new v2 behavior.
2. For consequential behavior, write failing tests first and retain actual evidence. Never reconstruct, backdate or relabel a historical red/green run.
3. Validate input, parameterize SQL, and escape source/model-derived display text, including chart tooltips. Keep visitor-facing UI labels in Chinese.
4. Run targeted tests, then relevant integration gates; review the diff and report the exact scope and remaining unverified work. Do not copy an earlier test count into a newer release record.
5. Update current specifications and verification notes. Keep private archives outside the tracked tree and release packages.

## Public request and data boundaries

- `WebGateway` is the shared HTTP boundary for local and WSGI serving. Route public visitor requests through its scoped application; never return the operator application's private resume, notes, task registry or result files.
- Public visitors require no account/login. Opaque `Secure`, `HttpOnly`, `SameSite=Strict` cookies identify temporary private workspaces; they are bearer capabilities, not verified identities.
- Public writes require the exact configured HTTPS origin, allowed Host, `X-JobCompass: 1`, and the existing cross-site checks. Only explicitly trusted proxy peers may supply client IP headers.
- Classify new routes for private/shared data, administrative scope and AI admission. Shared-source connection/index building stay outside public visitor HTTP operations. Reuse the bounded executor, per-visitor task registry and admission-release callbacks.
- Treat session creation, expiry, busy-work retention, restart invalidation, rate limits and quota ownership as testable behavior. Never leak another visitor's state through an ID lookup, cache or error response.
- Public arbitrary-page collection defaults to disabled and may only use administrator-configured exact hosts with the public fetch boundary. Fixed API adapters and visitor imports remain separate capabilities. Do not weaken redirect, DNS, origin or proxy checks to make a test pass.
- Never print or commit `.env`, credentials, personal resumes, notes, visitor databases, raw research archives or infrastructure paths. Use fictional fixtures. Keep source archives/container build contexts allowlisted.

## Research, AI and interface contracts

- Preserve read-only source research access. The shared index is readable across visitors; generated results, cohorts and tasks belong to the requesting visitor.
- Model plans are typed data, never executable Python, shell, JavaScript or generated SQL. OLAP identifiers come from fixed maps and values use parameters. Generate displayed/exported statistical titles from the validated query; model-suggested titles belong only in clearly labeled advanced information.
- The v2 natural-command path compiles and automatically executes a valid OLAP instruction. Do not reintroduce a manual confirmation step into that authorized visitor flow. The older deep-research single-plan preview is a separate retained feature.
- Keep the default `analytics` homepage, the platform workspace and the persistent right-side DeepSeek conversation consistent. On narrow screens use the implemented platform/chat switch. Conversation navigation must not invent successful results or silently relabel stale charts.
- Send only permitted query structure and bounded aggregates to analytical AI. Do not attach raw result rows, resumes, ad descriptions, source paths or hidden text-filter values as follow-up context. Explicit user command text is transmitted as entered; communicate that accurately.
- Scores are ranking indicators; sample mention rates are not overall market demand or hiring probabilities. Learning prerequisites are authored suggestions. Compute totals independently of limited groups, preserve unknown rates/gaps, and never sum distinct-employer counts or average group percentages into a false overall rate.
- Metadata-only current catalogs may use `_current(include_mask=False)`. Actual analytical queries must retain the default full-mask snapshot. Fetch detailed catalog data only for the selected dataset; optional metadata is not a zero count.
- Do not crawl or call paid AI in CI. Distinguish logical model turns, HTTP retry attempts, admission quotas and provider billing. Mocked tests do not certify model interpretation quality.

## Evidence and release claims

Use `docs/V2_VERIFICATION.md` and its linked release-specific records for verification. Document real commands, artifacts and limitations. Do not fabricate peer review, user evaluation, human relevance labels or deployment results. Do not claim GitHub publication, remote CI, Docker builds, TLS readiness or cloud deployment without observing that outcome. User authorization persists across turns; preserve user data and uncommitted changes and do not force-push or delete history to simplify delivery.
