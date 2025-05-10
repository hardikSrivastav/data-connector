-- Insert sample users
INSERT INTO users (username, email, first_name, last_name) VALUES
    ('johndoe', 'john.doe@example.com', 'John', 'Doe'),
    ('janedoe', 'jane.doe@example.com', 'Jane', 'Doe'),
    ('bobsmith', 'bob.smith@example.com', 'Bob', 'Smith'),
    ('alicejones', 'alice.jones@example.com', 'Alice', 'Jones'),
    ('mikebrown', 'mike.brown@example.com', 'Mike', 'Brown');

-- Insert categories
INSERT INTO categories (name, description) VALUES
    ('Electronics', 'Electronic devices and accessories'),
    ('Clothing', 'Apparel and fashion items'),
    ('Home & Kitchen', 'Products for home and kitchen use'),
    ('Books', 'Books and reading materials'),
    ('Sports & Outdoors', 'Sports equipment and outdoor gear');

-- Insert products
INSERT INTO products (name, description, price, sku, in_stock) VALUES
    ('Smartphone XYZ', 'Latest smartphone with advanced features', 899.99, 'ELEC-001', true),
    ('Laptop Pro', 'High-performance laptop for professionals', 1299.99, 'ELEC-002', true),
    ('Wireless Headphones', 'Noise-cancelling wireless headphones', 199.99, 'ELEC-003', true),
    ('T-shirt Basic', 'Cotton basic t-shirt', 24.99, 'CLOTH-001', true),
    ('Jeans Classic', 'Classic blue jeans', 59.99, 'CLOTH-002', true),
    ('Coffee Maker', 'Automatic coffee maker with timer', 79.99, 'HOME-001', true),
    ('Blender Pro', 'Professional-grade blender', 129.99, 'HOME-002', false),
    ('Fiction Bestseller', 'Latest bestselling fiction novel', 19.99, 'BOOK-001', true),
    ('Cookbook', 'Recipes from around the world', 29.99, 'BOOK-002', true),
    ('Tennis Racket', 'Professional tennis racket', 89.99, 'SPORT-001', true);

-- Associate products with categories
INSERT INTO product_categories (product_id, category_id) VALUES
    (1, 1), -- Smartphone in Electronics
    (2, 1), -- Laptop in Electronics
    (3, 1), -- Headphones in Electronics
    (4, 2), -- T-shirt in Clothing
    (5, 2), -- Jeans in Clothing
    (6, 3), -- Coffee Maker in Home & Kitchen
    (7, 3), -- Blender in Home & Kitchen
    (8, 4), -- Fiction Book in Books
    (9, 4), -- Cookbook in Books
    (10, 5); -- Tennis Racket in Sports & Outdoors

-- Insert orders
INSERT INTO orders (user_id, status, total_amount, shipping_address) VALUES
    (1, 'completed', 1099.98, '123 Main St, Anytown, AN 12345'),
    (2, 'processing', 199.99, '456 Oak Ave, Somecity, SC 67890'),
    (3, 'completed', 109.98, '789 Pine Rd, Otherville, OV 54321'),
    (4, 'pending', 149.98, '321 Cedar Ln, Newtown, NT 13579'),
    (5, 'completed', 979.98, '654 Maple Dr, Oldcity, OC 97531');

-- Insert order items
INSERT INTO order_items (order_id, product_id, quantity, unit_price) VALUES
    (1, 2, 1, 1099.99), -- Laptop for John
    (2, 3, 1, 199.99),  -- Headphones for Jane
    (3, 6, 1, 79.99),   -- Coffee Maker for Bob
    (3, 9, 1, 29.99),   -- Cookbook for Bob
    (4, 4, 2, 24.99),   -- 2 T-shirts for Alice
    (4, 8, 1, 19.99),   -- Fiction Book for Alice
    (5, 1, 1, 899.99),  -- Smartphone for Mike
    (5, 10, 1, 89.99);  -- Tennis Racket for Mike 