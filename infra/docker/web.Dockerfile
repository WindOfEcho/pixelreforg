FROM node:24-slim AS build

WORKDIR /app/apps/web

COPY apps/web/package.json apps/web/package-lock.json ./
RUN npm ci

COPY apps/web ./
RUN npm run build

FROM node:24-slim

ENV NODE_ENV=production \
    HOST=0.0.0.0 \
    PORT=3000

WORKDIR /app/apps/web

COPY apps/web/package.json apps/web/package-lock.json ./
RUN npm ci --omit=dev

COPY --from=build /app/apps/web/build ./build

COPY --from=build /app/apps/web/package.json ./package.json

EXPOSE 3000

CMD ["node", "build"]
