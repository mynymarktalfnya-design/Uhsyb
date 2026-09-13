FROM node:22-slim AS frontend-builder
WORKDIR /app
COPY . .
RUN npm install -g corepack@latest \
    && corepack pnpm install --frozen-lockfile \
    && PORT=5173 BASE_PATH=/ corepack pnpm --filter @workspace/market-frontend run build

FROM python:3.11-slim AS runtime
WORKDIR /app
ENV PYTHONUNBUFFERED=1
COPY requirements.deploy.txt ./requirements.deploy.txt
RUN pip install --no-cache-dir -r requirements.deploy.txt
COPY market-backend ./market-backend
COPY --from=frontend-builder /app/artifacts/market-frontend/dist/public ./web
COPY deploy_server.py ./deploy_server.py
ENV NODE_ENV=production
CMD ["sh", "-c", "exec uvicorn deploy_server:app --host 0.0.0.0 --port ${PORT:-8080}"]
