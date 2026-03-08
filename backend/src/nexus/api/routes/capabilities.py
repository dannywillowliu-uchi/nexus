from fastapi import APIRouter

router = APIRouter()

CAPABILITIES = {
	"tools": [
		{"name": "DiffDock", "category": "docking", "provider": "Tamarind Bio", "description": "Protein-ligand docking prediction"},
		{"name": "AutoDock Vina", "category": "docking", "provider": "Tamarind Bio", "description": "Classical molecular docking"},
		{"name": "AlphaFold", "category": "structure", "provider": "Tamarind Bio", "description": "Protein structure prediction"},
		{"name": "ESMFold", "category": "structure", "provider": "Tamarind Bio", "description": "Fast protein folding"},
		{"name": "ADMET Prediction", "category": "properties", "provider": "Tamarind Bio", "description": "Drug-likeness and ADMET properties"},
		{"name": "DeepFRI", "category": "function", "provider": "Tamarind Bio", "description": "Protein function prediction"},
		{"name": "ThermoMPNN", "category": "stability", "provider": "Tamarind Bio", "description": "Protein thermostability prediction"},
		{
			"name": "Literature Validation",
			"category": "literature",
			"provider": "PubMed/Semantic Scholar",
			"description": "Cross-reference against published literature",
		},
		{"name": "Pathway Overlap", "category": "pathway", "provider": "Internal", "description": "Biological pathway intersection analysis"},
		{
			"name": "Expression Correlation",
			"category": "expression",
			"provider": "Internal",
			"description": "Gene expression correlation analysis",
		},
	],
	"data_sources": [
		{"name": "PrimeKG", "nodes": 129375, "edges": 8100498, "description": "Precision Medicine Knowledge Graph"},
		{"name": "Hetionet", "nodes": 47031, "edges": 2250197, "description": "Integrative biomedical knowledge graph"},
		{"name": "PubMed", "type": "literature", "description": "Biomedical literature database via NCBI E-utilities"},
		{"name": "Semantic Scholar", "type": "literature", "description": "AI-powered academic search"},
	],
	"pipeline_stages": [
		"Literature Mining",
		"Knowledge Graph Enrichment",
		"Swanson ABC Traversal",
		"Adaptive Checkpoint",
		"Reasoning Agent",
		"Computational Validation",
		"Protocol Generation",
		"Cloud Lab Execution",
	],
	"cloud_labs": [
		{"name": "Strateos", "status": "integrated", "capabilities": ["dose-response", "binding-assay", "cell-viability"]},
		{"name": "Ginkgo Bioworks", "status": "planned", "capabilities": []},
	],
}


@router.get("/capabilities")
async def get_capabilities():
	"""Return platform capabilities, tools, data sources, and integrations."""
	return CAPABILITIES
