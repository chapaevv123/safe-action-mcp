FROM python:3.12-slim
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 SAFE_ACTION_HOST=0.0.0.0 SAFE_ACTION_DB=/tmp/safe-action.db
WORKDIR /app
COPY pyproject.toml README.md LICENSE ./
COPY safe_action_mcp ./safe_action_mcp
COPY client ./client
RUN pip install --no-cache-dir .
EXPOSE 10000
CMD ["python", "-m", "safe_action_mcp.app"]
