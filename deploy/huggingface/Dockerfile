# Hugging Face Space Dockerfile: upload this file and README.md (same folder) to a new Docker Space.
# It clones the public GitHub repo and builds the same image as the repo's root Dockerfile.
FROM python:3.11-slim-bookworm

ARG REPO=https://github.com/AyushSingh2024/ForgeAI.git
ARG REF=main
ARG WITH_OLLAMA=1
ARG JUDGE_MODEL=llama3.2:3b

ENV PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    HOME=/home/user \
    OLLAMA_MODELS=/opt/ollama/models \
    OLLAMA_NOPRUNE=1 \
    FASTEMBED_CACHE_PATH=/opt/fastembed

RUN apt-get update && apt-get install -y --no-install-recommends git curl ca-certificates zstd libgl1 libglib2.0-0 \
    && rm -rf /var/lib/apt/lists/*

RUN if [ "$WITH_OLLAMA" = "1" ]; then \
      curl -fsSL https://ollama.com/install.sh | sh && \
      (ollama serve > /tmp/ollama-build.log 2>&1 &) && \
      for i in $(seq 1 60); do curl -sf http://127.0.0.1:11434/api/version > /dev/null && break; sleep 1; done && \
      ollama pull "$JUDGE_MODEL" && chmod -R a+rX /opt/ollama; \
    fi

RUN git clone --depth 1 --branch "$REF" "$REPO" /app \
    && pip install -e /app/backend \
    && python -c "from fastembed import TextEmbedding; TextEmbedding('BAAI/bge-small-en-v1.5')" \
    && python -c "from rapidocr_onnxruntime import RapidOCR; RapidOCR()" \
    && sed -i 's/\r$//' /app/deploy/start.sh && chmod +x /app/deploy/start.sh \
    && useradd -m -u 1000 user \
    && mkdir -p /tmp/runs \
    && chown -R 1000:1000 /app /tmp/runs /opt/fastembed /home/user

USER 1000
WORKDIR /app

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
