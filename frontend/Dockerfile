FROM node:20-slim AS builder

WORKDIR /app

# Copy package files and .env
COPY package*.json ./
RUN npm install

COPY . .

RUN npm run build

# Add both build-time variables
ARG VITE_API_BASE
ARG VITE_GOOGLE_MAPS_API_KEY

ENV VITE_API_BASE=$VITE_API_BASE
ENV VITE_GOOGLE_MAPS_API_KEY=$VITE_GOOGLE_MAPS_API_KEY

RUN npm run build

# Serve with lightweight server
FROM node:20-alpine
WORKDIR /app
RUN npm install -g serve
COPY --from=builder /app/dist /app/dist
EXPOSE 80
CMD ["serve", "-s", "dist", "-l", "80"]
