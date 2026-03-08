from __future__ import annotations

from typing import Callable

from nexus.tools.compound_lookup import compound_lookup
from nexus.tools.expression_correlate import expression_correlate
from nexus.tools.generate_protocol import generate_protocol
from nexus.tools.literature_validate import literature_validate
from nexus.tools.molecular_dock import molecular_dock
from nexus.tools.pathway_overlap import pathway_overlap
from nexus.tools.protein_interaction import protein_interaction

TOOL_REGISTRY: dict[str, Callable] = {
	"literature_validate": literature_validate,
	"compound_lookup": compound_lookup,
	"pathway_overlap": pathway_overlap,
	"protein_interaction": protein_interaction,
	"expression_correlate": expression_correlate,
	"molecular_dock": molecular_dock,
	"generate_protocol": generate_protocol,
}
