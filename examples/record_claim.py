"""Example: record an agent conclusion grounded on a source span.

Run with:  python examples/record_claim.py
"""
from pathlib import Path

from provena.core.graph import ClaimDependencyGraph
from provena.core.provenance import record_claim
from provena.core.source import FileSpan


def main() -> None:
    src = Path(__file__).with_name("sample_source.txt")
    src.write_text("def parse_config(path: str) -> dict:\n    return {}\n", encoding="utf-8")

    graph = ClaimDependencyGraph()
    span = FileSpan.from_file(src, 1, 2)
    claim = record_claim(
        graph,
        text="`parse_config` takes one string argument and returns a dict.",
        grounded_on=[span],
    )
    print(graph.to_json(indent=2))
    print(f"\nrecorded claim: {claim.id} (status={claim.status.value})")


if __name__ == "__main__":
    main()
