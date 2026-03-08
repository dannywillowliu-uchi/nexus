# Tamarind Bio API Reference

## Full OpenAPI Spec
See `tamarind-api-openapi.yaml` in the project root for complete specification.

## Base URL
`https://api.tamarind.com/v1`

## Authentication
API key via header: `x-api-key: YOUR_API_KEY`

## Rate Limits
10 requests per second on all endpoints.

## Pricing Tiers
- **Free**: 10 jobs/month, all models, web UI only (no API access)
- **Premium**: $50,000/year, API access, unlimited runtime, high-volume
- **Enterprise**: Custom pricing, custom model hosting, SLA, SAML SSO

## Core Endpoints

### POST /submit-job
Submit a single computational job.

```json
{
	"jobName": "my-protein-analysis",
	"type": "alphafold",
	"settings": {
		"target": "MKTVRQERLKSIVRILERSKEPVSGAQLAEELSVSRQVIVQDIAYLRSLGYNIVATPRGYVLAGG",
		"modelType": "monomer",
		"numRecycles": 3
	}
}
```

### POST /submit-batch
Submit multiple jobs in a single request.

```json
{
	"batchName": "my-batch",
	"jobs": [
		{"jobName": "job1", "type": "alphafold", "settings": {...}},
		{"jobName": "job2", "type": "rfdiffusion", "settings": {...}}
	]
}
```

### GET /jobs
List user's jobs. Supports filtering by jobName, batch, organization.
- `startKey`: Pagination cursor
- `limit`: Max results (default 1000)
- `includeSubjobs`: Include batch sub-jobs

### POST /result
Get job results (returns S3 presigned URL for download).

```json
{
	"jobName": "my-protein-analysis",
	"pdbsOnly": true
}
```

### PUT /upload/{filename}
Upload files (PDB, sequences, etc.) for use in jobs.
- Content-Type: application/octet-stream
- Optional `folder` query param

## Available Job Types (200+ models)
- **Structure Prediction**: alphafold, chai, boltz, esmfold, openfold
- **Protein Design**: rfdiffusion, proteinmpnn, ligandmpnn
- **Docking**: autodock_vina, diffdock, gnina
- **Property Prediction**: solubility, thermostability, immunogenicity
- **Molecular Dynamics**: gromacs, openmm
- **Antibody**: abnumber, igfold, antifold
- **Small Molecule**: reinvent, molpal

## Workflow Pattern
1. Upload input files via PUT /upload/{filename}
2. Submit job via POST /submit-job with file references
3. Poll GET /jobs?jobName=X until status is "Complete"
4. Download results via POST /result

## Sign Up
https://app.tamarind.bio/sign-up

## Source
- https://www.tamarind.bio/pricing
- OpenAPI spec: tamarind-api-openapi.yaml (project root)
