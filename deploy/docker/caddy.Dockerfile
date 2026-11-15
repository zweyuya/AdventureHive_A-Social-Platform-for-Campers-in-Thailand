# Caddy with the built React frontend baked in.
# Stage 1 builds the React app (Vite); stage 2 is Caddy serving it, plus HTTPS and the proxy to Django.
FROM node:20-bookworm-slim AS frontend
WORKDIR /frontend
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci --no-audit --no-fund
COPY frontend/ ./
RUN npm run build

FROM caddy:2.8-alpine
COPY deploy/docker/Caddyfile /etc/caddy/Caddyfile
COPY --from=frontend /frontend/dist /srv/frontend
