# Changelog

All notable changes to this project are recorded here. Versions follow
[semver](https://semver.org/); the released version is the git tag.

## v0.4.0

Bug-hunt release. Four reproducible defects in the v0.3.0 source are fixed, and
the version lockstep guard now covers the product site's content version.

### Fixed

- **A decorated definition is grounded on its decorators.** `ast` reports
  `node.lineno` as the `def` line and gives each decorator its own line, so the
  toy agent's span (and the claim text citing it) started *after* the
  decorators: editing only a decorator — a route path, a cache size — left that
  claim fresh while `provena trace` still reported it fresh on a span that did
  not cover the definition. Spans now start at the first decorator
  (`provena/demo/agent.py`).
- **A source with no top-level function is still verified.** The module-level
  claim was guarded by `if func_claims:`, so a constants module, a package
  `__init__` or an empty file produced a graph with zero claims, and
  `provena check --fail-on-stale` printed "no stale claims" and exited 0 after
  the tracked file changed. The module claim is now always recorded, so a
  parseable source cannot yield an unverified graph (`provena/demo/agent.py`).
- **`provena check --fail-on-stale` no longer passes what it could not check.**
  Without a git baseline (not a repo, untracked file, no commit, or the packaged
  default source), the gate exited 0 — a CI / pre-commit pass for a file nothing
  was verified on. It now exits 2 and says nothing was verified; the
  informational invocation still exits 0 (`provena/cli.py`).
- **Re-recording a conclusion clears its stale flag.** Re-deriving through
  `record_claim` / the toy agent adopted the new content hash as the baseline
  but left the claim `stale` forever, so the graph reported "nothing left to
  re-derive" next to a stale claim. An identity-identical re-recording now
  adopts the incoming status, and `add_source`'s docstring matches its
  replace-the-stored-copy behavior. Mutation detection still recomputes from
  hashes, so a re-emission over still-drifted sources is re-flagged
  (`provena/core/graph.py`).

### Added

- `tests/test_version_lockstep.py` now also asserts `web/site.json`
  `content_version` matches the package version, closing the last
  hand-maintained version surface.

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
