FROM node:22-alpine AS build
WORKDIR /app
COPY package.json ./
# No lockfile is committed yet; run `npm install` locally and commit package-lock.json, then switch to `npm ci`.
RUN npm install
COPY . .
RUN npm run build

FROM node:22-alpine
WORKDIR /app
ENV NODE_ENV=production
COPY --from=build /app/.next/standalone ./
COPY --from=build /app/.next/static ./.next/static
USER node
EXPOSE 3000
CMD ["node", "server.js"]
