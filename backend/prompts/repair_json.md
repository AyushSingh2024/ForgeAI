---
id: repair_json
version: 1
purpose: fix invalid JSON against a schema
inputs: [error, schema]
output_schema: same as the failed call
---
Your previous reply could not be used. Problem: {{ error }}

Return ONLY the corrected JSON object. Keep the same content, fix only the structure and types.
It must match this JSON schema exactly:
{{ schema }}
