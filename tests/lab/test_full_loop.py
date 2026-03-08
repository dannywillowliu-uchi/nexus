"""Comprehensive test of the entire lab package and closed loop."""

import asyncio
import sys

from nexus.lab.protocols.spec import (
	AssaySpec,
	CellModelSpec,
	CompoundSpec,
	ControlSpec,
	DilutionStep,
	ExperimentSpec,
	PlateLayout,
	ProteinSpec,
	ReadoutSpec,
	SuccessCriteria,
)


async def main():
	passed = 0
	failed = 0

	def check(name, condition, detail=""):
		nonlocal passed, failed
		if condition:
			print(f"  [OK] {name}")
			passed += 1
		else:
			print(f"  [FAIL] {name} - {detail}")
			failed += 1

	print("=== 1. spec.py ===")
	spec = ExperimentSpec(
		hypothesis_id="test",
		compound=CompoundSpec(name="Test", smiles="C", molecular_weight=100),
		cell_model=CellModelSpec(name="HeLa"),
		protein_target=ProteinSpec(name="EGFR", pdb_ids=["1M17"]),
		assay=AssaySpec(assay_type="MTT_viability"),
	)
	d = spec.to_dict()
	spec2 = ExperimentSpec.from_dict(d)
	check("roundtrip compound", spec2.compound.name == "Test")
	check("roundtrip protein", spec2.protein_target.pdb_ids == ["1M17"])
	check("roundtrip cell_model", spec2.cell_model.name == "HeLa")
	check("roundtrip None protein", ExperimentSpec.from_dict({"protein_target": None}).protein_target is None)

	print("\n=== 2. cache.py ===")
	from nexus.lab.resolvers.cache import get_compound_cache, lookup_compound
	cache = get_compound_cache()
	check("cache has 10 compounds", len(cache) == 10, f"got {len(cache)}")
	rap = lookup_compound("Rapamycin")
	check("Rapamycin found", rap is not None)
	check("Rapamycin CAS", rap["cas_number"] == "53123-88-9")
	met = lookup_compound("metformin")
	check("metformin lowercase", met is not None)
	check("missing compound", lookup_compound("FakeCompound123") is None)

	print("\n=== 3. compound.py ===")
	from nexus.lab.resolvers.compound import resolve_compound
	comp = await resolve_compound("Rapamycin")
	check("cached resolve name", comp.name == "Rapamycin")
	check("cached resolve MW", comp.molecular_weight == 914.17)

	print("\n=== 4. cell_line.py ===")
	from nexus.lab.resolvers.cell_line import resolve_cell_line_local
	for disease, expected in [
		("Alzheimer", "SH-SY5Y"),
		("Parkinson", "SH-SY5Y"),
		("diabetes", "INS-1"),
		("cancer", "HeLa"),
		("cardiovascular", "HUVEC"),
		("inflammation", "THP-1"),
		("autoimmune", "Jurkat"),
	]:
		cl = resolve_cell_line_local(disease)
		check(f"{disease} -> {expected}", cl is not None and cl.name == expected,
			f"got {cl.name if cl else 'None'}")

	print("\n=== 5. protein.py ===")
	from nexus.lab.resolvers.protein import has_structural_data, is_receptor_or_enzyme
	p1 = ProteinSpec(name="EGFR", pdb_ids=["1M17"], protein_class="kinase")
	check("has_structural_data True", has_structural_data(p1))
	check("is_receptor_or_enzyme True", is_receptor_or_enzyme(p1))
	p2 = ProteinSpec(name="X", pdb_ids=[], protein_class="other")
	check("has_structural_data False", not has_structural_data(p2))
	check("is_receptor_or_enzyme False", not is_receptor_or_enzyme(p2))

	print("\n=== 6. assay_selector.py ===")
	from nexus.lab.design.assay_selector import _normalize_entity_type, select_assay
	check("normalize Gene", _normalize_entity_type("Gene") == "Gene")
	check("normalize gene/protein", _normalize_entity_type("gene/protein") == "Gene")
	check("normalize biological_process", _normalize_entity_type("biological_process") == "BiologicalProcess")
	check("normalize drug", _normalize_entity_type("drug") == "Compound")
	check("normalize Pathway", _normalize_entity_type("Pathway") == "Pathway")

	a1 = select_assay("drug_repurposing", "Gene", True, True)
	check("Gene+PDB+enzyme -> FP", a1.assay_type == "fluorescence_polarization")
	a2 = select_assay("drug_repurposing", "Gene", False, False)
	check("Gene no PDB -> MTT", a2.assay_type == "MTT_viability")
	a3 = select_assay("mechanism", "Pathway", False, False, True)
	check("Pathway+reporter -> luciferase", a3.assay_type == "luciferase_reporter")
	a4 = select_assay("mechanism", "BiologicalProcess")
	check("BiologicalProcess -> MTT", a4.assay_type == "MTT_viability")
	a5 = select_assay("drug_repurposing", "gene/protein", True, True)
	check("PrimeKG gene/protein -> FP", a5.assay_type == "fluorescence_polarization")

	print("\n=== 7. dilution.py ===")
	from nexus.lab.design.dilution import calculate_dilutions
	steps = calculate_dilutions(10000, [50, 10, 1, 0.1])
	check("4 steps", len(steps) == 4, f"got {len(steps)}")
	check("sorted high->low", steps[0].target_concentration_uM == 50)
	check("transfer > 0", all(s.transfer_volume_uL > 0 for s in steps))

	steps_int = calculate_dilutions(10000, [0.001])
	check("intermediate needed", steps_int[0].needs_intermediate)
	check("intermediate conc > 0", steps_int[0].intermediate_concentration_uM > 0)

	steps_dmso = calculate_dilutions(10000, [50], solvent="DMSO")
	check("DMSO fraction <= 0.01", steps_dmso[0].dmso_fraction <= 0.01)
	steps_water = calculate_dilutions(10000, [50], solvent="Water")
	check("Water = no DMSO", steps_water[0].dmso_fraction == 0)

	print("\n=== 8. plate_layout.py ===")
	from nexus.lab.design.plate_layout import generate_plate_layout
	layout = generate_plate_layout([100, 50, 10, 1], replicates=3)
	check("96-well", layout.plate_type == "96-well")
	check("21 wells", layout.total_wells_used == 21, f"got {layout.total_wells_used}")
	check("within capacity", layout.total_wells_used <= layout.max_wells)

	layout384 = generate_plate_layout([100], plate_type="384-well")
	check("384 max_wells", layout384.max_wells == 384)
	check("384 catalog", "384" in layout384.plate_catalog)

	print("\n=== 9. validator.py ===")
	from nexus.lab.design.validator import validate_protocol
	good = ExperimentSpec(
		compound=CompoundSpec(name="test", test_concentrations_uM=[50, 10, 1, 0.1]),
		plate_layout=generate_plate_layout([50, 10, 1, 0.1]),
		dilution_steps=calculate_dilutions(10000, [50, 10, 1, 0.1]),
		assay=AssaySpec(assay_type="MTT_viability"),
	)
	v = validate_protocol(good)
	check("good spec valid", v.valid, f"errors: {v.errors}")

	bad_dmso = ExperimentSpec(
		compound=CompoundSpec(name="test", test_concentrations_uM=[100]),
		plate_layout=generate_plate_layout([100]),
		dilution_steps=calculate_dilutions(10000, [100]),
		assay=AssaySpec(assay_type="MTT_viability"),
	)
	v2 = validate_protocol(bad_dmso)
	check("DMSO violation caught", not v2.valid and any("DMSO" in e for e in v2.errors))

	no_ctrl = ExperimentSpec(
		compound=CompoundSpec(name="test", test_concentrations_uM=[10]),
		plate_layout=PlateLayout(layout={"compound_10uM": ["A1", "A2", "A3"]}),
		dilution_steps=calculate_dilutions(10000, [10]),
		assay=AssaySpec(assay_type="MTT_viability"),
	)
	v3 = validate_protocol(no_ctrl)
	check("missing controls caught", not v3.valid)

	biologic = ExperimentSpec(
		compound=CompoundSpec(name="test", molecular_weight=150000, solvent="DMSO", test_concentrations_uM=[10]),
		plate_layout=generate_plate_layout([10]),
		dilution_steps=calculate_dilutions(10000, [10]),
		assay=AssaySpec(assay_type="MTT_viability"),
	)
	v4 = validate_protocol(biologic)
	check("biologic MW warning", any("biologic" in w.lower() or "MW" in w for w in v4.warnings))

	print("\n=== 10. pylabrobot_gen.py ===")
	from nexus.lab.protocols.pylabrobot_gen import generate_pylabrobot_code
	code = generate_pylabrobot_code(good)
	check("has async def", "async def run_protocol" in code)
	check("has SimulatorBackend", "SimulatorBackend" in code)
	check("has pick_up_tips", "pick_up_tips" in code)
	check("valid Python", _try_compile(code))

	print("\n=== 11. ecl_gen.py ===")
	from nexus.lab.protocols.ecl_gen import generate_ecl_code
	ecl = generate_ecl_code(good)
	check("has ExperimentMTT", "ExperimentMTT" in ecl)
	check("has Micromolar", "Micromolar" in ecl)

	print("\n=== 12. opentrons_gen.py ===")
	from nexus.lab.protocols.opentrons_gen import generate_opentrons_code
	ot = generate_opentrons_code(good)
	check("has def run", "def run(protocol" in ot)
	check("valid Python", _try_compile(ot))

	print("\n=== 13. simulator.py ===")
	from nexus.lab.execution.simulator import dry_run
	dr = await dry_run(code)
	check("dry run passes", dr.success)
	bad_dr = await dry_run("def foo(: pass")
	check("bad code fails", not bad_dr.success)

	print("\n=== 14. results_sim.py ===")
	from nexus.lab.execution.results_sim import generate_simulated_results
	res_active = generate_simulated_results(good, hypothesis_plausibility=0.9, seed=42)
	check("active=True", res_active.analysis["active"])
	check("has IC50", res_active.analysis["ic50_uM"] is not None)
	check("z_factor > 0", res_active.qc_metrics["z_factor"] > 0)
	check("4 dose-response points", len(res_active.dose_response) == 4)
	check("has neg ctrl", "negative_ctrl" in res_active.raw_data)
	check("has pos ctrl", "positive_ctrl" in res_active.raw_data)

	res_inactive = generate_simulated_results(good, hypothesis_plausibility=0.1, seed=42)
	check("inactive=False", not res_inactive.analysis["active"])
	check("no IC50", res_inactive.analysis["ic50_uM"] is None)

	print("\n=== 15. interpreter.py (fallback) ===")
	from nexus.lab.interpretation.interpreter import _fallback_interpretation
	fb1 = _fallback_interpretation(res_active.to_dict())
	check("active -> verdict", fb1["verdict"] in ("validated", "inconclusive"))
	check("has reasoning", len(fb1["reasoning"]) > 0)

	fb2 = _fallback_interpretation(res_inactive.to_dict())
	check("inactive -> refuted/inconclusive", fb2["verdict"] in ("refuted", "inconclusive"))

	fb3 = _fallback_interpretation({"qc_metrics": {"z_factor": 0.2}, "analysis": {"active": True, "ic50_uM": 5}})
	check("bad QC -> inconclusive", fb3["verdict"] == "inconclusive")

	print("\n=== 16-20. tools.py integration ===")
	from nexus.lab.tools import (
		_build_autoprotocol,
		_normalize_cloud_results,
		design_experiment,
		interpret_results,
		resolve_compound as rc_tool,
		submit_to_cloud_lab,
		validate_and_execute_protocol,
	)

	comp_dict = await rc_tool("Sildenafil")
	check("resolve Sildenafil CAS", comp_dict["cas_number"] == "139755-83-2")

	hyp = {
		"id": "int-test",
		"title": "Pioglitazone treats diabetes via PPARG",
		"hypothesis_type": "drug_repurposing",
		"disease_area": "diabetes",
		"abc_path": {
			"a": {"name": "Diabetes", "type": "disease"},
			"b": {"name": "PPARG", "type": "gene/protein"},
			"c": {"name": "Pioglitazone", "type": "drug"},
		},
	}
	exp = await design_experiment(hyp, budget_tier="minimal")
	check("design compound", exp["compound"]["name"] == "Pioglitazone")
	check("design cell INS-1", exp["cell_model"]["name"] == "INS-1")
	check("design has dilutions", len(exp["dilution_steps"]) > 0)
	check("design has layout", len(exp["plate_layout"]["layout"]) > 0)

	result = await validate_and_execute_protocol(exp, backend="simulator")
	check("simulator complete", result["status"] == "simulation_complete")
	check("simulator valid", result["validation"]["valid"])

	result_dry = await validate_and_execute_protocol(exp, backend="dry_run")
	check("dry_run code_ready", result_dry["status"] == "code_ready")
	check("dry_run has code", "protocol_code" in result_dry)

	verdict = await interpret_results(exp, result["simulated_results"])
	check("interpret has verdict", verdict["verdict"] in ("validated", "inconclusive", "refuted"))
	check("interpret has confidence", 0 <= verdict["confidence"] <= 1)

	print("\n=== 21. Autoprotocol ===")
	spec_obj = ExperimentSpec.from_dict(exp)
	ap = _build_autoprotocol(spec_obj)
	check("has refs", "refs" in ap and "assay_plate" in ap["refs"])
	check("has instructions", len(ap["instructions"]) > 0)
	check("has incubate", any(i["op"] == "incubate" for i in ap["instructions"]))
	has_read = any(i["op"] in ("absorbance", "fluorescence", "luminescence") for i in ap["instructions"])
	check("has plate read", has_read)

	print("\n=== 22. Cloud results normalization ===")
	fake_data = {}
	for cond, wells in spec_obj.plate_layout.layout.items():
		for well in wells:
			fake_data[well] = 0.75
	norm = _normalize_cloud_results({"plate_read": fake_data}, exp)
	check("has dose_response", "dose_response" in norm)
	check("has raw_data", "raw_data" in norm)

	print("\n=== 23. Cloud lab path (no creds) ===")
	try:
		await submit_to_cloud_lab(exp, provider="strateos")
		check("strateos rejects without creds", False, "should have raised")
	except ValueError:
		check("strateos raises ValueError", True)

	try:
		from nexus.lab.tools import _get_provider
		_get_provider("nonexistent")
		check("unknown provider raises", False)
	except ValueError:
		check("unknown provider raises ValueError", True)

	print("\n=== 24. Pipeline integration ===")
	# Can't import orchestrator (needs neo4j), but verify runner compiles
	import py_compile
	try:
		py_compile.compile("backend/src/nexus/harness/runner.py", doraise=True)
		check("runner.py compiles", True)
	except py_compile.PyCompileError as e:
		check("runner.py compiles", False, str(e))

	try:
		py_compile.compile("backend/src/nexus/pipeline/orchestrator.py", doraise=True)
		check("orchestrator.py compiles", True)
	except py_compile.PyCompileError as e:
		check("orchestrator.py compiles", False, str(e))

	try:
		py_compile.compile("backend/src/nexus/api/routes/experiments.py", doraise=True)
		check("experiments.py compiles", True)
	except py_compile.PyCompileError as e:
		check("experiments.py compiles", False, str(e))

	print(f"\n{'='*50}")
	print(f"RESULTS: {passed} passed, {failed} failed")
	if failed > 0:
		sys.exit(1)
	else:
		print("ALL CHECKS PASSED")


def _try_compile(code: str) -> bool:
	try:
		compile(code, "<test>", "exec")
		return True
	except SyntaxError:
		return False


if __name__ == "__main__":
	asyncio.run(main())
