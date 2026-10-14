FROM python:3.11-slim

WORKDIR /app
ENV PIP_NO_CACHE_DIR=1 HF_HOME=/app/hf-cache

# CPU-only torch first (skips ~2 GB of CUDA libraries), then llm-guard on its own, so its
# exact pins resolve against nothing else. Both layers are cached after the first build.
RUN pip install --upgrade pip \
    && pip install torch --index-url https://download.pytorch.org/whl/cpu
COPY requirements.txt .
RUN pip install -r requirements.txt

# Bake the classifier weights into the image so the first scan isn't a model download.
RUN python -c "from llm_guard.input_scanners import PromptInjection; PromptInjection()"

COPY server.py .
EXPOSE 8000
CMD ["python", "server.py"]
