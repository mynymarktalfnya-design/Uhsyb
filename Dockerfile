FROM python:3.11-slim

WORKDIR /app
ENV PYTHONUNBUFFERED=1

COPY requirements.deploy.txt ./requirements.deploy.txt
RUN pip install --no-cache-dir -r requirements.deploy.txt

COPY market-backend ./market-backend
COPY web ./web
COPY deploy_server.py ./deploy_server.py

ENV NODE_ENV=production
CMD ["sh", "-c", "exec uvicorn deploy_server:app --host 0.0.0.0 --port ${PORT:-8080}"]
