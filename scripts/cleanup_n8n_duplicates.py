"""Remove duplicate workflows — keep newest IDs."""
import httpx

URL      = "https://tillu-ai-tillu-engine.hf.space"
EMAIL    = "tillu@tillu.ai"
PASSWORD = "A45Bab2410ce@Tillu"

# Old IDs from first partial import — delete these
OLD_IDS = ["XZicRmQMuDD1KWj2", "6XaI4zrb2eE2FymO", "yG4vp6TaNqziGxoK"]

client = httpx.Client(timeout=20, follow_redirects=True)
client.post(URL + "/rest/login", json={"emailOrLdapLoginId": EMAIL, "password": PASSWORD})

for wid in OLD_IDS:
    # Deactivate first
    client.patch(URL + "/rest/workflows/" + wid, json={"active": False})
    # Then delete
    r = client.delete(URL + "/rest/workflows/" + wid)
    print("Deleted " + wid + " -> " + str(r.status_code))

# Final state
r = client.get(URL + "/rest/workflows")
wfs = r.json().get("data", [])
print("\nFinal (" + str(len(wfs)) + " workflows):")
for wf in wfs:
    print("  [" + wf.get("id") + "] " + wf.get("name"))
