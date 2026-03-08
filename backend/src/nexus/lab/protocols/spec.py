from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class CompoundSpec:
	"""Resolved compound with identifiers, physical properties, and test parameters."""

	name: str
	cas_number: str = ""
	smiles: str = ""
	inchi_key: str = ""
	molecular_weight: float = 0.0
	iupac_name: str = ""
	pubchem_cid: int = 0
	supplier: str = ""
	catalog_number: str = ""
	stock_concentration_uM: float = 10_000.0
	solvent: str = "DMSO"
	storage_temp_C: float = -20.0
	test_concentrations_uM: list[float] = field(default_factory=lambda: [100, 50, 25, 10, 5, 1, 0.1])

	def to_dict(self) -> dict:
		return {
			"name": self.name,
			"cas_number": self.cas_number,
			"smiles": self.smiles,
			"inchi_key": self.inchi_key,
			"molecular_weight": self.molecular_weight,
			"iupac_name": self.iupac_name,
			"pubchem_cid": self.pubchem_cid,
			"supplier": self.supplier,
			"catalog_number": self.catalog_number,
			"stock_concentration_uM": self.stock_concentration_uM,
			"solvent": self.solvent,
			"storage_temp_C": self.storage_temp_C,
			"test_concentrations_uM": self.test_concentrations_uM,
		}

	@classmethod
	def from_dict(cls, d: dict) -> CompoundSpec:
		return cls(**{k: v for k, v in d.items() if k in cls.__dataclass_fields__})


@dataclass
class CellModelSpec:
	"""Cell line specification with culture conditions."""

	name: str
	atcc_number: str = ""
	organism: str = "Homo sapiens"
	tissue: str = ""
	culture_medium: str = ""
	serum: str = ""
	seeding_density_cells_per_well: int = 10_000
	doubling_time_hours: float = 24.0
	growth_mode: str = "adherent"
	disease_relevance: str = ""

	def to_dict(self) -> dict:
		return {
			"name": self.name,
			"atcc_number": self.atcc_number,
			"organism": self.organism,
			"tissue": self.tissue,
			"culture_medium": self.culture_medium,
			"serum": self.serum,
			"seeding_density_cells_per_well": self.seeding_density_cells_per_well,
			"doubling_time_hours": self.doubling_time_hours,
			"growth_mode": self.growth_mode,
			"disease_relevance": self.disease_relevance,
		}

	@classmethod
	def from_dict(cls, d: dict) -> CellModelSpec:
		return cls(**{k: v for k, v in d.items() if k in cls.__dataclass_fields__})


@dataclass
class ProteinSpec:
	"""Target protein specification."""

	name: str
	uniprot_id: str = ""
	gene_name: str = ""
	organism: str = "Homo sapiens"
	pdb_ids: list[str] = field(default_factory=list)
	function: str = ""
	protein_class: str = ""

	def to_dict(self) -> dict:
		return {
			"name": self.name,
			"uniprot_id": self.uniprot_id,
			"gene_name": self.gene_name,
			"organism": self.organism,
			"pdb_ids": self.pdb_ids,
			"function": self.function,
			"protein_class": self.protein_class,
		}

	@classmethod
	def from_dict(cls, d: dict) -> ProteinSpec:
		return cls(**{k: v for k, v in d.items() if k in cls.__dataclass_fields__})


@dataclass
class DilutionStep:
	"""A single dilution step with volumes and concentrations."""

	target_concentration_uM: float
	source_concentration_uM: float
	transfer_volume_uL: float
	diluent_volume_uL: float
	final_volume_uL: float
	needs_intermediate: bool = False
	intermediate_concentration_uM: float = 0.0
	intermediate_transfer_uL: float = 0.0
	intermediate_diluent_uL: float = 0.0
	dmso_fraction: float = 0.0

	def to_dict(self) -> dict:
		return {
			"target_concentration_uM": self.target_concentration_uM,
			"source_concentration_uM": self.source_concentration_uM,
			"transfer_volume_uL": self.transfer_volume_uL,
			"diluent_volume_uL": self.diluent_volume_uL,
			"final_volume_uL": self.final_volume_uL,
			"needs_intermediate": self.needs_intermediate,
			"intermediate_concentration_uM": self.intermediate_concentration_uM,
			"intermediate_transfer_uL": self.intermediate_transfer_uL,
			"intermediate_diluent_uL": self.intermediate_diluent_uL,
			"dmso_fraction": self.dmso_fraction,
		}

	@classmethod
	def from_dict(cls, d: dict) -> DilutionStep:
		return cls(**{k: v for k, v in d.items() if k in cls.__dataclass_fields__})


@dataclass
class ControlSpec:
	"""Control well specification."""

	control_type: str  # "positive", "negative", "vehicle", "blank"
	description: str = ""
	compound_name: str = ""
	concentration_uM: float = 0.0
	expected_response: str = ""

	def to_dict(self) -> dict:
		return {
			"control_type": self.control_type,
			"description": self.description,
			"compound_name": self.compound_name,
			"concentration_uM": self.concentration_uM,
			"expected_response": self.expected_response,
		}

	@classmethod
	def from_dict(cls, d: dict) -> ControlSpec:
		return cls(**{k: v for k, v in d.items() if k in cls.__dataclass_fields__})


@dataclass
class ReadoutSpec:
	"""Assay readout specification."""

	readout_type: str  # "absorbance", "fluorescence", "luminescence"
	wavelength_nm: int = 0
	excitation_nm: int = 0
	emission_nm: int = 0
	read_time_minutes: int = 0
	instrument: str = ""

	def to_dict(self) -> dict:
		return {
			"readout_type": self.readout_type,
			"wavelength_nm": self.wavelength_nm,
			"excitation_nm": self.excitation_nm,
			"emission_nm": self.emission_nm,
			"read_time_minutes": self.read_time_minutes,
			"instrument": self.instrument,
		}

	@classmethod
	def from_dict(cls, d: dict) -> ReadoutSpec:
		return cls(**{k: v for k, v in d.items() if k in cls.__dataclass_fields__})


@dataclass
class SuccessCriteria:
	"""Criteria for evaluating experiment success."""

	min_z_factor: float = 0.5
	max_cv_percent: float = 20.0
	min_signal_to_background: float = 3.0
	significance_threshold: float = 0.05

	def to_dict(self) -> dict:
		return {
			"min_z_factor": self.min_z_factor,
			"max_cv_percent": self.max_cv_percent,
			"min_signal_to_background": self.min_signal_to_background,
			"significance_threshold": self.significance_threshold,
		}

	@classmethod
	def from_dict(cls, d: dict) -> SuccessCriteria:
		return cls(**{k: v for k, v in d.items() if k in cls.__dataclass_fields__})


@dataclass
class PlateLayout:
	"""Well assignment map for an assay plate."""

	plate_type: str = "96-well"
	plate_catalog: str = "corning_96_wellplate_360ul_flat"
	layout: dict[str, list[str]] = field(default_factory=dict)
	replicates: int = 3

	def to_dict(self) -> dict:
		return {
			"plate_type": self.plate_type,
			"plate_catalog": self.plate_catalog,
			"layout": self.layout,
			"replicates": self.replicates,
		}

	@classmethod
	def from_dict(cls, d: dict) -> PlateLayout:
		return cls(**{k: v for k, v in d.items() if k in cls.__dataclass_fields__})

	@property
	def total_wells_used(self) -> int:
		return sum(len(wells) for wells in self.layout.values())

	@property
	def max_wells(self) -> int:
		return 384 if "384" in self.plate_type else 96


@dataclass
class AssaySpec:
	"""Complete assay specification from the protocol library."""

	assay_type: str  # "MTT_viability", "fluorescence_polarization", etc.
	name: str = ""
	description: str = ""
	readout: ReadoutSpec = field(default_factory=lambda: ReadoutSpec(readout_type="absorbance"))
	incubation_time_hours: float = 24.0
	temperature_C: float = 37.0
	co2_percent: float = 5.0
	reagent_steps: list[dict] = field(default_factory=list)
	total_time_hours: float = 48.0
	controls: list[ControlSpec] = field(default_factory=list)
	success_criteria: SuccessCriteria = field(default_factory=SuccessCriteria)

	def to_dict(self) -> dict:
		return {
			"assay_type": self.assay_type,
			"name": self.name,
			"description": self.description,
			"readout": self.readout.to_dict(),
			"incubation_time_hours": self.incubation_time_hours,
			"temperature_C": self.temperature_C,
			"co2_percent": self.co2_percent,
			"reagent_steps": self.reagent_steps,
			"total_time_hours": self.total_time_hours,
			"controls": [c.to_dict() for c in self.controls],
			"success_criteria": self.success_criteria.to_dict(),
		}

	@classmethod
	def from_dict(cls, d: dict) -> AssaySpec:
		data = dict(d)
		if "readout" in data and isinstance(data["readout"], dict):
			data["readout"] = ReadoutSpec.from_dict(data["readout"])
		if "controls" in data and isinstance(data["controls"], list):
			data["controls"] = [ControlSpec.from_dict(c) if isinstance(c, dict) else c for c in data["controls"]]
		if "success_criteria" in data and isinstance(data["success_criteria"], dict):
			data["success_criteria"] = SuccessCriteria.from_dict(data["success_criteria"])
		return cls(**{k: v for k, v in data.items() if k in cls.__dataclass_fields__})


@dataclass
class ExperimentSpec:
	"""Complete experiment specification — the central interchange format.

	Everything downstream (code generators, simulators, interpreters) reads from this.
	"""

	hypothesis_id: str = ""
	hypothesis_title: str = ""
	hypothesis_type: str = ""
	disease_area: str = ""
	compound: CompoundSpec = field(default_factory=lambda: CompoundSpec(name="unknown"))
	cell_model: CellModelSpec = field(default_factory=lambda: CellModelSpec(name="unknown"))
	protein_target: ProteinSpec | None = None
	assay: AssaySpec = field(default_factory=lambda: AssaySpec(assay_type="MTT_viability"))
	plate_layout: PlateLayout = field(default_factory=PlateLayout)
	dilution_steps: list[DilutionStep] = field(default_factory=list)
	budget_tier: str = "minimal"

	def to_dict(self) -> dict:
		return {
			"hypothesis_id": self.hypothesis_id,
			"hypothesis_title": self.hypothesis_title,
			"hypothesis_type": self.hypothesis_type,
			"disease_area": self.disease_area,
			"compound": self.compound.to_dict(),
			"cell_model": self.cell_model.to_dict(),
			"protein_target": self.protein_target.to_dict() if self.protein_target else None,
			"assay": self.assay.to_dict(),
			"plate_layout": self.plate_layout.to_dict(),
			"dilution_steps": [s.to_dict() for s in self.dilution_steps],
			"budget_tier": self.budget_tier,
		}

	@classmethod
	def from_dict(cls, d: dict) -> ExperimentSpec:
		data = dict(d)
		if "compound" in data and isinstance(data["compound"], dict):
			data["compound"] = CompoundSpec.from_dict(data["compound"])
		if "cell_model" in data and isinstance(data["cell_model"], dict):
			data["cell_model"] = CellModelSpec.from_dict(data["cell_model"])
		if "protein_target" in data and isinstance(data["protein_target"], dict):
			data["protein_target"] = ProteinSpec.from_dict(data["protein_target"])
		elif "protein_target" in data and data["protein_target"] is None:
			pass
		if "assay" in data and isinstance(data["assay"], dict):
			data["assay"] = AssaySpec.from_dict(data["assay"])
		if "plate_layout" in data and isinstance(data["plate_layout"], dict):
			data["plate_layout"] = PlateLayout.from_dict(data["plate_layout"])
		if "dilution_steps" in data and isinstance(data["dilution_steps"], list):
			data["dilution_steps"] = [
				DilutionStep.from_dict(s) if isinstance(s, dict) else s for s in data["dilution_steps"]
			]
		return cls(**{k: v for k, v in data.items() if k in cls.__dataclass_fields__})
