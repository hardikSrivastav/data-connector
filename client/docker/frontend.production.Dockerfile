FROM node:18-alpine AS builder

WORKDIR /app

# Copy package.json files
COPY package*.json ./

# Install dependencies
RUN npm ci

# Copy all project files
COPY . .

# Build the application - this will also transpile next.config.ts to next.config.js
RUN npm run build

# Transpile the next.config.ts file explicitly to ensure it exists
RUN npx tsc next.config.ts --outDir ./ --module commonjs --moduleResolution node || echo "Transpilation attempt complete"

# Create next.config.js if it wasn't created by the transpilation
RUN if [ ! -f next.config.js ]; then echo "module.exports = $(cat next.config.ts | sed 's/export default//' | sed 's/: NextConfig//');" > next.config.js; fi

# Production image
FROM node:18-alpine AS runner
WORKDIR /app

ENV NODE_ENV=production

# Copy the transpiled next.config.js file
COPY --from=builder /app/next.config.js ./

# Copy other necessary files
COPY --from=builder /app/public ./public
COPY --from=builder /app/package.json ./package.json

# Copy the build output
COPY --from=builder /app/.next ./.next
COPY --from=builder /app/node_modules ./node_modules

# Ensure the .next directory exists with a complete build
RUN ls -la .next || echo "Build directory not copied correctly"

# Expose the port
EXPOSE 3000

# Run the production server
CMD ["npm", "start"]