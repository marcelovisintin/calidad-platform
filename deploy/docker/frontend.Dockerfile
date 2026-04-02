FROM node:24-alpine AS build

WORKDIR /app/frontend

COPY frontend/package*.json ./
RUN npm ci

COPY frontend ./

ARG VITE_API_BASE_URL=/api/v1
ARG VITE_CATALOG_BOOTSTRAP_URL=/catalog.bootstrap.json
ENV VITE_API_BASE_URL=${VITE_API_BASE_URL}
ENV VITE_CATALOG_BOOTSTRAP_URL=${VITE_CATALOG_BOOTSTRAP_URL}

RUN npm run build

FROM nginx:1.27-alpine

RUN apk add --no-cache openssl

COPY deploy/nginx/50-generate-self-signed-cert.sh /docker-entrypoint.d/50-generate-self-signed-cert.sh
RUN chmod +x /docker-entrypoint.d/50-generate-self-signed-cert.sh

COPY deploy/nginx/calidad.conf /etc/nginx/conf.d/default.conf
COPY --from=build /app/frontend/dist /usr/share/nginx/html
