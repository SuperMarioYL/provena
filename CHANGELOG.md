# Changelog

All notable changes to this project are recorded here. Versions follow
[semver](https://semver.org/); the released version is the git tag.

## v0.3.0

Bug-hunt release. Three reproducible defects in the v0.2.0 source are fixed, and
the version surfaces now have a mechanical lockstep guard.

### Fixed

- **An unreadable tracked source now compares as mutated instead of raising.**
  `FileSpan.current_hash` caught only `OSError`, but reading a file that exists
  and is not valid UTF-8 raises `UnicodeDecodeError` (a `ValueError`), so the
  guard missed the "unreadable" half of its documented contract
  (`provena/core/source.py`). Such a span now returns the tombstone hash and its
  claims are flagged stale, like a deleted file.
- **`provena graph` / `trace` / `demo` / `check` no longer leak raw tracebacks
  for an unusable source.** A missing, undecodable, or non-Python `--source`
  used to escape as `FileNotFoundError` / `UnicodeDecodeError` / `SyntaxError`
  from `ToyAgent.run` and the git-HEAD baseline reader. Each command now prints
  one diagnostic line and exits 2 (`provena/cli.py`, `provena/demo/agent.py`).
- **`async def` functions are grounded again.** The toy agent matched only
  `ast.FunctionDef`, but `ast.AsyncFunctionDef` is a sibling class, so an async
  top-level function produced no claim and could never be flagged stale.

### Added

- `tests/test_version_lockstep.py` — asserts `VERSION`, the `pyproject.toml`
  `[project]` version, `provena.__version__`, the CLI `--version` output, and
  the FastAPI app version all agree, so a future bump cannot silently drift.

## v0.2.0

### Fixed

- Deleting a tracked source file flags its grounded claims stale through a
  tombstone hash instead of crashing `provena check` with a raw
  `FileNotFoundError`, and baseline mode parses the baseline AST so a deleted
  function surfaces as a stale claim rather than vanishing.
- Re-deriving an identical conclusion lands on the existing claim node
  (idempotent `add_claim`) instead of raising `ValueError: duplicate claim id`.

### Added

- Opt-in `--fail-on-stale` exit gate on `provena check` for CI / pre-commit, and
  a root `provena --version` surface sourced from `provena.__version__`.

## v0.1.0

### Added

- `ClaimDependencyGraph`: claims, sources, and the `grounded_on` / `depends_on`
  edges, with a JSON snapshot (`provena graph --json`).
- `CascadeEngine`: file-mutation detection and transitive stale propagation over
  the claim DAG.
- `provena demo`: FastAPI + static UI rendering the claim-to-source graph with
  flagged nodes highlighted, plus the alert-webhook stub seam.
