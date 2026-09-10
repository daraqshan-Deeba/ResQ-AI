# ResQ AI — Context Retriever Setup

Expose ResQ operational data (community reports, shelters, SOS events) to AI agents via [Redis Context Retriever](https://redis.io/docs/latest/develop/ai/context-engine/context-retriever/) MCP tools.

> **Python 3.11+ required.** The default backend venv (3.10) cannot install `context-surfaces`. Use Python 3.12 as shown below.

## 1. Install the CLI

```powershell
py -3.12 -m pip install -r requirements.txt
```

On Windows, `ctxctl` is installed under your Python user Scripts folder. Either add that folder to `PATH`, or call it explicitly:

```powershell
$CTXCTL = "$env:LOCALAPPDATA\Packages\PythonSoftwareFoundation.Python.3.12_qbz5n2kfra8p0\LocalCache\local-packages\Python312\Scripts\ctxctl.exe"
```

## 2. Authenticate

```powershell
& $CTXCTL auth login --username "you@example.com"
```

This opens Redis Cloud OAuth. Use the account that owns your Context Retriever service.

## 3. Model definitions

Entity models live in [`models.py`](./models.py):

- `CommunityReport` — searchable by area and message text
- `Shelter` — numeric capacity/occupancy filters
- `SosEvent` — location + notification status

Validate locally:

```powershell
py -3.12 -c "from models import CommunityReport, Shelter, SosEvent; print('OK')"
```

## 4. Create a Context Retriever surface

Set Redis connection details (Redis Cloud or self-hosted with Search + JSON modules):

```powershell
$env:REDIS_PASSWORD = "<your-redis-password>"

& $CTXCTL surface create `
  --name "ResQ AI Surface" `
  --models ./models.py `
  --redis-addr "redis.example.com:6379" `
  --redis-password $env:REDIS_PASSWORD
```

For Redis Cloud TLS endpoints, add `--redis-tls` and `--redis-username default` per your instance docs.

Save the returned **surface ID**.

## 5. Create an agent key

```powershell
& $CTXCTL agent create --surface-id "<SURFACE_ID>" --name "ResQ Agent"
```

Save the returned **agent key** — add it to your environment as `CONTEXT_RETRIEVER_AGENT_KEY`.

## 6. List tools and run a sample query

```powershell
& $CTXCTL tools list --agent-key "<AGENT_KEY>"

& $CTXCTL tools call search_communityreport_by_text --agent-key "<AGENT_KEY>" --query "flood"
& $CTXCTL tools call search_shelter_by_text --agent-key "<AGENT_KEY>" --query "community hall"
```

Tool names are auto-generated from your model names and indexed fields.

## Quick setup script (Windows)

```powershell
.\setup.ps1
```

Runs install + model validation. Auth, surface create, and agent key steps still require your Redis Cloud credentials interactively.

## Using from Python

```python
import asyncio
from context_surfaces import UnifiedClient

async def main():
    client = UnifiedClient()
    tools = await client.list_tools(agent_key="YOUR_AGENT_KEY")
    print(tools)

asyncio.run(main())
```

## Environment variables

| Variable | Purpose |
|----------|---------|
| `REDIS_PASSWORD` | Redis data source password for `surface create` |
| `CONTEXT_RETRIEVER_AGENT_KEY` | Agent key for MCP tool calls |
| `CONTEXT_RETRIEVER_SURFACE_ID` | Surface ID for admin operations |
