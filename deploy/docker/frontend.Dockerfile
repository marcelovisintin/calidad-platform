FROM node:24-alpine AS build

ENV NODE_OPTIONS=--use-system-ca

WORKDIR /app/frontend

COPY frontend/package*.json ./
RUN --mount=type=secret,id=npm_ca,required=false \
    if [ -s /run/secrets/npm_ca ]; then \
        export NODE_EXTRA_CA_CERTS=/run/secrets/npm_ca; \
    fi; \
    npm ci

COPY frontend ./

ARG VITE_API_BASE_URL=/api/v1
ARG VITE_CATALOG_BOOTSTRAP_URL=/catalog.bootstrap.json
ARG APP_GIT_COMMIT=no-disponible
ARG APP_GIT_SHORT_COMMIT=no-disponible
ARG APP_GIT_BRANCH=no-disponible
ARG APP_GIT_DIRTY=false
ARG APP_DEPLOYMENT_ENV=local
ARG APP_GIT_HISTORY_B64=
ENV VITE_API_BASE_URL=${VITE_API_BASE_URL}
ENV VITE_CATALOG_BOOTSTRAP_URL=${VITE_CATALOG_BOOTSTRAP_URL}
ENV APP_GIT_COMMIT=${APP_GIT_COMMIT}
ENV APP_GIT_SHORT_COMMIT=${APP_GIT_SHORT_COMMIT}
ENV APP_GIT_BRANCH=${APP_GIT_BRANCH}
ENV APP_GIT_DIRTY=${APP_GIT_DIRTY}
ENV APP_DEPLOYMENT_ENV=${APP_DEPLOYMENT_ENV}
ENV APP_GIT_HISTORY_B64=${APP_GIT_HISTORY_B64}

RUN npm run build

FROM nginx:1.27-alpine

RUN apk add --no-cache openssl

COPY deploy/nginx/50-generate-self-signed-cert.sh /docker-entrypoint.d/50-generate-self-signed-cert.sh
RUN chmod +x /docker-entrypoint.d/50-generate-self-signed-cert.sh

COPY deploy/nginx/calidad.conf /etc/nginx/conf.d/default.conf
COPY --from=build /app/frontend/dist /usr/share/nginx/html
