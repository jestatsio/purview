# Releasing

Releases publish to [PyPI](https://pypi.org/p/purview-authz) automatically when a
version tag is pushed. Authentication uses **Trusted Publishing** (OIDC), so no API
token is stored anywhere. The version is derived from the git tag by `hatch-vcs` —
there is no version to bump in `pyproject.toml`.

## One-time setup

1. **Register the trusted publisher on PyPI.** At
   <https://pypi.org/manage/account/publishing/>, add a *pending publisher* (for the
   first release) or a publisher on the existing project with exactly:

   | Field            | Value          |
   |------------------|----------------|
   | PyPI Project Name| `purview-authz`|
   | Owner            | `jestatsio`    |
   | Repository name  | `purview`      |
   | Workflow name    | `release.yml`  |
   | Environment name | `pypi`         |

2. **Create the GitHub environment.** In the repo, *Settings → Environments → New
   environment → `pypi`*. Optionally add protection rules (required reviewers, or
   restrict deployments to tags) — the publish job runs in this environment.

## Cutting a release

1. Move the `## [Unreleased]` section of [CHANGELOG.md](CHANGELOG.md) under the new
   version heading.
2. Tag and push:

   ```bash
   git tag v0.1.0
   git push origin v0.1.0
   ```

3. The **Release** workflow then: runs the full gate (ruff, mypy, tests) → builds the
   sdist + wheel → `twine check` → publishes to PyPI via OIDC.

The published version equals the tag without the `v` (e.g. `v0.1.0` → `0.1.0`).
Use [PEP 440](https://peps.python.org/pep-0440/) pre-release suffixes for
pre-releases, e.g. `v0.1.0rc1`.

## Verifying

After the workflow succeeds:

```bash
pip install purview-authz==0.1.0
python -c "import purview; print(purview.__version__)"
```

## Optional: TestPyPI dry run

To rehearse without touching PyPI, add a second publisher for the `testpypi`
environment and a publish step with
`uses: pypa/gh-action-pypi-publish@release/v1` plus
`with: { repository-url: https://test.pypi.org/legacy/ }`, gated on a separate
pre-release tag pattern.
