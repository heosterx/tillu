path = "deployments/huggingface/websearch-space/main.py"
with open(path, encoding="utf-8") as f:
    content = f.read()

# Update port in the uvicorn launch at bottom of file
content = content.replace(
    'demo.launch(server_name="0.0.0.0", server_port=8080)',
    'demo.launch(server_name="0.0.0.0", server_port=7860)'
)
# Also update any hardcoded 8080 references in comments/strings
content = content.replace("port 8080", "port 7860")
content = content.replace(":8080", ":7860")

with open(path, "w", encoding="utf-8") as f:
    f.write(content)

print("Done — port references updated to 7860")
