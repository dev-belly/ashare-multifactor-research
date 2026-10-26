# Support

A-share factor research with purged out-of-sample evaluation, next-close execution and browser reports; synthetic data by default.

## Start here

Read the [README](README.md) for setup, examples and method boundaries. The tested maintenance commands are defined in the [CI workflow](.github/workflows/ci.yml). Environment: Python 3.11+ with uv; Node.js 24 for the frontend.

```bash
uv sync --frozen --group dev
```

Start with the default synthetic provider. A strict AkShare run can fail while point-in-time financial normalization remains incomplete; quote-only partial mode and fallback must be explicit. Never share FACTORLAB_RUN_TOKEN, provider tokens, private datasets or server credentials.

## Ask a question or report a problem

Use [GitHub Issues](https://github.com/dev-belly/ashare-multifactor-research/issues) for usage questions, reproducible bugs and scoped feature proposals. English and Chinese reports are welcome. Check existing issues first and use the bug or feature form when it fits. Support is best effort; no response time or delivery date is promised.

Include the config, meta.actual_data_source, meta.fallback_reason, meta.data_load, model, scored-date coverage, fold outcomes and execution/cost assumptions. Describe partial AkShare data explicitly; strict financial normalization is not yet complete.

Include the commit SHA, operating system, dependency versions, exact command, expected behavior and a minimal reproduction. Share only redacted logs and data you are allowed to publish. Remove credentials, personal information and confidential or licensed records. For a suspected security vulnerability, follow [SECURITY.md](SECURITY.md) before posting details.

## Verify locally

Run relevant checks before reporting a regression or opening a pull request:

```bash
uv run ruff check --select E4,E7,E9,F factorlab tests
uv run pytest -q
uv run mkdocs build --strict
# For frontend changes:
cd frontend
npm ci --no-audit --no-fund
npm run build
```

These are verification commands, not a claim that a new environment has already passed them. For changes that affect results, retain input provenance, configuration and seeds alongside the output.
