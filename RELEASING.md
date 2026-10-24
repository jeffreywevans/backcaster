# Releasing Backcaster

## Prepare 0.3.1

The package version is defined in `src/backcaster/__init__.py`; setuptools reads it
when building both distributions. Release notes are in `CHANGELOG.md`.

From the repository root, with Python 3.13+ and the development dependencies installed:

```bash
pytest --cov=src --cov-branch --cov-fail-under=100
ruff check src tests
ruff format --check src tests
mypy
python -m build
python -m pip install twine
python -m twine check --strict dist/*
```

Use a clean `dist/` directory for release builds so previous versions are not uploaded.
The Publish to PyPI workflow can be run manually on the release candidate branch
to build, check metadata, and smoke test the wheel without uploading to PyPI.

## Configure Trusted Publishing

On PyPI, configure the `backcaster` project's GitHub Trusted Publisher (or a pending
publisher if creating the project):

| Setting | Value |
| --- | --- |
| Owner | `jeffreywevans` |
| Repository | `backcaster` |
| Workflow filename | `workflow.yml` |
| Environment | `pypi` |

In the GitHub repository, create or review the `pypi` deployment environment and
its release-tag deployment policy. Add required reviewers if desired. Publishing
uses OpenID Connect with `id-token: write`; no PyPI API token is needed in the repository.
These GitHub and PyPI settings must be configured separately from the repository files.

## Publish

1. Merge the prepared changes into `main` and confirm CI passes, including Python
   3.13 and 3.14 and the 100% coverage gate.
2. Create a GitHub release named **0.3.1**, using tag **v0.3.1** at the validated
   commit on `main`. Use the 0.3.1 changelog entry as the release notes.
3. Publish the GitHub release as a stable release. This triggers `workflow.yml`;
   a draft does not trigger publication, and a prerelease does not upload to PyPI.
4. Review the build and the `pypi` deployment job; approve it if the environment
   requires approval. The workflow verifies the tag matches the package version,
   builds the source archive and wheel, checks metadata, and tests wheel installation.
5. After the upload succeeds, verify from a fresh environment:

   ```bash
   python -m pip install backcaster==0.3.1
   python -c 'from backcaster import __version__; assert __version__ == "0.3.1"'
   backcaster --help
   ```

PyPI versions are immutable. If an upload partially succeeds, investigate the
published files before retrying; do not replace an existing version's artifacts.
