FROM node:20-alpine AS frontend-builder

WORKDIR /app/frontend

COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci

COPY frontend ./
RUN npm run build

FROM python:3.11-slim

WORKDIR /app

COPY pyproject.toml README.md requirements.txt ./
COPY shipsim ./shipsim
COPY scenarios ./scenarios
COPY --from=frontend-builder /app/shipsim/web ./shipsim/web

RUN pip install --no-cache-dir --upgrade pip && pip install --no-cache-dir .

EXPOSE 8000

CMD ["shipsim", "serve", "--host", "0.0.0.0", "--port", "8000"]
