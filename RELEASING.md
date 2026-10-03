# Releasing Purview

Versions come from Git tags through `hatch-vcs`. There is no version string to edit
in `pyproject.toml`. A tag such as `v0.3.1` produces `purview-authz==0.3.1`.

## Publisher setup

PyPI uses GitHub's OIDC trusted publishing. Configure the publisher with these
exact values on the [PyPI project](https://pypi.org/manage/project/purview-authz/settings/publishing/):

| Field | Value |
| --- | --- |
| Project | `purview-authz` |
| Owner | `jestatsio` |
| Repository | `purview` |
| Workflow | `release.yml` |
| Environment | `pypi` |

The GitHub repository needs a `pypi` environment. GitHub Pages uses the
`github-pages` environment and the Actions deployment source.

## Prepare and tag

1. Put release notes under an exact version heading in `CHANGELOG.md`, keeping an
   empty `Unreleased` section above it. Update the comparison links.
2. Merge the reviewed changes after CI passes. Inspect the exact commit to release.
3. On a clean, current `main`, create and push the version tag:

   ```bash
   git pull --ff-only origin main
   git tag -a v0.3.1 -m "Purview 0.3.1"
   git push origin v0.3.1
   ```

Use a new version for every publication. Supported prerelease tags include
`v0.4.0a1`, `v0.4.0b1`, and `v0.4.0rc1`.

## Automated gates

The Release workflow reuses CI for the tagged commit:

- SQLite and PostgreSQL tests on Python 3.11 through 3.14, including tracker smoke
  tests and the coverage gate.
- Ruff lint and formatting, strict mypy, a strict docs build, and the quickstart.
- Nonempty release notes matching the tag.
- Wheel and source distribution builds, strict metadata checks, rebuilding from the
  source distribution, and a clean wheel install with the optional integrations.
- Verification that the installed version matches the tag and includes `py.typed`.

Only after all checks pass does the workflow publish the tested artifacts to PyPI.
The final job creates a GitHub Release from the changelog and attaches the same
wheel and source distribution. Prerelease tags create prereleases on GitHub.

The Docs workflow deploys GitHub Pages from `main`. The site and PyPI publication
have separate outcomes, so verify both.

## Verify publication

Check the [Release workflow](https://github.com/jestatsio/purview/actions/workflows/release.yml),
the [GitHub Release](https://github.com/jestatsio/purview/releases), the
[PyPI version](https://pypi.org/project/purview-authz/), and the
[live docs](https://jestatsio.github.io/purview/). Then install from the public index
in a fresh environment:

```bash
uv venv /tmp/purview-release-check
uv pip install --python /tmp/purview-release-check/bin/python "purview-authz[fastapi,sqlite,postgres]==0.3.1"
RELEASE_TAG=v0.3.1 /tmp/purview-release-check/bin/python scripts/check_install.py
/tmp/purview-release-check/bin/python examples/quickstart.py
```

If verification fails before publishing, fix the problem and prepare a new tag.
If PyPI succeeds and only GitHub Release creation fails, rerun the failed GitHub
Release job. Never delete and reuse a published version.
