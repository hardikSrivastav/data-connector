FROM node:18-alpine AS builder

WORKDIR /app

# Copy package.json files
COPY package*.json ./

# Install dependencies
RUN npm ci

# Copy all project files
COPY . .

# Debug: Check if next.config.ts exists
RUN ls -la && echo "Current directory contents"

# Make sure TypeScript is installed
RUN npm install typescript @types/node --save-dev

# Explicitly transpile next.config.ts to next.config.js
RUN echo "Transpiling next.config.ts..." && \
    npx tsc next.config.ts --outDir ./ --module commonjs --moduleResolution node --esModuleInterop true || \
    echo "module.exports = $(cat next.config.ts | sed 's/export default//' | sed 's/: NextConfig//' | grep -v 'import');" > next.config.js

# Verify next.config.js exists
RUN cat next.config.js && echo "next.config.js contents shown above"

# Build with verbose output to see any errors
RUN echo "Starting build..." && \
    npm run build && \
    echo "Build completed successfully"

# Debug: Verify .next directory exists and show contents
RUN ls -la .next || echo "ERROR: .next directory was not created!"

# Single-stage build - skip the runner stage to avoid copy issues
WORKDIR /app
ENV NODE_ENV=production

# Expose the port
EXPOSE 3000

# Run the production server
CMD ["npm", "start"]