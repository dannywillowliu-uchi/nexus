#!/usr/bin/env python3
"""Runner script to seed Hetionet data into Neo4j."""

import asyncio
import sys
from pathlib import Path

# Allow running from repo root
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "backend" / "src"))

from nexus.graph.seed import seed_all


async def main() -> None:
	data_dir = Path(sys.argv[1]) if len(sys.argv) > 1 else None
	print("Seeding Hetionet data into Neo4j...")
	result = await seed_all(data_dir)
	print(f"Done. Created {result['nodes']} nodes and {result['edges']} edges.")


if __name__ == "__main__":
	asyncio.run(main())
