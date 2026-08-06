FROM node:24-bookworm-slim
WORKDIR /app
ENV npm_config_audit=false \
    npm_config_fund=false \
    npm_config_update_notifier=false
COPY apps/web/package*.json ./
RUN npm install --include=dev --no-audit --no-fund
