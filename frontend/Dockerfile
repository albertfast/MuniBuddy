# Build aşaması
FROM node:20 AS builder

WORKDIR /app
COPY package*.json ./
RUN npm install
COPY . .
RUN npm run build

# Serve için basit bir static server kullan (alternatif olarak nginx de olur)
FROM node:20-alpine

WORKDIR /app
RUN npm install -g serve
COPY --from=builder /app/dist /app/dist
EXPOSE 80

CMD ["serve", "-s", "dist", "-l", "80"]