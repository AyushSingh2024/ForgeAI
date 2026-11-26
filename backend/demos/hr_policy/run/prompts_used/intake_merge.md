---
id: intake_merge
version: 1
purpose: turn a free-text interview answer into list edits (items to add / remove)
inputs: [field, current, answer]
output_schema: ListEdit
---
A list of {{ field }} currently contains:
{% for x in current %}
- {{ x }}
{% endfor %}

The user answered: "{{ answer }}"

Turn the answer into edits of the list. "add" = new short items (a few words each) the user wants. "remove" =
existing items the user wants dropped, copied exactly from the list. If the answer asks for no change, return
empty lists. Do not add anything the user did not say.

Return JSON: {"add": [], "remove": []}
