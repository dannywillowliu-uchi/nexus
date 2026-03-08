"""Generalized Swanson ABC traversal engine for literature-based discovery.

Given a source entity A, finds intermediate entities B and target entities C
where A-B and B-C relationships exist but no direct A-C connection is known.
"""

import math
from dataclasses import dataclass, field

from nexus.graph.client import graph_client


@dataclass
class ABCHypothesis:
	"""A hypothesis linking entity A to entity C through intermediary B."""

	a_id: str
	a_name: str
	a_type: str
	b_id: str
	b_name: str
	b_type: str
	c_id: str
	c_name: str
	c_type: str
	ab_relationship: str
	bc_relationship: str
	path_count: int
	novelty_score: float
	path_strength: float = 0.0
	intermediaries: list[dict] = field(default_factory=list)


# Hetionet relationship type weights (all 24 canonical types + extras)
RELATIONSHIP_WEIGHTS: dict[str, float] = {
	# Compound relationships
	"TREATS_CtD": 1.0,
	"PALLIATES_CpD": 0.9,
	"BINDS_CbG": 0.9,
	"UPREGULATES_CuG": 0.7,
	"DOWNREGULATES_CdG": 0.7,
	"CAUSES_CcSE": 0.6,
	"RESEMBLES_CrC": 0.65,
	# Disease relationships
	"ASSOCIATES_DaG": 0.85,
	"LOCALIZES_DlA": 0.75,
	"RESEMBLES_DrD": 0.6,
	"PRESENTS_DpS": 0.7,
	# Gene relationships
	"INTERACTS_GiG": 0.8,
	"COVARIES_GcG": 0.65,
	"REGULATES_GrG": 0.75,
	"PARTICIPATES_GpBP": 0.8,
	"PARTICIPATES_GpCC": 0.7,
	"PARTICIPATES_GpMF": 0.75,
	"PARTICIPATES_GpPW": 0.8,
	# Anatomy relationships
	"EXPRESSES_AeG": 0.7,
	"UPREGULATES_AuG": 0.65,
	"DOWNREGULATES_AdG": 0.65,
	# Pharmacologic class
	"INCLUDES_PCiC": 0.55,
	# Gene-Disease
	"ASSOCIATES_GaD": 0.85,
	# Symptom-Disease (reverse direction label)
	"PRESENTS_SpD": 0.7,
	# Extra convenience aliases (uppercase Cypher-sanitized forms)
	"TREATS": 1.0,
	"BINDS": 0.9,
	"ASSOCIATES": 0.85,
	"INTERACTS": 0.8,
	"REGULATES": 0.75,
	"PARTICIPATES": 0.8,
	"EXPRESSES": 0.7,
	"PALLIATES": 0.9,
	"RESEMBLES": 0.65,
}


def rel_weight(rel_type: str) -> float:
	"""Return the weight for a relationship type, defaulting to 0.5 for unknown types."""
	return RELATIONSHIP_WEIGHTS.get(rel_type, 0.5)


def compute_novelty(path_count: int) -> float:
	"""Compute a novelty score based on the number of connecting paths.

	Fewer paths suggest a more novel (less obvious) connection.
	Very few paths (<=2) may indicate noise, so scored slightly below the sweet spot.
	"""
	if path_count <= 2:
		return 0.9
	elif path_count <= 5:
		return 0.95
	elif path_count <= 10:
		return 0.8
	elif path_count <= 20:
		return 0.6
	else:
		return 0.4


async def find_abc_hypotheses(
	source_name: str,
	source_type: str = "Disease",
	target_type: str = "Compound",
	max_results: int = 20,
	exclude_known: bool = True,
) -> list[ABCHypothesis]:
	"""Find ABC hypotheses connecting a source entity to target entities via intermediaries.

	Uses a two-hop graph traversal: A -[r1]- B -[r2]- C where no direct A-C
	connection exists (when exclude_known=True).

	Args:
		source_name: Name of the source entity (e.g. a disease name).
		source_type: Node label of the source (default "Disease").
		target_type: Node label of the target (default "Compound").
		max_results: Maximum number of hypotheses to return.
		exclude_known: If True, exclude target entities already directly connected to source.

	Returns:
		List of ABCHypothesis objects sorted by path_count descending.
	"""
	exclude_clause = ""
	if exclude_known:
		exclude_clause = "AND NOT (a)-[]-(c)"

	query = f"""
		MATCH (a:{source_type} {{name: $source_name}})-[r1]-(b)-[r2]-(c:{target_type})
		WHERE a <> c AND b <> c AND b <> a
		{exclude_clause}
		WITH a, c,
			collect(DISTINCT {{
				b_id: coalesce(b.identifier, elementId(b)),
				b_name: coalesce(b.name, ''),
				b_type: labels(b)[0],
				ab_rel: type(r1),
				bc_rel: type(r2)
			}}) AS intermediaries,
			count(DISTINCT b) AS path_count
		RETURN
			coalesce(a.identifier, elementId(a)) AS a_id,
			a.name AS a_name,
			labels(a)[0] AS a_type,
			coalesce(c.identifier, elementId(c)) AS c_id,
			c.name AS c_name,
			labels(c)[0] AS c_type,
			intermediaries,
			path_count
		ORDER BY path_count DESC
		LIMIT $max_results
	"""

	records = await graph_client.execute_read(
		query,
		source_name=source_name,
		max_results=max_results,
	)

	hypotheses: list[ABCHypothesis] = []
	for row in records:
		intermediaries = row["intermediaries"]
		path_count = row["path_count"]
		novelty = compute_novelty(path_count)

		# Find the best intermediary by path strength
		best_strength = 0.0
		best_intermediary: dict = intermediaries[0] if intermediaries else {}

		for inter in intermediaries:
			ab_w = rel_weight(inter.get("ab_rel", ""))
			bc_w = rel_weight(inter.get("bc_rel", ""))
			strength = math.sqrt(ab_w * bc_w)
			if strength > best_strength:
				best_strength = strength
				best_intermediary = inter

		hypotheses.append(ABCHypothesis(
			a_id=str(row["a_id"]),
			a_name=row["a_name"],
			a_type=row["a_type"],
			b_id=str(best_intermediary.get("b_id", "")),
			b_name=best_intermediary.get("b_name", ""),
			b_type=best_intermediary.get("b_type", ""),
			c_id=str(row["c_id"]),
			c_name=row["c_name"],
			c_type=row["c_type"],
			ab_relationship=best_intermediary.get("ab_rel", ""),
			bc_relationship=best_intermediary.get("bc_rel", ""),
			path_count=path_count,
			novelty_score=novelty,
			path_strength=best_strength,
			intermediaries=intermediaries,
		))

	return hypotheses


async def find_drug_repurposing_candidates(
	disease_name: str,
	max_results: int = 20,
) -> list[ABCHypothesis]:
	"""Find potential drug repurposing candidates for a disease.

	Convenience wrapper around find_abc_hypotheses with Disease -> Compound.
	"""
	return await find_abc_hypotheses(
		source_name=disease_name,
		source_type="Disease",
		target_type="Compound",
		max_results=max_results,
	)


async def find_mechanism_hypotheses(
	disease_name: str,
	max_results: int = 20,
) -> list[ABCHypothesis]:
	"""Find potential biological mechanisms underlying a disease.

	Convenience wrapper around find_abc_hypotheses with Disease -> BiologicalProcess.
	"""
	return await find_abc_hypotheses(
		source_name=disease_name,
		source_type="Disease",
		target_type="BiologicalProcess",
		max_results=max_results,
	)
