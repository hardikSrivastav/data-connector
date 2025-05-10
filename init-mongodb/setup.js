// This script sets up a sample MongoDB database with collections
// that simulate a typical company's data structure

// Connect to the MongoDB instance
db = db.getSiblingDB('dataconnector_mongo');

// Create a user with read/write access to the database
db.createUser({
  user: "dataconnector",
  pwd: "dataconnector",
  roles: [{ role: "readWrite", db: "dataconnector_mongo" }]
});

// Create customers collection
db.customers.drop();
db.createCollection("customers");
db.customers.insertMany([
  {
    customerId: 1001,
    name: "Acme Corporation",
    email: "contact@acmecorp.com",
    phone: "555-123-4567",
    address: {
      street: "123 Main St",
      city: "New York",
      state: "NY",
      zipCode: "10001",
      country: "USA"
    },
    industry: "Manufacturing",
    active: true,
    createdAt: new Date("2020-01-15"),
    salesRep: {
      id: 5001,
      name: "John Smith"
    }
  },
  {
    customerId: 1002,
    name: "Global Tech Solutions",
    email: "info@globaltech.com",
    phone: "555-987-6543",
    address: {
      street: "456 Innovation Way",
      city: "San Francisco",
      state: "CA",
      zipCode: "94105",
      country: "USA"
    },
    industry: "Technology",
    active: true,
    createdAt: new Date("2020-03-22"),
    salesRep: {
      id: 5002,
      name: "Sarah Johnson"
    }
  },
  {
    customerId: 1003,
    name: "Pacific Distributors",
    email: "orders@pacificdist.com",
    phone: "555-456-7890",
    address: {
      street: "789 Harbor Blvd",
      city: "Seattle",
      state: "WA",
      zipCode: "98101",
      country: "USA"
    },
    industry: "Retail",
    active: false,
    createdAt: new Date("2019-11-08"),
    salesRep: {
      id: 5003,
      name: "Michael Brown"
    }
  },
  {
    customerId: 1004,
    name: "Healthcare Partners",
    email: "info@healthcarepartners.org",
    phone: "555-222-3333",
    address: {
      street: "101 Medical Center Dr",
      city: "Boston",
      state: "MA",
      zipCode: "02115",
      country: "USA"
    },
    industry: "Healthcare",
    active: true,
    createdAt: new Date("2021-05-17"),
    salesRep: {
      id: 5001,
      name: "John Smith"
    }
  },
  {
    customerId: 1005,
    name: "Metro Education Group",
    email: "admin@metroedu.edu",
    phone: "555-777-8888",
    address: {
      street: "222 Learning Lane",
      city: "Chicago",
      state: "IL",
      zipCode: "60601",
      country: "USA"
    },
    industry: "Education",
    active: true,
    createdAt: new Date("2020-08-30"),
    salesRep: {
      id: 5004,
      name: "Jessica Lee"
    }
  }
]);

// Create orders collection
db.orders.drop();
db.createCollection("orders");
db.orders.insertMany([
  {
    orderId: "ORD-2021-001",
    customerId: 1001,
    items: [
      { productId: "P-100", name: "Industrial Mixer", quantity: 2, price: 1200.00 },
      { productId: "P-205", name: "Safety Gloves", quantity: 100, price: 8.50 }
    ],
    totalAmount: 3050.00,
    status: "completed",
    orderDate: new Date("2021-02-15"),
    shipDate: new Date("2021-02-20"),
    paymentMethod: "credit_card"
  },
  {
    orderId: "ORD-2021-002",
    customerId: 1002,
    items: [
      { productId: "P-300", name: "Cloud Server License", quantity: 5, price: 199.99 },
      { productId: "P-301", name: "Support Package", quantity: 1, price: 499.95 }
    ],
    totalAmount: 1499.90,
    status: "completed",
    orderDate: new Date("2021-03-05"),
    shipDate: new Date("2021-03-05"),
    paymentMethod: "bank_transfer"
  },
  {
    orderId: "ORD-2021-003",
    customerId: 1004,
    items: [
      { productId: "P-450", name: "Medical Supplies", quantity: 10, price: 87.75 },
      { productId: "P-455", name: "Sterilization Kit", quantity: 2, price: 249.99 }
    ],
    totalAmount: 1377.48,
    status: "completed",
    orderDate: new Date("2021-06-10"),
    shipDate: new Date("2021-06-15"),
    paymentMethod: "credit_card"
  },
  {
    orderId: "ORD-2021-004",
    customerId: 1005,
    items: [
      { productId: "P-510", name: "Interactive Whiteboard", quantity: 3, price: 899.99 },
      { productId: "P-512", name: "Student Tablets", quantity: 20, price: 129.99 }
    ],
    totalAmount: 5299.77,
    status: "processing",
    orderDate: new Date("2021-09-01"),
    shipDate: null,
    paymentMethod: "purchase_order"
  },
  {
    orderId: "ORD-2021-005",
    customerId: 1001,
    items: [
      { productId: "P-110", name: "Conveyor Belt", quantity: 1, price: 3500.00 }
    ],
    totalAmount: 3500.00,
    status: "completed",
    orderDate: new Date("2021-07-22"),
    shipDate: new Date("2021-08-10"),
    paymentMethod: "bank_transfer"
  },
  {
    orderId: "ORD-2021-006",
    customerId: 1003,
    items: [
      { productId: "P-250", name: "Display Shelves", quantity: 15, price: 175.00 },
      { productId: "P-251", name: "Cash Register", quantity: 2, price: 499.50 }
    ],
    totalAmount: 3624.00,
    status: "cancelled",
    orderDate: new Date("2021-04-30"),
    shipDate: null,
    paymentMethod: "credit_card"
  }
]);

// Create employees collection
db.employees.drop();
db.createCollection("employees");
db.employees.insertMany([
  {
    employeeId: 5001,
    name: "John Smith",
    email: "john.smith@company.com",
    department: "Sales",
    title: "Senior Sales Representative",
    hireDate: new Date("2018-03-15"),
    salary: 85000,
    manager: 5010,
    active: true
  },
  {
    employeeId: 5002,
    name: "Sarah Johnson",
    email: "sarah.johnson@company.com",
    department: "Sales",
    title: "Sales Representative",
    hireDate: new Date("2019-06-22"),
    salary: 72000,
    manager: 5010,
    active: true
  },
  {
    employeeId: 5003,
    name: "Michael Brown",
    email: "michael.brown@company.com",
    department: "Sales",
    title: "Sales Representative",
    hireDate: new Date("2019-02-10"),
    salary: 71000,
    manager: 5010,
    active: true
  },
  {
    employeeId: 5004,
    name: "Jessica Lee",
    email: "jessica.lee@company.com",
    department: "Sales",
    title: "Sales Representative",
    hireDate: new Date("2020-01-05"),
    salary: 70000,
    manager: 5010,
    active: true
  },
  {
    employeeId: 5010,
    name: "David Wilson",
    email: "david.wilson@company.com",
    department: "Sales",
    title: "Sales Manager",
    hireDate: new Date("2017-04-18"),
    salary: 110000,
    manager: null,
    active: true
  },
  {
    employeeId: 5020,
    name: "Jennifer Garcia",
    email: "jennifer.garcia@company.com",
    department: "Marketing",
    title: "Marketing Director",
    hireDate: new Date("2018-09-15"),
    salary: 115000,
    manager: null,
    active: true
  },
  {
    employeeId: 5021,
    name: "Robert Taylor",
    email: "robert.taylor@company.com",
    department: "Marketing",
    title: "Marketing Specialist",
    hireDate: new Date("2019-11-01"),
    salary: 65000,
    manager: 5020,
    active: true
  },
  {
    employeeId: 5030,
    name: "Amanda Martinez",
    email: "amanda.martinez@company.com",
    department: "Finance",
    title: "Financial Analyst",
    hireDate: new Date("2020-02-15"),
    salary: 78000,
    manager: 5031,
    active: true
  },
  {
    employeeId: 5031,
    name: "William Johnson",
    email: "william.johnson@company.com",
    department: "Finance",
    title: "Finance Manager",
    hireDate: new Date("2017-08-23"),
    salary: 105000,
    manager: null,
    active: true
  }
]);

// Create products collection
db.products.drop();
db.createCollection("products");
db.products.insertMany([
  {
    productId: "P-100",
    name: "Industrial Mixer",
    category: "Equipment",
    price: 1200.00,
    inStock: 15,
    specifications: {
      weight: "75 kg",
      dimensions: "120x60x90 cm",
      powerRequirement: "220V"
    },
    supplier: {
      id: "S001",
      name: "Industrial Supplies Co."
    }
  },
  {
    productId: "P-110",
    name: "Conveyor Belt",
    category: "Equipment",
    price: 3500.00,
    inStock: 5,
    specifications: {
      length: "10 meters",
      width: "80 cm",
      powerRequirement: "220V"
    },
    supplier: {
      id: "S001",
      name: "Industrial Supplies Co."
    }
  },
  {
    productId: "P-205",
    name: "Safety Gloves",
    category: "Safety",
    price: 8.50,
    inStock: 450,
    specifications: {
      material: "Kevlar blend",
      size: "Universal"
    },
    supplier: {
      id: "S002",
      name: "Safety Products Inc."
    }
  },
  {
    productId: "P-250",
    name: "Display Shelves",
    category: "Retail",
    price: 175.00,
    inStock: 30,
    specifications: {
      dimensions: "180x90x45 cm",
      material: "Steel and glass",
      maxWeight: "120 kg per shelf"
    },
    supplier: {
      id: "S003",
      name: "Retail Solutions Ltd."
    }
  },
  {
    productId: "P-251",
    name: "Cash Register",
    category: "Retail",
    price: 499.50,
    inStock: 12,
    specifications: {
      dimensions: "35x40x20 cm",
      connectivity: "Wi-Fi, Ethernet",
      powerRequirement: "110-240V"
    },
    supplier: {
      id: "S003",
      name: "Retail Solutions Ltd."
    }
  },
  {
    productId: "P-300",
    name: "Cloud Server License",
    category: "Software",
    price: 199.99,
    inStock: 999,
    specifications: {
      licenseType: "Annual",
      users: "Per user"
    },
    supplier: {
      id: "S004",
      name: "TechSoft Solutions"
    }
  },
  {
    productId: "P-301",
    name: "Support Package",
    category: "Service",
    price: 499.95,
    inStock: 999,
    specifications: {
      duration: "12 months",
      responseTime: "24 hours"
    },
    supplier: {
      id: "S004",
      name: "TechSoft Solutions"
    }
  },
  {
    productId: "P-450",
    name: "Medical Supplies",
    category: "Healthcare",
    price: 87.75,
    inStock: 200,
    specifications: {
      type: "General purpose",
      sterile: true
    },
    supplier: {
      id: "S005",
      name: "MedSupply Inc."
    }
  },
  {
    productId: "P-455",
    name: "Sterilization Kit",
    category: "Healthcare",
    price: 249.99,
    inStock: 15,
    specifications: {
      method: "Autoclave",
      capacity: "5L"
    },
    supplier: {
      id: "S005",
      name: "MedSupply Inc."
    }
  }
]);

// Print confirmation message
print("MongoDB database setup complete!");
print("Database: dataconnector_mongo");
print("Collections created: customers, orders, employees, products");
print("User 'dataconnector' created with readWrite access"); 