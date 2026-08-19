# Contributing to FactorLab

Thanks for your interest in improving FactorLab! This guide covers local setup, conventions, and how to submit changes.

## 🧰 Environment

- **Python 3.11+** and **[uv](https://github.com/astral-sh/uv)** (package manager).
- Node is **not** required for the default frontend (it is a build-free CDN SPA). Only needed if you work on the optional `frontend/` Vite build.

```bash
# clone
git clone https://github.com/dev-belly/ashare-multifactor-research.git
cd ashare-multifactor-research

# create env + install deps (reproducible via uv.lock)
uv sync

# optional: real A-share data support
uv sync --extra data-akshare
```

## 🏃 Running

```bash
uv run factorlab run --models eq_weight,elastic_net,lightgbm,deep --hpo 8   # pipeline
uv run factorlab serve                                                      # dashboard
uv run factorlab report                                                     # HTML report
uv run pytest                                                               # tests
```

## 📐 Conventions

- **Code style:** `ruff` (line length 100). Run `uv run ruff check .` and `uv run ruff format .` before committing.
- **Types:** prefer typed signatures; config lives in `factorlab/config.py` (pydantic-settings).
- **Tests:** add/adjust tests under `tests/` for new factor/model/eval logic.
- **Commits:** clear, imperative subject lines (e.g. `feat:`, `fix:`, `docs:`, `ci:`).
- **No look-ahead bias:** any change to data/factors/backtest must preserve OOS discipline (expanding window, T+90 report lag, trade-day rebalance). Add a test/note if you touch this.

## 📦 Pull Requests

1. Fork → create a feature branch (`feat/...`, `fix/...`).
2. Make changes + ensure `uv run ruff check .` and `uv run pytest` pass.
3. Keep PRs focused; describe **what** and **why**.
4. Open the PR; CI (Python + frontend) must be green.

## 🐛 Issues

Please use issue templates where possible: bug report, feature request, or question. Include versions (`uv run factorlab version`) and minimal repro steps.

## 📜 License

By contributing, you agree your contributions are licensed under the [MIT License](LICENSE).
