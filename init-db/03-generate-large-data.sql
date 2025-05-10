-- Generate large synthetic data for testing without consuming much disk space
-- This approach uses views and functions to emulate a large dataset

-- Create a sequence helper table for generating rows
CREATE TABLE sequence_helper (id SERIAL PRIMARY KEY);

-- Add 1000 rows to sequence helper
DO $$
BEGIN
    FOR i IN 1..1000 LOOP
        INSERT INTO sequence_helper (id) VALUES (DEFAULT);
    END LOOP;
END $$;

-- Create a view that generates a lot of virtual users (100k+)
CREATE OR REPLACE VIEW large_users_view AS
SELECT 
    (s1.id * 1000 + s2.id) AS id,
    'user_' || (s1.id * 1000 + s2.id)::TEXT AS username,
    'user_' || (s1.id * 1000 + s2.id)::TEXT || '@example.com' AS email,
    'First' || (s1.id * 1000 + s2.id)::TEXT AS first_name,
    'Last' || (s1.id * 1000 + s2.id)::TEXT AS last_name,
    NOW() - (RANDOM() * INTERVAL '1000 days') AS created_at,
    NOW() - (RANDOM() * INTERVAL '500 days') AS updated_at
FROM 
    sequence_helper s1
CROSS JOIN 
    sequence_helper s2
WHERE 
    (s1.id * 1000 + s2.id) <= 100000;

-- Create a view that generates synthetic products (10k+)
CREATE OR REPLACE VIEW large_products_view AS
SELECT 
    s.id AS id,
    'Product ' || s.id::TEXT AS name,
    'Description for product ' || s.id::TEXT AS description,
    (RANDOM() * 1000)::NUMERIC(10,2) AS price,
    'SKU-' || LPAD(s.id::TEXT, 6, '0') AS sku,
    CASE WHEN RANDOM() > 0.1 THEN TRUE ELSE FALSE END AS in_stock,
    NOW() - (RANDOM() * INTERVAL '500 days') AS created_at,
    NOW() - (RANDOM() * INTERVAL '100 days') AS updated_at
FROM 
    (SELECT id FROM sequence_helper WHERE id <= 10000) s;

-- Create a view that generates 500k+ synthetic orders
CREATE OR REPLACE VIEW large_orders_view AS
SELECT 
    (s1.id * 1000 + s2.id) AS id,
    1 + (RANDOM() * 100000)::INTEGER % 100000 AS user_id,
    CASE 
        WHEN RANDOM() < 0.7 THEN 'completed'
        WHEN RANDOM() < 0.9 THEN 'processing' 
        ELSE 'pending' 
    END AS status,
    (RANDOM() * 2000)::NUMERIC(12,2) AS total_amount,
    NOW() - (RANDOM() * INTERVAL '1000 days') AS order_date,
    (100000 + (RANDOM() * 900000)::INTEGER)::TEXT || ' Main St, Anytown, AN ' || 
    LPAD((RANDOM() * 99999)::INTEGER::TEXT, 5, '0') AS shipping_address,
    NOW() - (RANDOM() * INTERVAL '1000 days') AS created_at,
    NOW() - (RANDOM() * INTERVAL '500 days') AS updated_at
FROM 
    (SELECT id FROM sequence_helper WHERE id <= 500) s1
CROSS JOIN 
    (SELECT id FROM sequence_helper WHERE id <= 1000) s2;

-- Create a view that generates millions of order items
CREATE OR REPLACE VIEW large_order_items_view AS
SELECT 
    (o.id * 10 + i) AS id,
    o.id AS order_id,
    1 + (RANDOM() * 10000)::INTEGER % 10000 AS product_id,
    1 + (RANDOM() * 5)::INTEGER AS quantity,
    (RANDOM() * 500)::NUMERIC(10,2) AS unit_price,
    o.created_at AS created_at
FROM 
    (SELECT id, created_at FROM large_orders_view LIMIT 500000) o
CROSS JOIN 
    GENERATE_SERIES(1, 5) AS i;

-- Function to get a sample of users
CREATE OR REPLACE FUNCTION sample_large_users(sample_size INTEGER)
RETURNS TABLE (
    id INTEGER,
    username TEXT,
    email TEXT,
    first_name TEXT,
    last_name TEXT,
    created_at TIMESTAMP WITH TIME ZONE,
    updated_at TIMESTAMP WITH TIME ZONE
) AS $$
BEGIN
    RETURN QUERY
    SELECT * FROM large_users_view
    ORDER BY RANDOM()
    LIMIT sample_size;
END;
$$ LANGUAGE plpgsql;

-- Function to get a sample of orders
CREATE OR REPLACE FUNCTION sample_large_orders(sample_size INTEGER)
RETURNS TABLE (
    id INTEGER,
    user_id INTEGER,
    status TEXT,
    total_amount NUMERIC,
    order_date TIMESTAMP WITH TIME ZONE,
    shipping_address TEXT,
    created_at TIMESTAMP WITH TIME ZONE,
    updated_at TIMESTAMP WITH TIME ZONE
) AS $$
BEGIN
    RETURN QUERY
    SELECT * FROM large_orders_view
    ORDER BY RANDOM()
    LIMIT sample_size;
END;
$$ LANGUAGE plpgsql;

-- Create materialized views with a small sample if you need real data
-- These only take up the space needed for the samples

-- Create a small materialized view of users for testing (1000 rows)
CREATE MATERIALIZED VIEW sample_users AS
SELECT * FROM sample_large_users(1000);

-- Create a small materialized view of products for testing (100 rows)
CREATE MATERIALIZED VIEW sample_products AS
SELECT * FROM large_products_view
ORDER BY RANDOM()
LIMIT 100;

-- Create a small materialized view of orders for testing (1000 rows)
CREATE MATERIALIZED VIEW sample_orders AS
SELECT * FROM sample_large_orders(1000);

-- Create a small materialized view of order items for testing
CREATE MATERIALIZED VIEW sample_order_items AS
SELECT 
    (o.id * 10 + i) AS id,
    o.id AS order_id,
    1 + (RANDOM() * 100)::INTEGER % 100 AS product_id,
    1 + (RANDOM() * 5)::INTEGER AS quantity,
    (RANDOM() * 500)::NUMERIC(10,2) AS unit_price,
    o.created_at AS created_at
FROM 
    sample_orders o
CROSS JOIN 
    GENERATE_SERIES(1, CEIL(RANDOM() * 5)::INTEGER) AS i;

-- Create indexes on the materialized views
CREATE INDEX ON sample_users (id);
CREATE INDEX ON sample_products (id);
CREATE INDEX ON sample_orders (id);
CREATE INDEX ON sample_orders (user_id);
CREATE INDEX ON sample_order_items (order_id);
CREATE INDEX ON sample_order_items (product_id);

-- Example usage:
-- To query the large virtual datasets (these don't use storage):
-- SELECT COUNT(*) FROM large_users_view;
-- SELECT COUNT(*) FROM large_orders_view;

-- To query the materialized sample (these use minimal storage):
-- SELECT COUNT(*) FROM sample_users;
-- SELECT COUNT(*) FROM sample_orders;

-- Add a comment explaining how to use this approach
COMMENT ON VIEW large_users_view IS 
'Virtual view of 100k+ users. Does not consume storage space. For performance testing, sample using ORDER BY RANDOM() LIMIT X';

COMMENT ON MATERIALIZED VIEW sample_users IS
'Materialized sample of 1000 users for testing. Consumes minimal storage.'; 