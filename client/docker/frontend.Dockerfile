FROM node:18-alpine

WORKDIR /app

# Copy package.json files
COPY package*.json ./

# Install dependencies
RUN npm install

# Copy all project files
COPY . .

# Expose the port
EXPOSE 3000

# Run the development server
CMD ["npm", "run", "dev"] 