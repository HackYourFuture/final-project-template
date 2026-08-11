# Stage 1: install dependencies and build the Next.js app
FROM node:24-alpine AS builder
WORKDIR /app
COPY package*.json ./
RUN npm ci
COPY . .
RUN npm run build

# Stage 2: run the built app with Next's minimal standalone server
FROM node:24-alpine AS runner
WORKDIR /app
ENV NODE_ENV=production
ENV PORT=3000
# Next's standalone server binds to $HOSTNAME; without this it can pick up the
# container/host name instead of listening on all interfaces
ENV HOSTNAME=0.0.0.0
# Default BACKEND_API_URL for typical container networking; override at runtime if needed
ENV BACKEND_API_URL=http://backend:8080
USER node
COPY --from=builder --chown=node:node /app/.next/standalone ./
COPY --from=builder --chown=node:node /app/.next/static ./.next/static
COPY --from=builder --chown=node:node /app/public ./public
EXPOSE 3000
CMD ["node", "server.js"]
