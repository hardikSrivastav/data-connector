-- Test queries for large data views

-- Count the number of rows in each view
SELECT 'Users (virtual)' AS table_name, COUNT(*) AS row_count FROM large_users_view;
SELECT 'Products (virtual)' AS table_name, COUNT(*) AS row_count FROM large_products_view;
SELECT 'Orders (virtual)' AS table_name, COUNT(*) AS row_count FROM large_orders_view;
SELECT 'Order Items (virtual)' AS table_name, COUNT(*) AS row_count FROM large_order_items_view LIMIT 10;

-- Count the number of rows in materialized views
SELECT 'Sample Users' AS table_name, COUNT(*) AS row_count FROM sample_users;
SELECT 'Sample Products' AS table_name, COUNT(*) AS row_count FROM sample_products;
SELECT 'Sample Orders' AS table_name, COUNT(*) AS row_count FROM sample_orders;
SELECT 'Sample Order Items' AS table_name, COUNT(*) AS row_count FROM sample_order_items;

-- Show sample data from large virtual views
SELECT 'Sample from large_users_view' AS data_source;
SELECT * FROM large_users_view LIMIT 5;

SELECT 'Sample from large_products_view' AS data_source;
SELECT * FROM large_products_view LIMIT 5;

SELECT 'Sample from large_orders_view' AS data_source;
SELECT * FROM large_orders_view LIMIT 5;

-- Example complex query - finding top 10 customers by order amount
SELECT 'Top 10 customers by order amount (virtual data)' AS query_description;
SELECT 
    u.id AS user_id,
    u.username,
    u.email,
    SUM(o.total_amount) AS total_spent,
    COUNT(o.id) AS order_count,
    AVG(o.total_amount) AS avg_order_value
FROM 
    large_users_view u
JOIN 
    large_orders_view o ON u.id = o.user_id
WHERE 
    o.status = 'completed'
GROUP BY 
    u.id, u.username, u.email
ORDER BY 
    total_spent DESC
LIMIT 10;

-- Example complex query - finding top selling products (using materialized views)
SELECT 'Top selling products (sample data)' AS query_description;
SELECT 
    p.id AS product_id,
    p.name AS product_name,
    p.price,
    SUM(oi.quantity) AS total_quantity_sold,
    SUM(oi.quantity * oi.unit_price) AS total_revenue
FROM 
    sample_products p
JOIN 
    sample_order_items oi ON p.id = oi.product_id
JOIN 
    sample_orders o ON oi.order_id = o.id
WHERE 
    o.status = 'completed'
GROUP BY 
    p.id, p.name, p.price
ORDER BY 
    total_revenue DESC
LIMIT 10;

-- Example time-series analysis
SELECT 'Monthly sales over time (virtual data)' AS query_description;
SELECT 
    DATE_TRUNC('month', o.order_date) AS month,
    COUNT(o.id) AS order_count,
    SUM(o.total_amount) AS total_sales
FROM 
    large_orders_view o
WHERE 
    o.status = 'completed'
GROUP BY 
    DATE_TRUNC('month', o.order_date)
ORDER BY 
    month
LIMIT 24;

-- Example query for testing with large results - a bad query that would return too many rows
-- This is to test LLM's ability to suggest optimizations
SELECT 'Example of a suboptimal query (returns large result set)' AS query_description;
EXPLAIN ANALYZE
SELECT * FROM large_users_view u
JOIN large_orders_view o ON u.id = o.user_id
LIMIT 100; 