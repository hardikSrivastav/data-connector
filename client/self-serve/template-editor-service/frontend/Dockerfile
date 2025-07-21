FROM node:18-alpine

WORKDIR /app

# Copy package files
COPY package*.json ./

# Install dependencies
RUN npm install

# Copy source code
COPY . .

# Expose the development server port
EXPOSE 8500

# Start the development server
CMD ["npm", "run", "dev", "--", "--host", "0.0.0.0", "--port", "8500"]
