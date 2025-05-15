FROM node:20-alpine

WORKDIR /app

# Copy package files
COPY landing_routes/package*.json ./

# Install dependencies
RUN npm install

# Copy source code
COPY landing_routes/src ./src

# Expose port
EXPOSE 3001

# Set environment variables
ENV NODE_ENV=production

# Start the app
CMD ["npm", "start"] 