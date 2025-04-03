# Dockerfile (frontend)

FROM node:20 AS builder

WORKDIR /app

# Copy .env and package files
COPY package*.json ./

RUN npm install
COPY . .

# Set API base at build time
ARG VITE_API_BASE
ENV VITE_API_BASE=$VITE_API_BASE

RUN npm run build

# Serve with lightweight server
FROM node:20-alpine
WORKDIR /app
RUN npm install -g serve
COPY --from=builder /app/dist /app/dist
EXPOSE 80
CMD ["serve", "-s", "dist", "-l", "80"]
