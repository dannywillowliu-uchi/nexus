"""Swanson ABC traversal engine for PrimeKG-based drug repurposing.

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


# Relationship type weights for path strength scoring.
# Covers actual PrimeKG Neo4j labels plus literature edges.
RELATIONSHIP_WEIGHTS: dict[str, float] = {
	# Drug-Disease (high signal for drug repurposing)
	"INDICATION": 1.0,
	"OFF_LABEL_USE": 0.9,
	"CONTRAINDICATION": 0.4,
	# Drug-Gene/Protein (pharmacological)
	"TARGET": 0.95,
	"ENZYME": 0.75,
	"TRANSPORTER": 0.7,
	"CARRIER": 0.7,
	# Disease-Gene (genomic association)
	"ASSOCIATED_WITH": 0.85,
	# Phenotype edges
	"PHENOTYPE_PROTEIN": 0.8,
	"PHENOTYPE_PRESENT": 0.7,
	# Literature-derived edges
	"LITERATURE_EDGE": 0.75,
	"LITERATURE_ASSOCIATION": 0.8,
	# PrimeKG protein-protein interactions
	"PROTEIN_PROTEIN": 0.8,
	# PrimeKG ontology edges
	"DISEASE_PROTEIN": 0.85,
	"BIOPROCESS_PROTEIN": 0.7,
	"PATHWAY_PROTEIN": 0.75,
	"MOLFUNC_PROTEIN": 0.7,
	"CELLCOMP_PROTEIN": 0.65,
	"ANATOMY_PROTEIN_PRESENT": 0.7,
	"ANATOMY_PROTEIN_ABSENT": 0.3,
	"DRUG_EFFECT": 0.6,
	# Legacy Hetionet abbreviation forms (kept for compatibility)
	"TREATS_CtD": 1.0,
	"PALLIATES_CpD": 0.9,
	"BINDS_CbG": 0.9,
	"UPREGULATES_CuG": 0.7,
	"DOWNREGULATES_CdG": 0.7,
	"CAUSES_CcSE": 0.6,
	"RESEMBLES_CrC": 0.65,
	"ASSOCIATES_DaG": 0.85,
	"LOCALIZES_DlA": 0.75,
	"RESEMBLES_DrD": 0.6,
	"PRESENTS_DpS": 0.7,
	"INTERACTS_GiG": 0.8,
	"COVARIES_GcG": 0.65,
	"REGULATES_GrG": 0.75,
	"PARTICIPATES_GpBP": 0.8,
	"PARTICIPATES_GpCC": 0.7,
	"PARTICIPATES_GpMF": 0.75,
	"PARTICIPATES_GpPW": 0.8,
	"EXPRESSES_AeG": 0.7,
	"UPREGULATES_AuG": 0.65,
	"DOWNREGULATES_AdG": 0.65,
	"INCLUDES_PCiC": 0.55,
	"ASSOCIATES_GaD": 0.85,
	"PRESENTS_SpD": 0.7,
}

# Intermediary type multipliers -- Gene intermediaries are most valuable
# for drug repurposing hypotheses
INTERMEDIARY_MULTIPLIERS: dict[str, float] = {
	"Gene": 1.5,
	"Anatomy": 1.3,
	"Phenotype": 1.0,
	"BiologicalProcess": 0.7,
	"Pathway": 0.7,
	"MolecularFunction": 0.7,
	"CellularComponent": 0.7,
}

HUB_DEGREE_THRESHOLD = 200


def rel_weight(rel_type: str) -> float:
	"""Return the weight for a relationship type, defaulting to 0.5 for unknown types."""
	return RELATIONSHIP_WEIGHTS.get(rel_type, 0.5)


def compute_novelty(path_count: int, b_degree: int = 0) -> float:
	"""Compute novelty score. Hub nodes (degree > 200) get a 0.5x penalty."""
	if path_count <= 2:
		score = 0.9
	elif path_count <= 5:
		score = 0.95
	elif path_count <= 10:
		score = 0.8
	elif path_count <= 20:
		score = 0.6
	else:
		score = 0.4

	if b_degree > HUB_DEGREE_THRESHOLD:
		score *= 0.5

	return score


async def find_abc_hypotheses(
	source_name: str,
	source_type: str = "Disease",
	target_type: str = "Drug",
	max_results: int = 20,
	exclude_known: bool = True,
	fuzzy: bool = False,
	preferred_ab_rels: list[str] | None = None,
) -> list[ABCHypothesis]:
	"""Find ABC hypotheses via two-hop PrimeKG traversal through Gene intermediaries.

	Core drug repurposing query: Drug-[TARGET|CARRIER|ENZYME|TRANSPORTER]-Gene-[ASSOCIATED_WITH|LITERATURE_ASSOCIATION]-Disease.
	Always excludes known INDICATION edges when exclude_known=True.
	"""
	exclude_clause = ""
	if exclude_known:
		exclude_clause = "AND NOT (a)-[:INDICATION]-(c)"

	if fuzzy:
		source_filter = "WHERE a.name =~ $source_pattern"
	else:
		source_filter = "WHERE a.name = $source_name"

	ab_rel_clause = ""
	if preferred_ab_rels:
		ab_rel_clause = "AND type(r1) IN $preferred_ab_rels"

	query = f"""
		MATCH (a:{source_type})-[r1]-(b:Gene)-[r2]-(c:{target_type})
		{source_filter}
		AND a <> c AND b <> c AND b <> a
		{ab_rel_clause}
		{exclude_clause}
		WITH a, c,
			collect(DISTINCT {{
				b_id: toString(coalesce(b.primekg_index, b.identifier, elementId(b))),
				b_name: coalesce(b.name, ''),
				b_type: labels(b)[0],
				ab_rel: type(r1),
				bc_rel: type(r2)
			}}) AS intermediaries,
			count(DISTINCT b) AS path_count
		RETURN
			toString(coalesce(a.primekg_index, a.identifier, elementId(a))) AS a_id,
			a.name AS a_name,
			labels(a)[0] AS a_type,
			toString(coalesce(c.primekg_index, c.identifier, elementId(c))) AS c_id,
			c.name AS c_name,
			labels(c)[0] AS c_type,
			intermediaries,
			path_count
		ORDER BY path_count DESC
		LIMIT $max_results
	"""

	params: dict = {"max_results": max_results}
	if fuzzy:
		params["source_pattern"] = f"(?i).*{source_name}.*"
	else:
		params["source_name"] = source_name
	if preferred_ab_rels:
		params["preferred_ab_rels"] = preferred_ab_rels

	records = await graph_client.execute_read(query, **params)

	hypotheses: list[ABCHypothesis] = []
	for row in records:
		intermediaries = row["intermediaries"]
		path_count = row["path_count"]
		novelty = compute_novelty(path_count)

		best_strength = 0.0
		best_intermediary: dict = intermediaries[0] if intermediaries else {}

		for inter in intermediaries:
			ab_w = rel_weight(inter.get("ab_rel", ""))
			bc_w = rel_weight(inter.get("bc_rel", ""))
			strength = math.sqrt(ab_w * bc_w)
			b_type = inter.get("b_type", "")
			multiplier = INTERMEDIARY_MULTIPLIERS.get(b_type, 1.0)
			strength *= multiplier
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
	drug_name: str,
	max_results: int = 20,
	fuzzy: bool = False,
	preferred_ab_rels: list[str] | None = None,
) -> list[ABCHypothesis]:
	"""Find diseases a drug might treat via shared gene targets (Drug->Gene->Disease)."""
	if preferred_ab_rels is None:
		preferred_ab_rels = ["TARGET", "INDICATION", "ASSOCIATED_WITH", "DISEASE_PROTEIN"]
	return await find_abc_hypotheses(
		source_name=drug_name,
		source_type="Drug",
		target_type="Disease",
		max_results=max_results,
		fuzzy=fuzzy,
		preferred_ab_rels=preferred_ab_rels,
	)


async def find_comorbidity(
	disease_name: str,
	max_results: int = 20,
	fuzzy: bool = False,
	preferred_ab_rels: list[str] | None = None,
) -> list[ABCHypothesis]:
	"""Find related diseases via shared genes (Disease->Gene->Disease)."""
	return await find_abc_hypotheses(
		source_name=disease_name,
		source_type="Disease",
		target_type="Disease",
		max_results=max_results,
		fuzzy=fuzzy,
		preferred_ab_rels=preferred_ab_rels,
	)
