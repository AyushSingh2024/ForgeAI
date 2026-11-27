---
title: ForgeAI
emoji: 🛠️
colorFrom: blue
colorTo: indigo
sdk: docker
app_port: 7860
pinned: false
---

# ForgeAI backend

The API of [ForgeAI](https://github.com/AyushSingh2024/ForgeAI): brief + documents in, tested agent out.
This Space builds the backend from the GitHub repository and runs a local `llama3.2:3b` judge with Ollama
inside the same container.

- Health check: `/health`. API docs: `/docs`.
- Required secrets (Settings → Variables and secrets): `OPENAI_API_KEY`, `API_KEY`.
- Required variable: `CORS_ORIGINS` = the Vercel URL of the frontend.
- After pushing new code to GitHub, use **Settings → Factory rebuild** to pick it up.
