FROM node:24-bookworm-slim
WORKDIR /app
COPY apps/web/package*.json ./
RUN npm install
