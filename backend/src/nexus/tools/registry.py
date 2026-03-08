from __future__ import annotations

from typing import Callable

from nexus.tools.batch_screen import batch_screen
from nexus.tools.compound_lookup import compound_lookup
from nexus.tools.dock_compound import dock_compound
from nexus.tools.expression_correlate import expression_correlate
from nexus.tools.generate_protocol import generate_protocol
from nexus.tools.literature_validate import literature_validate
from nexus.tools.molecular_dock import molecular_dock
from nexus.tools.pathway_overlap import pathway_overlap
from nexus.tools.predict_properties import predict_properties
from nexus.tools.predict_structure import predict_structure
from nexus.tools.protein_interaction import protein_interaction
from nexus.tools.validation_planner import run_validation_plan

TOOL_REGISTRY: dict[str, Callable] = {
	"literature_validate": literature_validate,
	"compound_lookup": compound_lookup,
	"pathway_overlap": pathway_overlap,
	"protein_interaction": protein_interaction,
	"expression_correlate": expression_correlate,
	"molecular_dock": molecular_dock,
	"generate_protocol": generate_protocol,
	"predict_structure": predict_structure,
	"dock_compound": dock_compound,
	"predict_properties": predict_properties,
	"batch_screen": batch_screen,
	"run_validation_plan": run_validation_plan,
}
