# frontend/Dockerfile

# 1. Install dependencies
FROM node:26-alpine AS deps
WORKDIR /app
COPY package.json package-lock.json ./
RUN npm ci --legacy-peer-deps

COPY package.json package-lock.json ./
RUN npm install -g npm@12.2.3 && npm ci --legacy-peer-deps

# 2. Build
FROM node:26-alpine AS builder
WORKDIR /app
COPY --from=deps /app/node_modules ./node_modules
COPY . .

# CRITICAL FIX: Set to production URL so Next.js bakes the correct API path
ENV NEXT_PUBLIC_API_URL=https://my-leads.app

RUN npm run build

# 3. Production Image
FROM node:26-alpine AS runner
WORKDIR /app

ENV NODE_ENV production

RUN addgroup --system --gid 1001 nodejs
RUN adduser --system --uid 1001 nextjs

COPY --from=builder /app/public ./public

# Copy built files
COPY --from=builder --chown=nextjs:nodejs /app/.next/standalone ./
COPY --from=builder --chown=nextjs:nodejs /app/.next/static ./.next/static

USER nextjs

EXPOSE 3000
ENV PORT 3000

ENV HOSTNAME "0.0.0.0"

CMD ["node", "server.js"]