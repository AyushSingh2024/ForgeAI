---
title: ForgeAI
emoji: 🛠️
colorFrom: blue
colorTo: indigo
sdk: gradio
sdk_version: 6.32.0
python_version: "3.11"
app_file: server.py
pinned: false
---

# ForgeAI backend

The API of [ForgeAI](https://github.com/AyushSingh2024/ForgeAI): brief + documents in, tested agent out.
This Space runs on the free Gradio SDK: `server.py` downloads the backend from GitHub, serves the FastAPI app
(with a small status page at `/`), and installs a local Ollama `llama3.2:3b` judge in the background.

- API docs: `/docs`. Health: `/health`.
- Secrets (Settings → Variables and secrets): `OPENAI_API_KEY`, `API_KEY`.
- Variable: `CORS_ORIGINS` = the Vercel URL of the frontend.
- To pick up new code pushed to GitHub: **Settings → Restart this Space**.
