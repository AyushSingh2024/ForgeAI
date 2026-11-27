# ForgeAI backend + a local Ollama judge in ONE container.
# Works on Hugging Face Spaces (Docker SDK), an Oracle Cloud Always Free VM, or any Docker host.
#
#   docker build -t forgeai .
#   docker run -p 7860:7860 -e OPENAI_API_KEY=... -e API_KEY=... -e CORS_ORIGINS=https://<app>.vercel.app forgeai
#
# Build args: WITH_OLLAMA=0 skips Ollama (the judge then falls back to the agent's hosted model, with a warning);
#             JUDGE_MODEL picks the local judge (llama3.2:1b is faster on small CPUs).
FROM python:3.11-slim-bookworm

ARG WITH_OLLAMA=1
ARG JUDGE_MODEL=llama3.2:3b

ENV PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    HOME=/home/user \
    OLLAMA_MODELS=/opt/ollama/models \
    OLLAMA_NOPRUNE=1 \
    FASTEMBED_CACHE_PATH=/opt/fastembed

# curl/zstd for the Ollama installer; libgl1/libglib2.0-0 for OpenCV (used by the OCR engine)
RUN apt-get update && apt-get install -y --no-install-recommends curl ca-certificates zstd libgl1 libglib2.0-0 \
    && rm -rf /var/lib/apt/lists/*

# Ollama + the judge model, baked into the image so a cold start needs no download
RUN if [ "$WITH_OLLAMA" = "1" ]; then \
      curl -fsSL https://ollama.com/install.sh | sh && \
      (ollama serve > /tmp/ollama-build.log 2>&1 &) && \
      for i in $(seq 1 60); do curl -sf http://127.0.0.1:11434/api/version > /dev/null && break; sleep 1; done && \
      ollama pull "$JUDGE_MODEL" && chmod -R a+rX /opt/ollama; \
    fi

WORKDIR /app
COPY backend /app/backend
COPY deploy/start.sh /app/deploy/start.sh
RUN pip install -e /app/backend \
    && python -c "from fastembed import TextEmbedding; TextEmbedding('BAAI/bge-small-en-v1.5')" \
    && python -c "from rapidocr_onnxruntime import RapidOCR; RapidOCR()" \
    && sed -i 's/\r$//' /app/deploy/start.sh && chmod +x /app/deploy/start.sh \
    && useradd -m -u 1000 user \
    && mkdir -p /tmp/runs \
    && chown -R 1000:1000 /app /tmp/runs /opt/fastembed /home/user

USER 1000

# Defaults: hosted agent (OpenAI) + local judge. Override any of them with -e or the platform's variables.
# Secrets (OPENAI_API_KEY, API_KEY) are NOT baked in: set them on the platform.
ENV LLM_PROVIDER=openai \
    AGENT_MODEL=gpt-4o-mini \
    JUDGE_PROVIDER=ollama \
    JUDGE_MODEL=${JUDGE_MODEL} \
    OLLAMA_BASE_URL=http://127.0.0.1:11434 \
    RUNS_DIR=/tmp/runs \
    BUDGET_MAX_LLM_CALLS=450 \
    BUDGET_MAX_TOKENS=500000 \
    BUDGET_MAX_SECONDS=3600 \
    EVAL_TARGET_CASES=20 \
    FORGE_MAX_ITERATIONS=2 \
    PORT=7860

EXPOSE 7860
CMD ["/app/deploy/start.sh"]
