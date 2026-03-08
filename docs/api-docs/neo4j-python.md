# Neo4j Python Driver Reference

## Installation
```bash
pip install neo4j
```

Supports Bolt protocol 4.4, 5.0-5.8, 6.0. Python 3.10-3.14.

## Connection Setup

### Local
```python
from neo4j import GraphDatabase

driver = GraphDatabase.driver("neo4j://localhost:7687", auth=("neo4j", "password"))
```

### Neo4j Aura (cloud)
```python
driver = GraphDatabase.driver(
	"neo4j+s://xxxx.databases.neo4j.io",
	auth=("neo4j", "your-password")
)
```

## Query Execution

### Simple (recommended for most cases)
```python
records, summary, keys = driver.execute_query(
	"MATCH (a:Person)-[:KNOWS]->(friend) WHERE a.name = $name RETURN friend.name",
	name="Arthur",
	database_="neo4j",
	routing_=RoutingControl.READ
)
for record in records:
	print(record["friend.name"])
```

### Session-based (for transactions)
```python
with driver.session() as session:
	result = session.run("MATCH (n) RETURN n LIMIT 10")
	for record in result:
		print(record)
```

### Write transactions with retry
```python
def create_node(tx, name):
	tx.run("CREATE (p:Person {name: $name})", name=name)

with driver.session() as session:
	session.execute_write(create_node, "Alice")
```

## Async Support
```python
from neo4j import AsyncGraphDatabase

async_driver = AsyncGraphDatabase.driver(uri, auth=auth)
records, summary, keys = await async_driver.execute_query(query, **params)
```

## Error Handling
```python
from neo4j.exceptions import DriverError, Neo4jError

try:
	records, summary, keys = driver.execute_query(query)
except (DriverError, Neo4jError) as e:
	logging.error(f"Query failed: {e}")
```

## Data Types
Supports: Spatial, Temporal, Vector, and standard Python types.

## Connection Pooling
Managed automatically by the driver. Configure via driver constructor parameters.

## Cleanup
```python
driver.close()  # Always close when done
```

## Source
https://neo4j.com/docs/api/python-driver/current/
