# syntax=docker/dockerfile:1.7
ARG NODE_IMAGE=node:24.8.0-alpine3.22@sha256:3e843c608bb5232f39ecb2b25e41214b958b0795914707374c8acc28487dea17
ARG NGINX_IMAGE=nginxinc/nginx-unprivileged:1.31.5-alpine-slim@sha256:7d289d4f8935051d213bc3ecee3b4fc2d52f97ea5a954273e031054b633e7934

# hadolint ignore=DL3006
FROM ${NODE_IMAGE} AS build
WORKDIR /build
COPY apps/console/package.json apps/console/package-lock.json ./
RUN npm ci --ignore-scripts
COPY docs/dusk-hero-banner.svg /docs/dusk-hero-banner.svg
COPY docs/dusk-logo.svg /docs/dusk-logo.svg
COPY apps/console/ ./
RUN npm run build && npm prune --omit=dev

# hadolint ignore=DL3006
FROM ${NGINX_IMAGE} AS runtime
USER root
COPY apps/console/nginx.conf /etc/nginx/conf.d/default.conf
COPY --from=build --chown=101:101 /build/dist /usr/share/nginx/html
RUN chmod -R a-w /usr/share/nginx/html /etc/nginx/conf.d/default.conf
USER 101:101
EXPOSE 8080
HEALTHCHECK --interval=10s --timeout=3s --start-period=5s --retries=3 CMD ["wget", "-q", "-O", "/dev/null", "http://127.0.0.1:8080/healthz"]
