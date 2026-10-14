FROM python:3.11-slim

WORKDIR /app

# System deps. (The victim/guardrail agents call provider APIs directly via Pydantic AI —
# no Node / Claude Code CLI needed in the container.)
RUN apt-get update && apt-get install -y postgresql-client curl \
    && apt-get clean && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --upgrade pip && pip install --no-cache-dir -r requirements.txt

COPY . .

EXPOSE 5000
CMD ["python", "app.py"]
