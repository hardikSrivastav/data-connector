// MongoDB script to generate large virtual collections without consuming much storage
// This script creates a small base collection and uses aggregation with $function for virtual data generation

// Connect to the MongoDB instance
db = db.getSiblingDB('dataconnector_mongo');

// Create a sequence helper collection with 1000 documents
db.sequence_helper.drop();
db.createCollection("sequence_helper");

// Create a simple function to insert 1000 sequence documents
function insertSequenceDocuments() {
  const docs = [];
  for (let i = 1; i <= 1000; i++) {
    docs.push({ id: i });
  }
  db.sequence_helper.insertMany(docs);
}

// Execute the sequence insertion
insertSequenceDocuments();
print("Created sequence_helper collection with 1000 documents");

// Create indexes for better performance
db.sequence_helper.createIndex({ id: 1 });

// ----------------- SAMPLE COLLECTIONS -----------------

// Create sample collections for materialized views
db.sample_users.drop();
db.createCollection("sample_users");

db.sample_products.drop();
db.createCollection("sample_products");

db.sample_orders.drop();
db.createCollection("sample_orders");

// ----------------- GENERATE SAMPLE USERS -----------------

// Generate and insert 1000 sample users
const userDocs = [];
for (let i = 1; i <= 1000; i++) {
  userDocs.push({
    userId: i,
    username: `user_${i}`,
    email: `user_${i}@example.com`,
    firstName: `First${i}`,
    lastName: `Last${i}`,
    createdAt: new Date(Date.now() - Math.random() * 1000 * 86400 * 1000), // Random date within the last 1000 days
    profile: {
      address: `${Math.floor(Math.random() * 1000)} Main St, Anytown`,
      phone: `555-${Math.floor(Math.random() * 1000).toString().padStart(3, '0')}-${Math.floor(Math.random() * 10000).toString().padStart(4, '0')}`,
      preferences: {
        theme: Math.random() > 0.5 ? "light" : "dark",
        notifications: Math.random() > 0.3
      }
    },
    status: Math.random() > 0.1 ? "active" : "inactive"
  });
}

if (userDocs.length > 0) {
  db.sample_users.insertMany(userDocs);
  print(`Created sample_users collection with ${db.sample_users.count()} documents`);
}

// ----------------- GENERATE SAMPLE PRODUCTS -----------------

// Generate and insert 100 sample products
const productDocs = [];
for (let i = 1; i <= 100; i++) {
  productDocs.push({
    productId: i,
    name: `Product ${i}`,
    description: `Description for product ${i}`,
    price: Math.floor(Math.random() * 1000 * 100) / 100, // Random price up to $1000
    sku: `SKU-${i.toString().padStart(6, '0')}`,
    inStock: Math.random() > 0.1,
    category: ["Electronics", "Home Goods", "Office Supplies", "Clothing", "Food"][Math.floor(Math.random() * 5)],
    specifications: {
      weight: Math.floor(Math.random() * 100) / 10,
      dimensions: {
        length: Math.floor(Math.random() * 50),
        width: Math.floor(Math.random() * 30),
        height: Math.floor(Math.random() * 20)
      }
    },
    createdAt: new Date(Date.now() - Math.random() * 500 * 86400 * 1000) // Random date within the last 500 days
  });
}

if (productDocs.length > 0) {
  db.sample_products.insertMany(productDocs);
  print(`Created sample_products collection with ${db.sample_products.count()} documents`);
}

// ----------------- GENERATE SAMPLE ORDERS -----------------

// Generate and insert 1000 sample orders
const orderDocs = [];
for (let i = 1; i <= 1000; i++) {
  const userId = 1 + Math.floor(Math.random() * 1000);
  const itemCount = 1 + Math.floor(Math.random() * 5);
  const items = [];
  let totalAmount = 0;
  
  for (let j = 0; j < itemCount; j++) {
    const productId = 1 + Math.floor(Math.random() * 100);
    const quantity = 1 + Math.floor(Math.random() * 5);
    const price = Math.floor(Math.random() * 500 * 100) / 100;
    const itemTotal = quantity * price;
    totalAmount += itemTotal;
    
    items.push({
      productId: `P-${productId}`,
      name: `Product ${productId}`,
      quantity: quantity,
      price: price
    });
  }
  
  const orderDate = new Date(Date.now() - Math.random() * 1000 * 86400 * 1000);
  const shipDate = Math.random() > 0.2 ? new Date(orderDate.getTime() + Math.random() * 15 * 86400 * 1000) : null;
  
  orderDocs.push({
    orderId: `ORD-${i.toString().padStart(8, '0')}`,
    userId: userId,
    items: items,
    totalAmount: Math.round(totalAmount * 100) / 100,
    status: Math.random() < 0.7 ? "completed" : (Math.random() < 0.9 ? "processing" : "pending"),
    orderDate: orderDate,
    shipDate: shipDate,
    paymentMethod: ["credit_card", "bank_transfer", "paypal", "cash"][Math.floor(Math.random() * 4)]
  });
}

if (orderDocs.length > 0) {
  db.sample_orders.insertMany(orderDocs);
  print(`Created sample_orders collection with ${db.sample_orders.count()} documents`);
}

// Create indexes on the materialized sample collections
db.sample_users.createIndex({ userId: 1 });
db.sample_products.createIndex({ productId: 1 });
db.sample_orders.createIndex({ orderId: 1 });
db.sample_orders.createIndex({ userId: 1 });

// ----------------- CREATE VIRTUAL COLLECTION VIEWS -----------------

// Create a function to generate large virtual users
db.createView(
  "virtual_users",
  "sequence_helper",
  [
    { $limit: 500 },
    {
      $lookup: {
        from: "sequence_helper",
        pipeline: [{ $limit: 500 }],
        as: "seq2"
      }
    },
    { $unwind: "$seq2" },
    {
      $project: {
        _id: 0,
        userId: { $add: [{ $multiply: ["$id", 1000] }, "$seq2.id"] },
      }
    },
    {
      $match: {
        userId: { $lte: 100000 }
      }
    },
    {
      $addFields: {
        username: { $concat: ["user_", { $toString: "$userId" }] },
        email: { $concat: ["user_", { $toString: "$userId" }, "@example.com"] },
        firstName: { $concat: ["First", { $toString: "$userId" }] },
        lastName: { $concat: ["Last", { $toString: "$userId" }] },
        createdAt: { $dateSubtract: { 
          startDate: new Date(), 
          unit: "day", 
          amount: { $floor: { $multiply: [{ $rand: {} }, 1000] } } 
        }},
        status: {
          $cond: {
            if: { $gt: [{ $rand: {} }, 0.1] },
            then: "active",
            else: "inactive"
          }
        }
      }
    }
  ]
);

// Create a function to generate large virtual products
db.createView(
  "virtual_products",
  "sequence_helper",
  [
    { $limit: 10000 },
    {
      $project: {
        _id: 0,
        productId: "$id",
        name: { $concat: ["Product ", { $toString: "$id" }] },
        description: { $concat: ["Description for product ", { $toString: "$id" }] },
        price: { $multiply: [{ $rand: {} }, 1000] },
        sku: { $concat: ["SKU-", { $toString: { $toLong: "$id" } }] },
        inStock: { $cond: { if: { $gt: [{ $rand: {} }, 0.1] }, then: true, else: false } },
        category: {
          $arrayElemAt: [
            ["Electronics", "Home Goods", "Office Supplies", "Clothing", "Food"],
            { $floor: { $multiply: [{ $rand: {} }, 5] } }
          ]
        },
        createdAt: { $dateSubtract: { 
          startDate: new Date(), 
          unit: "day", 
          amount: { $floor: { $multiply: [{ $rand: {} }, 500] } } 
        }}
      }
    }
  ]
);

// Create a function to generate large virtual orders
db.createView(
  "virtual_orders",
  "sequence_helper",
  [
    { $limit: 500 },
    {
      $lookup: {
        from: "sequence_helper",
        pipeline: [{ $limit: 1000 }],
        as: "seq2"
      }
    },
    { $unwind: "$seq2" },
    {
      $project: {
        _id: 0,
        orderId: { 
          $concat: [
            "ORD-", 
            { 
              $toString: { 
                $add: [{ $multiply: ["$id", 1000] }, "$seq2.id"] 
              } 
            }
          ]
        },
        userId: { $add: [1, { $floor: { $multiply: [{ $rand: {} }, 100000] } }] },
        status: {
          $cond: {
            if: { $lt: [{ $rand: {} }, 0.7] },
            then: "completed",
            else: {
              $cond: {
                if: { $lt: [{ $rand: {} }, 0.9] },
                then: "processing",
                else: "pending"
              }
            }
          }
        },
        totalAmount: { $multiply: [{ $rand: {} }, 2000] },
        orderDate: { $dateSubtract: { 
          startDate: new Date(), 
          unit: "day", 
          amount: { $floor: { $multiply: [{ $rand: {} }, 1000] } } 
        }},
        paymentMethod: {
          $arrayElemAt: [
            ["credit_card", "bank_transfer", "paypal", "cash"],
            { $floor: { $multiply: [{ $rand: {} }, 4] } }
          ]
        }
      }
    }
  ]
);

// Create a README collection with usage instructions
db.data_generator_instructions.drop();
db.createCollection("data_generator_instructions");
db.data_generator_instructions.insertOne({
  title: "Virtual Large Collections Guide",
  description: "This database contains both materialized sample collections and virtual views for large data generation",
  materialized_collections: [
    {
      name: "sample_users",
      description: "1,000 actual stored user documents",
      example_query: "db.sample_users.find().limit(10)"
    },
    {
      name: "sample_products",
      description: "100 actual stored product documents",
      example_query: "db.sample_products.find().limit(5)"
    },
    {
      name: "sample_orders",
      description: "1,000 actual stored order documents",
      example_query: "db.sample_orders.find().limit(10)"
    }
  ],
  virtual_collections: [
    {
      name: "virtual_users",
      description: "Virtual view generating up to 100,000 users on-the-fly without storage",
      example_query: "db.virtual_users.find().limit(10)"
    },
    {
      name: "virtual_products",
      description: "Virtual view generating up to 10,000 products on-the-fly without storage",
      example_query: "db.virtual_products.find().limit(10)"
    },
    {
      name: "virtual_orders",
      description: "Virtual view generating up to 500,000 orders on-the-fly without storage",
      example_query: "db.virtual_orders.find().limit(10)"
    }
  ],
  usage_notes: [
    "Virtual collections don't consume storage space but generate data on demand",
    "For better performance, use limit() in your queries against virtual collections",
    "For testing with large datasets, try db.virtual_users.find().limit(10000)",
    "The virtual views create different random data on each query"
  ]
});

print("\n=====================================================");
print("Virtual Large Collections Setup Complete!");
print("=====================================================");
print("Materialized Sample Collections (actual stored data):");
print("- sample_users (1,000 documents)");
print("- sample_products (100 documents)");
print("- sample_orders (1,000 documents)");
print("");
print("Virtual Views (dynamically generated, no storage):");
print("- virtual_users (up to 100,000 documents)");
print("- virtual_products (up to 10,000 documents)");
print("- virtual_orders (up to 500,000 documents)");
print("");
print("For usage instructions:");
print("db.data_generator_instructions.findOne()");
print("====================================================="); 