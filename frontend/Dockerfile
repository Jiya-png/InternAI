# InternAI frontend: static build served by nginx, /api proxied to the backend service.
#   (used by docker-compose; build context = repo root)
FROM node:20-alpine AS build
WORKDIR /web
COPY frontend/package*.json ./
RUN npm install
COPY frontend/ .
RUN npm run build

FROM nginx:1.27-alpine
COPY frontend/nginx.conf /etc/nginx/conf.d/default.conf
COPY --from=build /web/dist /usr/share/nginx/html
EXPOSE 80
