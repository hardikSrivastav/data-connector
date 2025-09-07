FROM node:18-alpine
WORKDIR /app

# 1) Install deps
COPY package*.json ./
RUN npm ci

# 2) Copy source & build
COPY . .
RUN npm run build

# 3) Runtime config
ENV NODE_ENV=production
EXPOSE 3000

# next start will see a valid /app/.next directory
CMD ["npm", "start"]
