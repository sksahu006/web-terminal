# Stage 1: Build the React/Vite app
FROM node:20-alpine AS builder
WORKDIR /app

# Copy only package files first (better layer caching)
COPY package.json package-lock.json ./
RUN npm ci --frozen-lockfile

# Copy source and build
COPY . .
RUN npm run build

# Stage 2: Serve with lightweight Nginx (no Node.js, no node_modules)
FROM nginx:alpine AS runner
COPY --from=builder /app/dist /usr/share/nginx/html
EXPOSE 80
CMD ["nginx", "-g", "daemon off;"]
