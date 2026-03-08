#!/bin/bash
set -e

DATA_DIR="data/hetionet"
mkdir -p "$DATA_DIR"

COMBINED_BZ2="/tmp/hetionet-v1.0.json.bz2"
COMBINED_JSON="/tmp/hetionet-v1.0.json"

echo "Downloading Hetionet v1.0 (combined JSON via Git LFS)..."
curl -L "https://media.githubusercontent.com/media/hetio/hetionet/main/hetnet/json/hetionet-v1.0.json.bz2" -o "$COMBINED_BZ2"

echo "Decompressing..."
bunzip2 -k -f "$COMBINED_BZ2"

echo "Splitting into nodes and edges files..."
python3 -c "
import json, sys

with open('$COMBINED_JSON') as f:
	data = json.load(f)

nodes = data['nodes']
edges = data['edges']

with open('$DATA_DIR/hetionet-v1.0-nodes.json', 'w') as f:
	json.dump(nodes, f)
print(f'Wrote {len(nodes)} nodes')

with open('$DATA_DIR/hetionet-v1.0-edges.json', 'w') as f:
	json.dump(edges, f)
print(f'Wrote {len(edges)} edges')
"

echo "Cleaning up temp files..."
rm -f "$COMBINED_BZ2" "$COMBINED_JSON"

echo "Done. Files saved to $DATA_DIR/"
ls -lh "$DATA_DIR/"
