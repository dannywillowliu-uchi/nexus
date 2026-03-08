# PubChem PUG REST API Reference

## Base URL
`https://pubchem.ncbi.nlm.nih.gov/rest/pug`

## Authentication
None required (public API).

## Rate Limits
- Max 5 requests per second
- Max 400 requests per minute
- Excessive use may result in temporary IP block
- Use `User-Agent` header with contact email for heavy usage

## URL Pattern
```
/rest/pug/{domain}/{namespace}/{identifiers}/{operation}/{output}
```

## Core Endpoints

### Compound Properties
Get properties for a compound by name.

```
GET /rest/pug/compound/name/{name}/property/{properties}/JSON
```

```
GET /rest/pug/compound/name/curcumin/property/MolecularFormula,MolecularWeight,IUPACName,CanonicalSMILES,XLogP/JSON
```

**Response:**
```json
{
	"PropertyTable": {
		"Properties": [
			{
				"CID": 969516,
				"MolecularFormula": "C21H20O6",
				"MolecularWeight": 368.38,
				"IUPACName": "(1E,6E)-1,7-bis(4-hydroxy-3-methoxyphenyl)hepta-1,6-diene-3,5-dione",
				"CanonicalSMILES": "COC1=CC(/C=C/C(=O)CC(=O)/C=C/C2=CC(=C(C=C2)O)OC)=CC=C1O",
				"XLogP": 3.2
			}
		]
	}
}
```

**Available Properties:**
`MolecularFormula`, `MolecularWeight`, `CanonicalSMILES`, `IsomericSMILES`, `InChI`, `InChIKey`, `IUPACName`, `XLogP`, `ExactMass`, `MonoisotopicMass`, `TPSA`, `Complexity`, `Charge`, `HBondDonorCount`, `HBondAcceptorCount`, `RotatableBondCount`, `HeavyAtomCount`, `AtomStereoCount`, `BondStereoCount`, `CovalentUnitCount`

### Compound by CID
```
GET /rest/pug/compound/cid/969516/property/MolecularWeight,XLogP/JSON
```

### Compound Synonyms
```
GET /rest/pug/compound/name/aspirin/synonyms/JSON
```

### Compound Description
```
GET /rest/pug/compound/name/curcumin/description/JSON
```

### Compound Assays
Get bioassay data for a compound.
```
GET /rest/pug/compound/name/curcumin/assaysummary/JSON
```

### Substructure Search
```
POST /rest/pug/compound/substructure/smiles/JSON
Content-Type: application/x-www-form-urlencoded

smiles=c1ccccc1
```

### Similarity Search
```
GET /rest/pug/compound/similarity/smiles/{smiles}/JSON?Threshold=90
```

## Batch Queries
Multiple CIDs in one request:
```
GET /rest/pug/compound/cid/2244,3672,5988/property/MolecularWeight,MolecularFormula/JSON
```

Multiple names (POST):
```
POST /rest/pug/compound/name/property/MolecularWeight,MolecularFormula/JSON
Content-Type: application/x-www-form-urlencoded

name=aspirin&name=ibuprofen&name=curcumin
```

## Error Handling
```json
{
	"Fault": {
		"Code": "PUGREST.NotFound",
		"Message": "No CID found",
		"Details": ["No CID found for the given name"]
	}
}
```

Common fault codes:
- `PUGREST.NotFound` — Compound not found
- `PUGREST.BadRequest` — Invalid input
- `PUGREST.ServerBusy` — Rate limited, retry after delay
- `PUGREST.Timeout` — Query too complex

## Nexus Usage
- `tools/compound_check.py` — Looks up compound properties (MW, SMILES, XLogP) to validate drug-likeness
- Lipinski's Rule of Five: MW < 500, XLogP < 5, HBD < 5, HBA < 10
- Used to validate whether compounds in ABC hypotheses are viable drug candidates

## Source
- https://pubchem.ncbi.nlm.nih.gov/docs/pug-rest
- https://pubchem.ncbi.nlm.nih.gov/docs/pug-rest-tutorial
