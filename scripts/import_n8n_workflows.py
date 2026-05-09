"""Import all TILLU workflows into the live n8n instance."""
import httpx
import json
import os

URL      = "https://tillu-ai-tillu-engine.hf.space"
EMAIL    = "tillu@tillu.ai"
PASSWORD = "A45Bab2410ce@Tillu"

WORKFLOWS_DIR = os.path.join(
    os.path.dirname(__file__), "..", "n8n", "workflows"
)

print("=" * 55)
print("Importing TILLU workflows into n8n")
print("=" * 55)

client = httpx.Client(timeout=30, follow_redirects=True)

# Login
login = client.post(
    URL + "/rest/login",
    json={"emailOrLdapLoginId": EMAIL, "password": PASSWORD},
)
print("Login:", login.status_code)
if login.status_code != 200:
    print("Login failed:", login.text[:200])
    exit(1)

# Import each workflow file
workflow_files = [f for f in os.listdir(WORKFLOWS_DIR) if f.endswith(".json")]
print("Found", len(workflow_files), "workflow files\n")

imported = 0
for fname in sorted(workflow_files):
    fpath = os.path.join(WORKFLOWS_DIR, fname)
    with open(fpath, "r", encoding="utf-8") as f:
        wf_data = json.load(f)

    name = wf_data.get("name", fname)

    # POST to create workflow
    r = client.post(URL + "/rest/workflows", json=wf_data)

    if r.status_code in (200, 201):
        wf_id = r.json().get("data", {}).get("id", "?")
        print("  [OK  ] " + name + " (id=" + str(wf_id) + ")")
        imported += 1
    elif r.status_code == 409:
        print("  [SKIP] " + name + " (already exists)")
    else:
        print("  [FAIL] " + name + " — " + str(r.status_code) + ": " + r.text[:120])

print()
print("Imported:", imported, "/", len(workflow_files))

# Final list
r = client.get(URL + "/rest/workflows")
wfs = r.json().get("data", [])
print("Total in n8n now:", len(wfs))
for wf in wfs:
    print("  - " + wf.get("name", "?") + " | active=" + str(wf.get("active")))

print("=" * 55)
