# Strateos (Cloud Lab) API Reference

## Base URL
`https://secure.transcriptic.com`

## Authentication
Login to get a session cookie, then use cookie-based auth for subsequent requests.
Alternatively, use the Transcriptic Python CLI which handles auth.

Environment variables:
- `STRATEOS_EMAIL` — Account email
- `STRATEOS_TOKEN` — API token (from web UI Settings > API)
- `STRATEOS_ORGANIZATION_ID` — Organization slug (e.g., `org_id`)

## Python CLI
```bash
pip install transcriptic
transcriptic login
```

```python
import transcriptic
api = transcriptic.Connection.from_default_env()
```

## Autoprotocol Format

Strateos accepts experiments in **Autoprotocol** JSON format — a standardized protocol description language.

### Structure
```json
{
	"refs": {
		"my_plate": {
			"new": "96-pcr-std",
			"store": {"where": "cold_4", "shaking": false}
		},
		"reagent_plate": {
			"id": "ct_existing_container_id",
			"discard": true
		}
	},
	"instructions": [
		{
			"op": "pipette",
			"groups": [
				{
					"transfer": [
						{
							"from": "reagent_plate/A1",
							"to": "my_plate/A1",
							"volume": "10:microliter"
						}
					]
				}
			]
		},
		{
			"op": "seal",
			"object": "my_plate",
			"type": "ultra-clear"
		},
		{
			"op": "thermocycle",
			"object": "my_plate",
			"groups": [
				{"cycles": 1, "steps": [{"temperature": "95:celsius", "duration": "5:minute"}]},
				{"cycles": 30, "steps": [
					{"temperature": "95:celsius", "duration": "30:second"},
					{"temperature": "55:celsius", "duration": "30:second"},
					{"temperature": "72:celsius", "duration": "60:second"}
				]}
			]
		}
	]
}
```

### Common Operations (ops)
| Op | Purpose |
|----|---------|
| `pipette` | Liquid transfer (transfer, distribute, consolidate, mix) |
| `seal` | Seal a plate |
| `unseal` | Unseal a plate |
| `thermocycle` | PCR / thermal cycling |
| `incubate` | Incubate at temperature |
| `spin` | Centrifuge |
| `absorbance` | Plate reader absorbance |
| `fluorescence` | Plate reader fluorescence |
| `gel_separate` | Gel electrophoresis |
| `spectrophotometry` | Measure optical density |

### Refs (Container References)
- `"new": "container_type"` — Create new container
- `"id": "ct_..."` — Reference existing container
- `"store"` — Store after protocol (cold_4, cold_20, cold_80, ambient)
- `"discard": true` — Discard after protocol

### Units
Format: `"value:unit"` (e.g., `"10:microliter"`, `"95:celsius"`, `"5:minute"`)

## Key Endpoints

### POST /{org_id}/runs
Submit an Autoprotocol run.
```json
{
	"title": "Nexus Docking Validation",
	"protocol": { ... autoprotocol JSON ... },
	"project_id": "p_..."
}
```

### GET /{org_id}/runs/{run_id}
Check run status. Statuses: `accepted`, `in_progress`, `complete`, `aborted`, `canceled`.

### GET /{org_id}/runs/{run_id}/data
Get run data/results after completion.

### GET /{org_id}/projects
List projects.

### GET /{org_id}/inventory
List containers in inventory.

## Run Lifecycle
1. Submit protocol via POST `/{org_id}/runs`
2. Run enters `accepted` -> `in_progress`
3. Poll GET `/{org_id}/runs/{run_id}` for status
4. On `complete`, fetch results via `/{org_id}/runs/{run_id}/data`

## Autoprotocol Libraries
- **autoprotocol-python**: `pip install autoprotocol` — Build protocols programmatically
```python
from autoprotocol import Protocol

p = Protocol()
plate = p.ref("my_plate", cont_type="96-pcr-std", storage="cold_4")
p.transfer(source_plate.well("A1"), plate.well("A1"), "10:microliter")
p.seal(plate)
p.thermocycle(plate, groups=[...])
print(p.as_dict())  # Autoprotocol JSON
```

## Nexus Usage
- `cloudlab/strateos_client.py` — Submits validation experiments
- `tools/generate_protocol.py` — Generates Autoprotocol JSON from hypothesis parameters
- Used in the final pipeline stage to physically validate computational predictions

## Source
- https://developers.strateos.com
- https://autoprotocol.org
- https://github.com/autoprotocol/autoprotocol-python
