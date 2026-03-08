# Supabase Python Client Reference

## Installation
```bash
pip install supabase
```

## Client Initialization
```python
import os
from supabase import create_client, Client

url = os.environ.get("SUPABASE_URL")
key = os.environ.get("SUPABASE_ANON_KEY")
supabase: Client = create_client(url, key)
```

### With options
```python
from supabase.client import ClientOptions

supabase = create_client(url, key, options=ClientOptions(
	postgrest_client_timeout=10,
	storage_client_timeout=10,
	schema="public",
))
```

## Database Operations

### Select
```python
response = supabase.table("users").select("*").execute()
response = supabase.table("users").select("name, email").eq("active", True).execute()
```

### Insert
```python
response = supabase.table("users").insert({"name": "John", "email": "john@example.com"}).execute()
```

### Update
```python
response = supabase.table("users").update({"name": "Jane"}).eq("id", 1).execute()
```

### Upsert
```python
response = supabase.table("users").upsert({"id": 1, "name": "Jane"}).execute()
```

### Delete
```python
response = supabase.table("users").delete().eq("id", 1).execute()
```

## Filtering
```python
.eq("column", value)       # equals
.neq("column", value)      # not equals
.gt("column", value)       # greater than
.gte("column", value)      # greater than or equal
.lt("column", value)       # less than
.lte("column", value)      # less than or equal
.like("column", "%pattern%")
.ilike("column", "%pattern%")  # case insensitive
.in_("column", ["a", "b"])
.contains("column", {"key": "val"})
.overlaps("column", [1, 2])
.not_.is_("column", "null")
.or_("col1.eq.val1,col2.eq.val2")
.filter("column", "op", "value")
```

## Modifiers
```python
.order("column", desc=True)
.limit(10)
.range(0, 9)
.single()           # expect exactly one row
.maybe_single()     # expect zero or one row
.csv()              # return as CSV
```

## Authentication
```python
# Sign up
supabase.auth.sign_up({"email": "user@example.com", "password": "password"})

# Sign in
supabase.auth.sign_in_with_password({"email": "user@example.com", "password": "password"})

# Sign out
supabase.auth.sign_out()

# Get user
user = supabase.auth.get_user()

# Get session
session = supabase.auth.get_session()
```

## Edge Functions
```python
response = supabase.functions.invoke("function-name", invoke_options={"body": {"key": "value"}})
```

## Real-time
```python
channel = supabase.channel("room1")
channel.on_broadcast("event", callback).subscribe()
channel.send_broadcast("event", {"message": "hello"})
```

## Storage
```python
# Upload
supabase.storage.from_("bucket").upload("path/file.pdf", file_data)

# Download
data = supabase.storage.from_("bucket").download("path/file.pdf")

# Get public URL
url = supabase.storage.from_("bucket").get_public_url("path/file.pdf")
```

## RPC (Remote Procedure Call)
```python
response = supabase.rpc("function_name", {"param1": "value1"}).execute()
```

## Source
https://supabase.com/docs/reference/python/introduction
