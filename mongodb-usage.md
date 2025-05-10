# MongoDB Adapter Usage Guide

This guide explains how to use the MongoDB adapter with the MongoDB service we've set up in our Docker environment.

## MongoDB Connection Information

- **Host**: localhost 
- **Port**: 27000 (mapped to MongoDB's standard port 27017 inside the container)
- **Database**: dataconnector_mongo
- **Username**: dataconnector
- **Password**: dataconnector
- **Connection URI**: `mongodb://dataconnector:dataconnector@localhost:27000/dataconnector_mongo`

## Test Connection

Use the `test_mongo.py` script to test the connection to MongoDB:

```bash
# Test the connection to MongoDB
python server/agent/cmd/test_mongo.py test-connection \
  --uri "mongodb://dataconnector:dataconnector@localhost:27000/dataconnector_mongo" \
  --db "dataconnector_mongo"
```

## Introspect Schema

Examine the MongoDB collections and document structure:

```bash
# Introspect the MongoDB schema
python server/agent/cmd/test_mongo.py introspect-schema \
  --uri "mongodb://dataconnector:dataconnector@localhost:27000/dataconnector_mongo" \
  --db "dataconnector_mongo"
```

## Test Natural Language Queries

Try generating MongoDB queries from natural language:

```bash
# Generate a query to find customers in the manufacturing industry
python server/agent/cmd/test_mongo.py test-query \
  --uri "mongodb://dataconnector:dataconnector@localhost:27000/dataconnector_mongo" \
  --db "dataconnector_mongo" \
  --collection "customers" \
  "Find all customers in the manufacturing industry"

# Generate a query to find the top 3 most expensive products
python server/agent/cmd/test_mongo.py test-query \
  --uri "mongodb://dataconnector:dataconnector@localhost:27000/dataconnector_mongo" \
  --db "dataconnector_mongo" \
  --collection "products" \
  "What are the top 3 most expensive products?"

# Find orders with a total amount greater than $3000
python server/agent/cmd/test_mongo.py test-query \
  --uri "mongodb://dataconnector:dataconnector@localhost:27000/dataconnector_mongo" \
  --db "dataconnector_mongo" \
  --collection "orders" \
  "Show me all orders with a total amount greater than $3000"

# Find employees in the Sales department with a salary above $75000
python server/agent/cmd/test_mongo.py test-query \
  --uri "mongodb://dataconnector:dataconnector@localhost:27000/dataconnector_mongo" \
  --db "dataconnector_mongo" \
  --collection "employees" \
  "List all employees in the Sales department with a salary above $75000"
```

## Test Using Orchestrator

Test the orchestrator with MongoDB:

```bash
# Use the adapter tester with MongoDB
python server/agent/cmd/test_adapter.py test-query \
  --uri "mongodb://dataconnector:dataconnector@localhost:27000/dataconnector_mongo?authSource=dataconnector_mongo" \
  "What are the top 5 customers by total order amount?" \
  --execute
```

## Database Collections

The MongoDB database includes the following collections:

1. **customers** - Company information with fields like:
   - customerId, name, email, phone, address, industry, active, createdAt, salesRep

2. **orders** - Order information with fields like:
   - orderId, customerId, items, totalAmount, status, orderDate, shipDate, paymentMethod

3. **employees** - Employee information with fields like:
   - employeeId, name, email, department, title, hireDate, salary, manager, active

4. **products** - Product information with fields like:
   - productId, name, category, price, inStock, specifications, supplier

## Using with Environment Variables

You can set up environment variables in your `.env` file to use MongoDB by default:

```
DB_URI=mongodb://dataconnector:dataconnector@localhost:27000/dataconnector_mongo?authSource=dataconnector_mongo
DB_TYPE=mongodb
MONGODB_DB_NAME=dataconnector_mongo
``` 