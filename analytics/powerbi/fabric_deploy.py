"""Deploy the AeroPulse Power BI Project into a Fabric workspace (run inside a Fabric notebook).

Used when GitHub Git integration is disabled by the tenant. Runs with the notebook user's own
identity via Microsoft's `sempy` library (no tokens handled by hand), reads the validated PBIP
files from this public repository, and calls the documented Fabric REST APIs:

* POST /v1/workspaces/{id}/semanticModels  (TMDL definition parts)
* POST /v1/workspaces/{id}/reports         (PBIR definition parts, bound byConnection)
* then triggers a semantic model refresh.

Re-running updates the existing items in place (updateDefinition) instead of duplicating them.

In a Fabric notebook cell:
    import urllib.request
    exec(urllib.request.urlopen("https://raw.githubusercontent.com/Gnanasudharsan/aeropulse-aviation-intelligence/main/analytics/powerbi/fabric_deploy.py").read().decode())
"""

import base64
import json
import time
import urllib.request

import sempy.fabric as fabric

REPO = "Gnanasudharsan/aeropulse-aviation-intelligence"
REF = "main"
BASE = "analytics/powerbi"
NAME = "AeroPulse Airport Performance"
API = "https://api.fabric.microsoft.com"

ws_id = fabric.get_workspace_id()
ws_name = fabric.resolve_workspace_name(ws_id)
client = fabric.FabricRestClient()


def _get(url):
    req = urllib.request.Request(url, headers={"User-Agent": "aeropulse-fabric-deploy"})
    with urllib.request.urlopen(req, timeout=60) as r:
        return r.read()


TREE = [
    t["path"]
    for t in json.loads(_get(f"https://api.github.com/repos/{REPO}/git/trees/{REF}?recursive=1"))["tree"]
    if t["type"] == "blob"
]


def parts(folder, override=None):
    prefix = f"{BASE}/{folder}/"
    out = []
    for path in TREE:
        if path.startswith(prefix) and not path.endswith("/.platform"):
            rel = path[len(prefix) :]
            data = (
                override[rel]
                if override and rel in override
                else _get(f"https://raw.githubusercontent.com/{REPO}/{REF}/{path}")
            )
            out.append({"path": rel, "payload": base64.b64encode(data).decode(), "payloadType": "InlineBase64"})
    return out


def wait(resp):
    """Follow a Fabric long-running operation to completion."""
    if resp.status_code in (200, 201):
        return resp.json() if resp.content else {}
    if resp.status_code != 202:
        raise RuntimeError(f"{resp.status_code}: {resp.text}")
    location = resp.headers["Location"].replace(API, "")
    while True:
        time.sleep(int(resp.headers.get("Retry-After", 5)))
        state = client.get(location).json()
        if state.get("status") == "Succeeded":
            result = client.get(location + "/result")
            return result.json() if result.status_code == 200 and result.content else {}
        if state.get("status") == "Failed":
            raise RuntimeError(json.dumps(state))


def existing(kind):
    items = client.get(f"/v1/workspaces/{ws_id}/{kind}").json().get("value", [])
    return next((i["id"] for i in items if i["displayName"] == NAME), None)


def upsert(kind, definition_parts):
    item_id = existing(kind)
    if item_id:
        wait(
            client.post(
                f"/v1/workspaces/{ws_id}/{kind}/{item_id}/updateDefinition",
                json={"definition": {"parts": definition_parts}},
            )
        )
        print(f"updated {kind[:-1]} {item_id}")
        return item_id
    created = wait(
        client.post(
            f"/v1/workspaces/{ws_id}/{kind}", json={"displayName": NAME, "definition": {"parts": definition_parts}}
        )
    )
    item_id = created.get("id") or existing(kind)
    print(f"created {kind[:-1]} {item_id}")
    return item_id


model_id = upsert("semanticModels", parts("AeroPulse.SemanticModel"))

pbir = {
    "$schema": "https://developer.microsoft.com/json-schemas/fabric/item/report/definitionProperties/2.0.0/schema.json",
    "version": "4.0",
    "datasetReference": {
        "byConnection": {
            "connectionString": (
                f'Data Source="powerbi://api.powerbi.com/v1.0/myorg/{ws_name}";initial catalog="{NAME}";'
                f"integrated security=ClaimsToken;semanticmodelid={model_id}"
            )
        }
    },
}
report_id = upsert("reports", parts("AeroPulse.Report", {"definition.pbir": json.dumps(pbir).encode()}))

try:
    fabric.refresh_dataset(dataset=NAME, workspace=ws_id)
    print("refresh requested")
except Exception as exc:  # e.g. data source credentials not yet set
    print(f"refresh not started: {exc}")

print(json.dumps({"workspace": ws_name, "semantic_model_id": model_id, "report_id": report_id}))
