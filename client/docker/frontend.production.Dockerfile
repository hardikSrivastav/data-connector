FROM node:18-alpine
WORKDIR /app

# Install deps, copy source, build
COPY package*.json ./
RUN npm ci

COPY . .
RUN npm run build

# Production run
ENV NODE_ENV=production
EXPOSE 3000
CMD ["npm", "start"]
