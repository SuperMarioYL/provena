<div align="right"><sub><b>English</b>&nbsp;&nbsp;⇄&nbsp;&nbsp;<a href="./README.md">中文</a></sub></div>

<p align="center">
<picture>
  <source media="(prefers-color-scheme: dark)" srcset="./assets/hero-dark.svg">
  <source media="(prefers-color-scheme: light)" srcset="./assets/hero-light.svg">
  <img src="./assets/hero-light.svg" width="880" alt="Provena — provenance-cascade for agent conclusions">
</picture>
</p>

<p align="center"><sub>Provena is the provenance layer for long-horizon agent teams: when a source mutates, dependent conclusions are cascade-flagged stale.</sub></p>

<p align="center">
  <a href="./LICENSE"><img src="https://img.shields.io/github/license/SuperMarioYL/provena?color=0071E3" alt="license"></a>
  <a href="https://github.com/SuperMarioYL/provena/releases"><img src="https://img.shields.io/github/v/release/SuperMarioYL/provena?color=10A37F" alt="release"></a>
  <a href="https://github.com/SuperMarioYL/provena/actions/workflows/ci.yml"><img src="https://img.shields.io/github/actions/workflow/status/SuperMarioYL/provena/ci.yml?branch=main&label=CI&color=5E5CE6" alt="CI"></a>
  <img src="https://img.shields.io/badge/Python-3.12%2B-3776AB?logo=python&logoColor=white" alt="python">
</p>

**Every agent conclusion is linked back to a machine-checkable source span; when a source mutates (a file edit, a model swap, a web page update), dependent conclusions are cascade-flagged stale and queued for re-derivation — all visible on one claim-to-source graph.**

<h2><img src="https://api.iconify.design/tabler:topology-star-3.svg?color=%230071E3&width=24" height="22" align="absmiddle" alt=""> Architecture</h2>

<p align="center">
<picture>
  <source media="(prefers-color-scheme: dark)" srcset="./assets/atlas-dark.svg">
  <source media="(prefers-color-scheme: light)" srcset="./assets/atlas-light.svg">
  <img src="./assets/atlas-light.svg" width="880" alt="architecture: source spans -> claim-to-source graph -> cascade engine -> graph UI + alert webhook">
</picture>
</p>

The core primitive is the **ClaimDependencyGraph**: a DAG whose nodes are *claims* (agent-emitted conclusions) and *sources* (machine-checkable spans), with two edge types:

- `grounded_on`: claim -> source (the conclusion was derived from this span)
- `depends_on`: claim -> claim (one conclusion built on another)

On any source mutation, the engine flags the directly-grounded claims `stale` and propagates `stale` **transitively** along `depends_on` edges — Bazel-style dirty-marking lifted from code-graph nodes to *agent-claim* nodes. The unit of invalidation is an agent's emitted *conclusion*, not a file or a code-graph node.

## Contents

- [Why this exists](#why-this-exists)
- [Install & Quickstart](#install--quickstart)
- [Usage](#usage)
- [Demo](#demo)
- [Roadmap](#roadmap)
- [License](#license)

## Why this exists

When a fact an agent grounded a conclusion on mutates (a function signature refactored, a model swapped, a web page updated), every downstream conclusion goes **silently stale** and no existing tool re-flags it — the agent keeps reasoning on conclusions that no longer hold. This is exactly the pain *Verschlimmbesserung* (an "improvement" that makes things worse) names: upstream changes, downstream degrades quietly.

Provena links each conclusion backward to a **machine-checkable source span** (a dataflow proxy, not a black-box rationale) and cascade-flags dependent conclusions the moment their ground shifts, surfaced on a live claim-to-source graph. If it exists, stale conclusions stop being silent — they get flagged and queued for re-derivation.

## Install & Quickstart

```bash
git clone https://github.com/SuperMarioYL/provena && cd provena
pip install -e .
provena demo            # open http://127.0.0.1:8000, edit provena/demo/source.py -> dependents turn red
```

> Or with [uv](https://docs.astral.sh/uv/): `uv run provena demo`.

<details>
<summary>Sample output (provena demo)</summary>

```
Provena demo — http://127.0.0.1:8000
edit the source to flag dependents: .../provena/demo/source.py
watching .../provena/demo/source.py for mutations (live edit -> flag)
graph ready: 5 claims, 5 sources
# after editing parse_config's signature:
[cascade] 2 claim(s) flagged stale by file:.../source.py:15-17
  - claim_....  `parse_config` is defined at ...:15-17 ...
  - claim_....  The module exposes a stable public surface of callables ...
```
</details>

## Usage

<h3><img src="https://api.iconify.design/tabler:terminal-2.svg?color=%230071E3&width=20" height="18" align="absmiddle" alt=""> Subcommands</h3>

```bash
# print the claim-to-source DAG (m1 done criterion)
provena graph --json

# explain a conclusion's provenance (which spans it grounds on + which claims it depends on)
provena trace <claim_id>

# diff the working tree against the git baseline and list stale claims (run after an edit)
provena check

# boot the toy agent + local UI server + file watcher (edit -> flag -> alert)
provena demo
```

The programming API is equally direct:

```python
from provena.core.graph import ClaimDependencyGraph
from provena.core.provenance import record_claim
from provena.core.source import FileSpan

g = ClaimDependencyGraph()
span = FileSpan.from_file("kb.py", 1, 2)
claim = record_claim(g, "`parse_config` returns a dict.", grounded_on=[span])
print(g.to_json(indent=2))
```

More examples in [`examples/`](./examples).

## Demo

<h3><img src="https://api.iconify.design/tabler:photo.svg?color=%230071E3&width=20" height="18" align="absmiddle" alt=""> edit a source -> dependents cascade-flag stale</h3>

![demo](assets/demo.gif)

Edit a function signature in `provena/demo/source.py` that an agent conclusion cited; `provena check` flags the grounded claim and every claim depending on it as stale.

## Roadmap

<h3><img src="https://api.iconify.design/tabler:map-2.svg?color=%230071E3&width=20" height="18" align="absmiddle" alt=""> Milestones</h3>

- [x] **m1** — claim->source data model + provenance recording; toy agent emits graph-queryable conclusions (`provena graph --json`)
- [x] **m2** — file-mutation detection (watchfiles) + transitive stale propagation over the claim DAG (`provena check`)
- [x] **m3** — FastAPI + vis-network graph view, flagged nodes highlighted, click-to-inspect spans (`provena demo` end-to-end < 10 min)

**Future (explicitly out of scope for v0.1):**

- Real-agent framework plugins (Claude Code / Cursor / LangChain) — v0.1 ships a toy scripted agent only
- Executing re-derivation (auto-re-running the agent) — v0.1 flags only; it never auto-re-derives
- Persistent storage / DB — in-memory graph only
- Multi-user, auth, cloud hosting, SSO
- Collaboration or dashboards beyond the single-user local graph view
- Full OpenTelemetry GenAI collector pipeline — modeled spans, not a real collector
- Enterprise license / real billing system (the alert-webhook is a stub previewing the paid tier)
- Custom-trained models / ML
- Web-source and model-version mutation watchers (file-span only; model/web are stubbed interfaces)

**Commercial path:** free OSS core (MIT) + a hosted team tier (managed claim-to-source graph storage + cascade dashboards + 飞书/Slack alerting). The demo's alert-webhook stub previews the paid tier.

**Kill criteria:** after one month live on GitHub + Gitee with 3 launch activities, abandon if the combined stars are <50 AND zero organic issues from users attempting to integrate Provena into a real agent, AND the 5 pre-build interviews returned <2 willing-to-instrument. A primitive nobody wires in is not a business — even with stars.

## License

MIT — see [`LICENSE`](./LICENSE). Issues and PRs welcome: [issues](https://github.com/SuperMarioYL/provena/issues).

<p align="center"><sub><a href="./LICENSE">MIT</a> © 2026 SuperMarioYL</sub></p>
