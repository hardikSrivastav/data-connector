# Database Initialization Scripts

This directory contains scripts to initialize the PostgreSQL database with schema and test data for the data connector.

## Scripts Overview

1. `01-schema.sql` - Creates the base schema with tables for users, products, orders, etc.
2. `02-sample-data.sql` - Inserts a small set of sample data for basic testing
3. `03-generate-large-data.sql` - Generates large virtual datasets without consuming much storage
4. `test-large-data.sql` - Contains example queries to test and validate the large data generation

## Large Data Generation Approach

The large data generation script (`03-generate-large-data.sql`) uses a clever approach to simulate large datasets without consuming significant disk space:

1. **Virtual Views**: Creates views that generate data on-the-fly using cross joins and calculations
2. **Materialized Sample Views**: Creates small materialized views for real data samples
3. **Helper Functions**: Provides functions to sample from the large virtual datasets

This approach gives you:
- Virtual tables with 100k+ users, 10k+ products, 500k+ orders, and millions of order items
- Minimal disk space usage (only a small helper table and materialized samples)
- Realistic query performance testing with complex joins and aggregations
- The ability to test the LLM's handling of large datasets and query optimization

## How to Use

### 1. Initialize the database with base schema and sample data

```bash
psql -U postgres -d your_database -f 01-schema.sql
psql -U postgres -d your_database -f 02-sample-data.sql
```

### 2. Generate the large virtual datasets

```bash
psql -U postgres -d your_database -f 03-generate-large-data.sql
```

### 3. Test the large data generation

```bash
psql -U postgres -d your_database -f test-large-data.sql
```

## Using in Your Application

When developing or testing your application, you can query either:

1. **Real Tables**: `users`, `products`, `orders`, `order_items` - Small set of real data
2. **Large Virtual Views**: `large_users_view`, `large_products_view`, etc. - Large virtual datasets
3. **Materialized Samples**: `sample_users`, `sample_products`, etc. - Medium-sized real data

### Example Queries

To count virtual rows:
```sql
SELECT COUNT(*) FROM large_users_view;
```

To get top customers from virtual data:
```sql
SELECT 
    u.id, u.username, SUM(o.total_amount) AS total_spent
FROM 
    large_users_view u
JOIN 
    large_orders_view o ON u.id = o.user_id
GROUP BY 
    u.id, u.username
ORDER BY 
    total_spent DESC
LIMIT 10;
```

## Performance Considerations

- **Virtual Views**: These generate data on-the-fly and may be slower for complex queries
- **Materialized Views**: These contain real data and provide better performance
- The `RANDOM()` function in views makes results non-deterministic

For production performance testing, consider creating larger materialized views or using real production data.

## Refreshing Materialized Views

To refresh the materialized sample views with new random data:

```sql
REFRESH MATERIALIZED VIEW sample_users;
REFRESH MATERIALIZED VIEW sample_products;
REFRESH MATERIALIZED VIEW sample_orders;
REFRESH MATERIALIZED VIEW sample_order_items;
``` 