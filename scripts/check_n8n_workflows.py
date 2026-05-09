"""Check n8n workflows loaded in the HF Space."""
import httpx
import json

URL = "https://tillu-ai-tillu-engine.hf.space"
EMAIL = "tillu@tillu.ai"
PASSWORD = "A45Bab2410ce@Tillu"

EXPECTED = [
    "Message Router",
    "Morning Intelligence Brief",
    "Memory Consolidation",
    "Personality Evolution",
]

print("=" * 55)
print("n8n Workflow Check")
print("=" * 55)

client = httpx.Client(timeout=20, follow_redirects=True)

# Login
login = client.post(
    URL + "/rest/login",
    json={"emailOrLdapLoginId": EMAIL, "password": PASSWORD},
)
print("Login:", login.status_code)
if login.status_code != 200:
    print("Login failed:", login.text[:200])
    exit(1)

# List workflows
r = client.get(URL + "/rest/workflows")
print("Workflows API:", r.status_code)

if r.status_code != 200:
    print("Error:", r.text[:300])
    exit(1)

body = r.json()
wfs = body.get("data", body) if isinstance(body, dict) else body
print("Total workflows:", len(wfs))
print()

found = [wf.get("name", "") for wf in wfs]

for name in EXPECTED:
    matched = any(name.lower() in n.lower() for n in found)
    icon = "OK  " if matched else "MISS"
    print("  [" + icon + "] " + name)

print()
print("All loaded:")
for wf in wfs:
    wid = str(wf.get("id", "?"))
    wname = wf.get("name", "?")
    active = wf.get("active", False)
    print("  - [" + wid + "] " + wname + " | active=" + str(active))

print("=" * 55)
