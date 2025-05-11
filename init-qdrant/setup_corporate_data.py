#!/usr/bin/env python
"""
Vector database initialization script for Qdrant.
This script creates sample collections and loads dummy vector data
that simulates a corporate environment with document search capabilities.
"""

import numpy as np
import time
from qdrant_client import QdrantClient
from qdrant_client.http import models
import logging
import sys
import json
from datetime import datetime, timedelta
import random
import os

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    stream=sys.stdout
)
logger = logging.getLogger(__name__)

# Connect to Qdrant
def connect_qdrant():
    """Connect to the Qdrant server"""
    max_retries = 5
    retry_delay = 5
    
    # Inside the container, Qdrant is available at localhost:6333
    # The port 7500 is only mapped on the host machine
    host = "localhost"
    port = 6333  # Use the internal container port
    
    logger.info(f"Attempting to connect to Qdrant at {host}:{port}")
    
    for attempt in range(max_retries):
        try:
            client = QdrantClient(host=host, port=port)
            # Test connection
            logger.info(f"Testing connection to Qdrant at {host}:{port}...")
            client.get_collections()
            logger.info("Successfully connected to Qdrant!")
            return client
        except Exception as e:
            logger.warning(f"Connection attempt {attempt+1}/{max_retries} failed: {str(e)}")
            if attempt < max_retries - 1:
                logger.info(f"Retrying in {retry_delay} seconds...")
                time.sleep(retry_delay)
            else:
                logger.error("Failed to connect to Qdrant after maximum attempts")
                raise

# Generate random embeddings that simulate actual embeddings
def generate_random_embedding(dim=1536):
    """Generate a random embedding vector (normalized)"""
    vec = np.random.normal(0, 1, dim)
    vec = vec / np.linalg.norm(vec)  # Normalize to unit length
    return vec.tolist()

# Create corporate knowledge base collection
def create_knowledge_base(client):
    """Create a collection for corporate knowledge base documents"""
    collection_name = "corporate_knowledge"
    
    # Check if collection already exists
    collections = client.get_collections().collections
    if any(collection.name == collection_name for collection in collections):
        logger.info(f"Collection '{collection_name}' already exists, recreating...")
        client.delete_collection(collection_name)
    
    # Create collection with vector configurations
    client.create_collection(
        collection_name=collection_name,
        vectors_config=models.VectorParams(
            size=1536,  # OpenAI embedding dimension
            distance=models.Distance.COSINE
        ),
        # Add payload schema for better filtering
        on_disk_payload=True,  # Store payload on disk for large collections
    )
    
    # Define payload indexes for efficient filtering
    client.create_payload_index(
        collection_name=collection_name,
        field_name="department",
        field_schema=models.PayloadSchemaType.KEYWORD
    )
    
    client.create_payload_index(
        collection_name=collection_name,
        field_name="document_type",
        field_schema=models.PayloadSchemaType.KEYWORD
    )
    
    client.create_payload_index(
        collection_name=collection_name,
        field_name="created_at",
        field_schema=models.PayloadSchemaType.DATETIME
    )
    
    return collection_name

# Create product catalog collection
def create_product_catalog(client):
    """Create a collection for product catalog search"""
    collection_name = "product_catalog"
    
    # Check if collection already exists
    collections = client.get_collections().collections
    if any(collection.name == collection_name for collection in collections):
        logger.info(f"Collection '{collection_name}' already exists, recreating...")
        client.delete_collection(collection_name)
    
    # Create collection with vector configurations
    client.create_collection(
        collection_name=collection_name,
        vectors_config=models.VectorParams(
            size=1536,  # OpenAI embedding dimension
            distance=models.Distance.COSINE
        )
    )
    
    # Define payload indexes for efficient filtering
    client.create_payload_index(
        collection_name=collection_name,
        field_name="category",
        field_schema=models.PayloadSchemaType.KEYWORD
    )
    
    client.create_payload_index(
        collection_name=collection_name,
        field_name="in_stock",
        field_schema=models.PayloadSchemaType.BOOL
    )
    
    client.create_payload_index(
        collection_name=collection_name,
        field_name="price",
        field_schema=models.PayloadSchemaType.FLOAT
    )
    
    return collection_name

# Create customer support collection
def create_customer_support(client):
    """Create a collection for customer support queries"""
    collection_name = "customer_support"
    
    # Check if collection already exists
    collections = client.get_collections().collections
    if any(collection.name == collection_name for collection in collections):
        logger.info(f"Collection '{collection_name}' already exists, recreating...")
        client.delete_collection(collection_name)
    
    # Create collection with vector configurations
    client.create_collection(
        collection_name=collection_name,
        vectors_config=models.VectorParams(
            size=1536,  # OpenAI embedding dimension
            distance=models.Distance.COSINE
        )
    )
    
    # Define payload indexes for efficient filtering
    client.create_payload_index(
        collection_name=collection_name,
        field_name="category",
        field_schema=models.PayloadSchemaType.KEYWORD
    )
    
    client.create_payload_index(
        collection_name=collection_name,
        field_name="resolved",
        field_schema=models.PayloadSchemaType.BOOL
    )
    
    return collection_name

# Generate sample knowledge base data
def generate_knowledge_base_data(count=500):
    """Generate sample knowledge base document data"""
    departments = ["Engineering", "Finance", "HR", "Marketing", "Operations", "Legal", "Product", "Sales"]
    doc_types = ["Policy", "Procedure", "Handbook", "Report", "Guideline", "Memo", "Specification", "Contract"]
    
    # Sample document titles for each department
    titles_by_dept = {
        "Engineering": [
            "System Architecture Overview",
            "Code Review Process",
            "Technical Stack Documentation",
            "API Design Guidelines",
            "Security Best Practices",
            "Database Schema Documentation",
            "Testing Framework Guide",
            "Deployment Procedure"
        ],
        "Finance": [
            "Annual Budget Report",
            "Expense Policy",
            "Financial Forecasting Model",
            "Investment Strategy",
            "Tax Compliance Guide",
            "Accounting Procedures",
            "Revenue Recognition Policy",
            "Cost Allocation Framework"
        ],
        "HR": [
            "Employee Handbook",
            "Performance Review Process",
            "Hiring Guidelines",
            "Benefits Overview",
            "Remote Work Policy",
            "Training and Development Plan",
            "Compensation Structure",
            "Workplace Safety Guidelines"
        ],
        "Marketing": [
            "Brand Guidelines",
            "Content Strategy Framework",
            "Market Analysis Report",
            "Campaign Performance Metrics",
            "Social Media Playbook",
            "Product Messaging Guide",
            "Competitive Landscape Analysis",
            "Marketing Budget Allocation"
        ],
        "Operations": [
            "Supply Chain Procedure",
            "Quality Assurance Protocol",
            "Operational Efficiency Report",
            "Vendor Management Process",
            "Logistics Handbook",
            "Facilities Management Guide",
            "Business Continuity Plan",
            "Risk Assessment Framework"
        ],
        "Legal": [
            "Intellectual Property Guidelines",
            "Contract Template",
            "Regulatory Compliance Checklist",
            "Data Protection Policy",
            "Terms of Service",
            "Privacy Policy",
            "Licensing Agreement",
            "Corporate Governance Guide"
        ],
        "Product": [
            "Product Requirements Document",
            "User Research Findings",
            "Feature Specification",
            "Product Roadmap",
            "UX Design Guidelines",
            "A/B Testing Framework",
            "Product Metrics Dashboard",
            "Release Plan Template"
        ],
        "Sales": [
            "Sales Playbook",
            "Account Management Guide",
            "Pricing Strategy",
            "Sales Territory Mapping",
            "Customer Segmentation Analysis",
            "Lead Qualification Framework",
            "Quarterly Sales Forecast",
            "Deal Negotiation Guidelines"
        ]
    }
    
    # Generate random documents
    documents = []
    now = datetime.now()
    
    for i in range(count):
        department = random.choice(departments)
        doc_type = random.choice(doc_types)
        title = random.choice(titles_by_dept[department])
        created_at = now - timedelta(days=random.randint(0, 365*2))
        
        # Generate content based on document type and department
        content = f"{title} - {department} Department\n\n"
        content += f"Document Type: {doc_type}\n"
        content += f"Last Updated: {created_at.strftime('%Y-%m-%d')}\n\n"
        content += "This is a sample document for demonstration purposes. In a real system, this would contain the actual document content and would be much more detailed."
        
        document = {
            "title": title,
            "content": content,
            "department": department,
            "document_type": doc_type,
            "created_at": created_at.strftime("%Y-%m-%dT%H:%M:%S"),
            "vector": generate_random_embedding()
        }
        documents.append(document)
    
    return documents

# Generate sample product catalog data
def generate_product_catalog_data(count=200):
    """Generate sample product catalog data"""
    categories = ["Electronics", "Furniture", "Office Supplies", "Software", "Hardware", "Peripherals", "Network", "Storage"]
    manufacturers = ["TechCorp", "OfficeWorks", "DataSystems", "ErgonomicsPlus", "NetGear Solutions", "WorkStation Inc."]
    
    products = []
    
    # Template products for each category
    product_templates = {
        "Electronics": [
            "Laptop Computer - {}", "Desktop Workstation - {}", "Tablet Device - {}", 
            "Smartphone - {}", "Video Conferencing System - {}"
        ],
        "Furniture": [
            "Ergonomic Chair - {}", "Standing Desk - {}", "Conference Table - {}", 
            "Filing Cabinet - {}", "Modular Workstation - {}"
        ],
        "Office Supplies": [
            "Premium Notebook - {}", "Fountain Pen Set - {}", "Desk Organizer - {}", 
            "Whiteboard Markers - {}", "Business Card Holder - {}"
        ],
        "Software": [
            "Project Management Solution - {}", "Design Suite - {}", "Accounting Package - {}", 
            "Security Software - {}", "Database Management System - {}"
        ],
        "Hardware": [
            "Network Server - {}", "GPU Unit - {}", "Processing Unit - {}", 
            "Memory Module - {}", "RAID Controller - {}"
        ],
        "Peripherals": [
            "Mechanical Keyboard - {}", "Precision Mouse - {}", "Ultrawide Monitor - {}", 
            "Noise-Cancelling Headphones - {}", "Document Scanner - {}"
        ],
        "Network": [
            "Wireless Router - {}", "Network Switch - {}", "Firewall Appliance - {}", 
            "Access Point - {}", "Network Cable Set - {}"
        ],
        "Storage": [
            "External Hard Drive - {}", "NAS System - {}", "SSD Drive - {}", 
            "Cloud Storage License - {}", "Backup Solution - {}"
        ]
    }
    
    for i in range(count):
        category = random.choice(categories)
        manufacturer = random.choice(manufacturers)
        
        product_template = random.choice(product_templates[category])
        name = product_template.format(manufacturer)
        
        # Random SKU format
        sku = f"{category[:3].upper()}-{manufacturer[:3].upper()}-{random.randint(1000, 9999)}"
        
        # Price based on category
        price_ranges = {
            "Electronics": (500, 2500),
            "Furniture": (200, 1500),
            "Office Supplies": (10, 100),
            "Software": (100, 1000),
            "Hardware": (300, 3000),
            "Peripherals": (50, 500),
            "Network": (100, 1500),
            "Storage": (150, 1200)
        }
        
        price = round(random.uniform(*price_ranges[category]), 2)
        
        # 80% chance of being in stock
        in_stock = random.random() < 0.8
        
        # Generate description
        description = f"{name}\n\n"
        description += f"SKU: {sku}\n"
        description += f"Category: {category}\n"
        description += f"Manufacturer: {manufacturer}\n"
        description += f"Price: ${price}\n"
        description += f"In Stock: {'Yes' if in_stock else 'No'}\n\n"
        description += "This product is designed for corporate environments and offers professional-grade quality and performance."
        
        product = {
            "name": name,
            "sku": sku,
            "category": category,
            "manufacturer": manufacturer,
            "price": price,
            "in_stock": in_stock,
            "description": description,
            "vector": generate_random_embedding()
        }
        
        products.append(product)
    
    return products

# Generate sample customer support data
def generate_customer_support_data(count=300):
    """Generate sample customer support query data"""
    categories = ["Technical", "Billing", "Account", "Product", "Service", "General"]
    
    # Common query templates for each category
    query_templates = {
        "Technical": [
            "How do I configure {}?",
            "I'm having trouble connecting to {}",
            "{} is showing an error message",
            "Can't install {}",
            "{} keeps crashing"
        ],
        "Billing": [
            "Question about my invoice #{}",
            "Why was I charged for {}?",
            "Need to update payment method for account #{}",
            "Requesting refund for {}",
            "Subscription renewal issue for {}"
        ],
        "Account": [
            "How do I reset my password for {}?",
            "Need to add users to account #{}",
            "Can't access my {} account",
            "How to update profile information for {}",
            "Account lockout issue with {}"
        ],
        "Product": [
            "Missing features in {}",
            "How to use {} with our existing system",
            "{} compatibility question",
            "Looking for documentation on {}",
            "Is {} the right solution for our needs?"
        ],
        "Service": [
            "Service interruption with {}",
            "Scheduled maintenance for {}",
            "Service level agreement for {}",
            "Upgrade options for {}",
            "Service quality issues with {}"
        ],
        "General": [
            "Contact information for {} department",
            "Opening hours of {}",
            "Company policy regarding {}",
            "Where can I find information about {}?",
            "Request for information on {}"
        ]
    }
    
    products = ["Cloud Server", "ERP System", "CRM Platform", "Security Suite", 
                "Database License", "Email Service", "VPN Access", "Backup Solution",
                "Project Management Tool", "Collaboration Suite"]
    
    queries = []
    now = datetime.now()
    
    for i in range(count):
        category = random.choice(categories)
        product = random.choice(products)
        template = random.choice(query_templates[category])
        query_text = template.format(product)
        
        # 70% of tickets are resolved
        resolved = random.random() < 0.7
        created_at = now - timedelta(days=random.randint(0, 180))
        
        if resolved:
            resolved_at = created_at + timedelta(days=random.randint(1, 10))
        else:
            resolved_at = None
        
        # Generate sample customer information
        customer = {
            "id": f"CUST-{random.randint(10000, 99999)}",
            "company": f"Company-{random.randint(100, 999)}",
            "plan": random.choice(["Basic", "Professional", "Enterprise"])
        }
        
        # Generate full ticket text
        full_text = f"Support Ticket: {query_text}\n\n"
        full_text += f"Category: {category}\n"
        full_text += f"Customer: {customer['company']} (ID: {customer['id']})\n"
        full_text += f"Plan: {customer['plan']}\n"
        full_text += f"Created: {created_at.strftime('%Y-%m-%d')}\n"
        if resolved:
            full_text += f"Status: Resolved on {resolved_at.strftime('%Y-%m-%d')}\n"
        else:
            full_text += "Status: Open\n"
        full_text += "\nAdditional Details:\n"
        full_text += "This is a sample support ticket for demonstration purposes. In a real system, this would contain the full conversation history and resolution details."
            
        query = {
            "query_text": query_text,
            "category": category,
            "product": product,
            "resolved": resolved,
            "created_at": created_at.strftime("%Y-%m-%dT%H:%M:%S"),
            "resolved_at": resolved_at.strftime("%Y-%m-%dT%H:%M:%S") if resolved else None,
            "customer": customer,
            "full_text": full_text,
            "vector": generate_random_embedding()
        }
        
        queries.append(query)
    
    return queries

# Main function to set up all collections
def setup_qdrant():
    """Main function to set up Qdrant with sample data"""
    logger.info("Starting Qdrant data setup...")
    
    # Connect to Qdrant
    client = connect_qdrant()
    
    # Create knowledge base collection and load data
    logger.info("Creating knowledge base collection...")
    kb_collection = create_knowledge_base(client)
    kb_data = generate_knowledge_base_data(500)
    
    # Upload in batches
    batch_size = 100
    for i in range(0, len(kb_data), batch_size):
        batch = kb_data[i:i + batch_size]
        logger.info(f"Uploading knowledge base documents batch {i//batch_size + 1}/{(len(kb_data) + batch_size - 1)//batch_size}...")
        
        # Convert data format for Qdrant
        points = []
        for idx, doc in enumerate(batch):
            vector = doc.pop("vector")
            points.append(models.PointStruct(
                id=i + idx,
                vector=vector,
                payload=doc
            ))
        
        # Upload batch
        client.upsert(
            collection_name=kb_collection,
            points=points
        )
    
    # Create product catalog collection and load data
    logger.info("Creating product catalog collection...")
    product_collection = create_product_catalog(client)
    product_data = generate_product_catalog_data(200)
    
    # Upload in batches
    for i in range(0, len(product_data), batch_size):
        batch = product_data[i:i + batch_size]
        logger.info(f"Uploading product catalog data batch {i//batch_size + 1}/{(len(product_data) + batch_size - 1)//batch_size}...")
        
        # Convert data format for Qdrant
        points = []
        for idx, product in enumerate(batch):
            vector = product.pop("vector")
            points.append(models.PointStruct(
                id=i + idx,
                vector=vector,
                payload=product
            ))
        
        # Upload batch
        client.upsert(
            collection_name=product_collection,
            points=points
        )
    
    # Create customer support collection and load data
    logger.info("Creating customer support collection...")
    support_collection = create_customer_support(client)
    support_data = generate_customer_support_data(300)
    
    # Upload in batches
    for i in range(0, len(support_data), batch_size):
        batch = support_data[i:i + batch_size]
        logger.info(f"Uploading customer support data batch {i//batch_size + 1}/{(len(support_data) + batch_size - 1)//batch_size}...")
        
        # Convert data format for Qdrant
        points = []
        for idx, query in enumerate(batch):
            vector = query.pop("vector")
            points.append(models.PointStruct(
                id=i + idx,
                vector=vector,
                payload=query
            ))
        
        # Upload batch
        client.upsert(
            collection_name=support_collection,
            points=points
        )
    
    # Print collection info and counts
    for collection_name in [kb_collection, product_collection, support_collection]:
        count = client.count(collection_name=collection_name).count
        logger.info(f"Collection '{collection_name}' created with {count} points")
    
    logger.info("Qdrant data setup completed successfully!")

if __name__ == "__main__":
    setup_qdrant()