FROM python:3.12-slim-bookworm AS theme
WORKDIR /src
COPY theme /src/theme
COPY scripts /src/scripts
COPY web /src/web
COPY api /src/api
COPY worker /src/worker
COPY docs /src/docs
RUN python /src/scripts/generate_theme.py --root /src \
    && python /src/scripts/check_theme.py --root /src

FROM node:22-bookworm-slim AS build
WORKDIR /app
ENV NEXT_TELEMETRY_DISABLED=1 \
    API_INTERNAL_URL=http://api:8000
COPY web /app
COPY --from=theme /src/web/app/tokens.css /app/app/tokens.css
COPY assets/brand /app/public/brand
COPY assets/fonts /app/public/fonts
COPY assets/team /app/public/team
RUN npm install && npm run build

FROM node:22-bookworm-slim
WORKDIR /app
ENV NODE_ENV=production \
    NEXT_TELEMETRY_DISABLED=1 \
    PORT=3000 \
    HOSTNAME=0.0.0.0
COPY --from=build /app/public ./public
COPY --from=build /app/.next/standalone ./
COPY --from=build /app/.next/static ./.next/static
EXPOSE 3000
CMD ["node", "server.js"]
