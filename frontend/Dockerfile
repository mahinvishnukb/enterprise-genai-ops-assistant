# Two-stage build: compile the static React bundle with Node, then serve
# the compiled output with a tiny nginx image (no Node runtime in the final
# image — ~25MB instead of ~1GB, and nginx is what you'd actually run in
# prod for a static SPA bundle).
FROM node:20-slim AS build
WORKDIR /app
COPY package.json ./
RUN npm install
COPY . .
RUN npm run build

FROM nginx:alpine
COPY --from=build /app/dist /usr/share/nginx/html
COPY nginx.conf /etc/nginx/conf.d/default.conf
EXPOSE 80
