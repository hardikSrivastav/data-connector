"""
Stock Metrics Flat - Demo Data Generator
Generates realistic stock data for the stock_metrics_flat collection
"""

import random
import json
from datetime import datetime, timedelta
from pymongo import MongoClient
import yaml

# Sector configurations with realistic median values
SECTOR_PROFILES = {
    "Technology": {
        "pe_median": 28.5, "roe_median": 0.18, "growth_median": 0.15,
        "net_margin_median": 0.12, "debt_to_equity_median": 0.3
    },
    "Healthcare": {
        "pe_median": 22.3, "roe_median": 0.14, "growth_median": 0.08,
        "net_margin_median": 0.10, "debt_to_equity_median": 0.4
    },
    "Financials": {
        "pe_median": 12.8, "roe_median": 0.12, "growth_median": 0.05,
        "net_margin_median": 0.18, "debt_to_equity_median": 0.8
    },
    "Consumer Discretionary": {
        "pe_median": 18.5, "roe_median": 0.15, "growth_median": 0.07,
        "net_margin_median": 0.08, "debt_to_equity_median": 0.5
    },
    "Industrials": {
        "pe_median": 16.2, "roe_median": 0.13, "growth_median": 0.06,
        "net_margin_median": 0.09, "debt_to_equity_median": 0.6
    },
    "Energy": {
        "pe_median": 9.4, "roe_median": 0.08, "growth_median": 0.03,
        "net_margin_median": 0.06, "debt_to_equity_median": 0.7
    },
    "Materials": {
        "pe_median": 14.1, "roe_median": 0.11, "growth_median": 0.04,
        "net_margin_median": 0.08, "debt_to_equity_median": 0.5
    },
    "Consumer Staples": {
        "pe_median": 19.8, "roe_median": 0.16, "growth_median": 0.04,
        "net_margin_median": 0.10, "debt_to_equity_median": 0.4
    },
    "Utilities": {
        "pe_median": 17.5, "roe_median": 0.09, "growth_median": 0.02,
        "net_margin_median": 0.12, "debt_to_equity_median": 0.9
    },
    "Real Estate": {
        "pe_median": 25.3, "roe_median": 0.07, "growth_median": 0.05,
        "net_margin_median": 0.15, "debt_to_equity_median": 1.2
    },
    "Communication Services": {
        "pe_median": 21.7, "roe_median": 0.14, "growth_median": 0.08,
        "net_margin_median": 0.11, "debt_to_equity_median": 0.5
    }
}

# Real household name stocks (Tier 1)
HOUSEHOLD_STOCKS = [
    # Technology
    {"ticker": "AAPL", "name": "Apple Inc.", "sector": "Technology", "type": "mega_cap_growth"},
    {"ticker": "MSFT", "name": "Microsoft Corporation", "sector": "Technology", "type": "mega_cap_growth"},
    {"ticker": "GOOGL", "name": "Alphabet Inc.", "sector": "Communication Services", "type": "mega_cap_growth"},
    {"ticker": "AMZN", "name": "Amazon.com Inc.", "sector": "Consumer Discretionary", "type": "mega_cap_growth"},
    {"ticker": "NVDA", "name": "NVIDIA Corporation", "sector": "Technology", "type": "high_growth"},
    {"ticker": "META", "name": "Meta Platforms Inc.", "sector": "Communication Services", "type": "mega_cap_growth"},
    {"ticker": "TSLA", "name": "Tesla Inc.", "sector": "Consumer Discretionary", "type": "high_growth"},
    
    # Healthcare
    {"ticker": "JNJ", "name": "Johnson & Johnson", "sector": "Healthcare", "type": "dividend_aristocrat"},
    {"ticker": "UNH", "name": "UnitedHealth Group", "sector": "Healthcare", "type": "large_cap_growth"},
    {"ticker": "PFE", "name": "Pfizer Inc.", "sector": "Healthcare", "type": "value_dividend"},
    
    # Financials
    {"ticker": "JPM", "name": "JPMorgan Chase & Co.", "sector": "Financials", "type": "large_cap_value"},
    {"ticker": "BAC", "name": "Bank of America Corp", "sector": "Financials", "type": "large_cap_value"},
    {"ticker": "WFC", "name": "Wells Fargo & Company", "sector": "Financials", "type": "value_dividend"},
    
    # Energy
    {"ticker": "XOM", "name": "Exxon Mobil Corporation", "sector": "Energy", "type": "dividend_aristocrat"},
    {"ticker": "CVX", "name": "Chevron Corporation", "sector": "Energy", "type": "dividend_aristocrat"},
    
    # Consumer
    {"ticker": "WMT", "name": "Walmart Inc.", "sector": "Consumer Staples", "type": "large_cap_value"},
    {"ticker": "PG", "name": "Procter & Gamble Co.", "sector": "Consumer Staples", "type": "dividend_aristocrat"},
    {"ticker": "KO", "name": "The Coca-Cola Company", "sector": "Consumer Staples", "type": "dividend_aristocrat"},
    
    # Industrials
    {"ticker": "BA", "name": "The Boeing Company", "sector": "Industrials", "type": "large_cap"},
    {"ticker": "CAT", "name": "Caterpillar Inc.", "sector": "Industrials", "type": "dividend_aristocrat"},
]

def generate_stock_archetype(ticker, name, sector, archetype_type):
    """Generate a complete stock record based on archetype"""
    
    profile = SECTOR_PROFILES.get(sector, SECTOR_PROFILES["Technology"])
    
    # Base price and market cap
    if archetype_type == "mega_cap_growth":
        market_cap = random.randint(1_000_000_000_000, 3_000_000_000_000)  # $1T-$3T
        price = random.uniform(150, 400)
        pe_ratio = random.uniform(25, 35)
        revenue_growth_1y = random.uniform(0.08, 0.20)
        dividend_yield = random.uniform(0, 0.01)
    elif archetype_type == "high_growth":
        market_cap = random.randint(200_000_000_000, 800_000_000_000)  # $200B-$800B
        price = random.uniform(180, 500)
        pe_ratio = random.uniform(40, 80)
        revenue_growth_1y = random.uniform(0.20, 0.50)
        dividend_yield = 0
    elif archetype_type == "dividend_aristocrat":
        market_cap = random.randint(100_000_000_000, 400_000_000_000)  # $100B-$400B
        price = random.uniform(80, 180)
        pe_ratio = random.uniform(12, 20)
        revenue_growth_1y = random.uniform(0.02, 0.08)
        dividend_yield = random.uniform(0.025, 0.045)
    elif archetype_type == "large_cap_value":
        market_cap = random.randint(100_000_000_000, 500_000_000_000)  # $100B-$500B
        price = random.uniform(40, 150)
        pe_ratio = random.uniform(8, 15)
        revenue_growth_1y = random.uniform(0.03, 0.10)
        dividend_yield = random.uniform(0.015, 0.035)
    elif archetype_type == "value_dividend":
        market_cap = random.randint(50_000_000_000, 200_000_000_000)  # $50B-$200B
        price = random.uniform(30, 80)
        pe_ratio = random.uniform(10, 16)
        revenue_growth_1y = random.uniform(0.02, 0.08)
        dividend_yield = random.uniform(0.03, 0.05)
    else:  # generic large_cap
        market_cap = random.randint(50_000_000_000, 300_000_000_000)
        price = random.uniform(50, 200)
        pe_ratio = random.uniform(15, 25)
        revenue_growth_1y = random.uniform(0.04, 0.12)
        dividend_yield = random.uniform(0.01, 0.03)
    
    # Calculate derived metrics
    roe = random.uniform(profile["roe_median"] * 0.8, profile["roe_median"] * 1.3)
    net_margin = random.uniform(profile["net_margin_median"] * 0.7, profile["net_margin_median"] * 1.5)
    operating_margin = net_margin * random.uniform(1.1, 1.4)
    current_ratio = random.uniform(1.0, 3.0)
    debt_to_equity = profile["debt_to_equity_median"] * random.uniform(0.7, 1.3)
    years_of_dividend_growth = random.randint(0, 30) if dividend_yield > 0 else 0
    
    # Build complete stock record
    stock = {
        # Basic Info
        "ticker": ticker,
        "company_name": name,
        "sector": sector,
        "industry": f"{sector} Industry",
        "exchange": "NASDAQ" if sector == "Technology" else random.choice(["NYSE", "NASDAQ"]),
        "currency": "USD",
        "country": "US",
        "market_cap": market_cap,
        "price": round(price, 2),
        "is_actively_trading": True,
        "is_etf": False,
        "full_time_employees": random.randint(10000, 200000),
        "ipo_date": f"{random.randint(1990, 2020)}-{random.randint(1, 12):02d}-{random.randint(1, 28):02d}",
        "fiscal_year_end": random.choice(["December", "September", "June", "March"]),
        "beta": round(random.uniform(0.8, 1.6), 2),
        "vol_avg": random.randint(1_000_000, 50_000_000),
        
        # Valuation
        "pe_ratio": round(pe_ratio, 2),
        "pe_ratio_ttm": round(pe_ratio * random.uniform(0.95, 1.05), 2),
        "pb_ratio": round(pe_ratio * roe * random.uniform(0.8, 1.2), 2),
        "ps_ratio": round(pe_ratio * net_margin * random.uniform(0.9, 1.1), 2),
        "peg_ratio": round(pe_ratio / (revenue_growth_1y * 100 + 1), 2),
        "ev_ebitda": round(pe_ratio * random.uniform(0.7, 0.9), 2),
        "price_to_fcf": round(pe_ratio * random.uniform(1.0, 1.3), 2),
        "dividend_yield": round(dividend_yield, 4),
        "earnings_yield": round(1 / pe_ratio if pe_ratio > 0 else 0, 4),
        "fcf_yield": round(random.uniform(0.02, 0.08), 4),
        
        # Growth
        "revenue_growth_1y": round(revenue_growth_1y, 4),
        "revenue_growth_3y": round(revenue_growth_1y * random.uniform(0.7, 1.2), 4),
        "revenue_growth_5y": round(revenue_growth_1y * random.uniform(0.6, 1.1), 4),
        "revenue_growth_ttm": round(revenue_growth_1y * random.uniform(0.9, 1.1), 4),
        "eps_growth_1y": round(revenue_growth_1y * random.uniform(1.1, 1.5), 4),
        "eps_growth_3y": round(revenue_growth_1y * random.uniform(0.8, 1.3), 4),
        "eps_growth_5y": round(revenue_growth_1y * random.uniform(0.7, 1.2), 4),
        "ebitda_growth_1y": round(revenue_growth_1y * random.uniform(0.9, 1.2), 4),
        "fcf_growth_1y": round(revenue_growth_1y * random.uniform(0.8, 1.4), 4),
        
        # Profitability
        "roe": round(roe, 4),
        "roa": round(roe * random.uniform(0.3, 0.6), 4),
        "roce": round(roe * random.uniform(0.8, 1.1), 4),
        "roic": round(roe * random.uniform(0.9, 1.2), 4),
        "net_margin": round(net_margin, 4),
        "operating_margin": round(operating_margin, 4),
        "ebitda_margin": round(operating_margin * random.uniform(1.1, 1.3), 4),
        "gross_margin": round(operating_margin * random.uniform(1.5, 2.5), 4),
        "asset_turnover": round(random.uniform(0.5, 2.0), 4),
        
        # Financial Health
        "debt_to_equity": round(debt_to_equity, 4),
        "debt_to_assets": round(random.uniform(0.2, 0.6), 4),
        "current_ratio": round(current_ratio, 2),
        "quick_ratio": round(random.uniform(0.8, 2.5), 2),
        "interest_coverage": round(random.uniform(5.0, 20.0), 2),
        "free_cash_flow": int(market_cap * random.uniform(0.02, 0.08)),
        "operating_cash_flow": int(market_cap * random.uniform(0.05, 0.12)),
        "altman_z_score": round(random.uniform(2.5, 5.0), 2),
        "piotroski_score": random.randint(6, 9),
        
        # Market Data
        "current_price": round(price, 2),
        "open_price": round(price * random.uniform(0.98, 1.02), 2),
        "day_high": round(price * random.uniform(1.00, 1.03), 2),
        "day_low": round(price * random.uniform(0.97, 1.00), 2),
        "previous_close": round(price * random.uniform(0.98, 1.02), 2),
        "volume": random.randint(1_000_000, 100_000_000),
        "year_high": round(price * random.uniform(1.05, 1.30), 2),
        "year_low": round(price * random.uniform(0.70, 0.95), 2),
        "price_change_percentage": round(random.uniform(-0.03, 0.03), 4),
        
        # Technical
        "rsi_14": round(random.uniform(30, 70), 2),
        "rsi_30": round(random.uniform(35, 65), 2),
        "sma_50": round(price * random.uniform(0.95, 1.05), 2),
        "sma_200": round(price * random.uniform(0.90, 1.10), 2),
        "bollinger_upper": round(price * 1.10, 2),
        "bollinger_lower": round(price * 0.90, 2),
        "volatility_30d": round(random.uniform(0.15, 0.45), 4),
        "sharpe_ratio": round(random.uniform(0.5, 2.0), 2),
        
        # Dividend
        "dividend_per_share": round(price * dividend_yield if dividend_yield > 0 else 0, 2),
        "dividend_payout_ratio": round(random.uniform(0.2, 0.6) if dividend_yield > 0 else 0, 4),
        "dividend_growth_rate_1y": round(random.uniform(0.02, 0.10) if dividend_yield > 0 else 0, 4),
        "years_of_dividend_payments": random.randint(0, 50) if dividend_yield > 0 else 0,
        "years_of_dividend_growth": years_of_dividend_growth,
        
        # Analyst Data
        "consensus_rating": random.choice(["Strong Buy", "Buy", "Hold"]),
        "total_analysts": random.randint(10, 50),
        "strong_buy_count": random.randint(3, 20),
        "buy_count": random.randint(5, 25),
        "hold_count": random.randint(2, 15),
        "avg_price_target_12m": round(price * random.uniform(1.05, 1.25), 2),
        
        # Screening Flags
        "is_large_cap": market_cap > 10_000_000_000,
        "is_profitable": net_margin > 0,
        "is_dividend_stock": dividend_yield > 0.02,
        "is_growth_stock": revenue_growth_1y > 0.10,
        "is_value_stock": pe_ratio < 15,
        "is_undervalued": pe_ratio < profile["pe_median"] * 0.8,
        "is_high_quality": roe > 0.15 and net_margin > 0.10,
        "is_financially_strong": current_ratio > 1.5 and debt_to_equity < 0.8,
        "has_competitive_advantage": roe > 0.15 and operating_margin > 0.15,
        "is_dividend_aristocrat": dividend_yield > 0 and years_of_dividend_growth >= 25,
        
        # Quality Scores
        "financial_health_score": round(random.uniform(6.0, 9.5), 1),
        "earnings_quality_score": round(random.uniform(0.6, 0.95), 2),
        "balance_sheet_quality_score": round(random.uniform(0.65, 0.90), 2),
        "management_effectiveness_score": round(random.uniform(0.70, 0.95), 2),
        
        # ESG
        "esg_total_score": round(random.uniform(50, 85), 1),
        "environmental_score": round(random.uniform(45, 80), 1),
        "social_score": round(random.uniform(50, 85), 1),
        "governance_score": round(random.uniform(55, 90), 1),
        
        # Metadata
        "last_updated": datetime.now().isoformat(),
        "data_source": "demo_generator",
        "is_demo_data": True
    }
    
    return stock

def generate_synthetic_stock(index, sector=None):
    """Generate a synthetic stock with random but realistic data"""
    
    if sector is None:
        sector = random.choice(list(SECTOR_PROFILES.keys()))
    
    # Generate synthetic ticker and name
    ticker = f"SYN{index:04d}"
    name = f"Synthetic {sector} Corp {index}"
    
    # Choose archetype
    archetype = random.choice([
        "large_cap_value", "large_cap_growth", "value_dividend",
        "high_growth", "mega_cap_growth"
    ])
    
    return generate_stock_archetype(ticker, name, sector, archetype)

def generate_all_stocks(household_count=20, synthetic_count=80):
    """Generate complete dataset"""
    
    stocks = []
    
    # Generate household name stocks
    print(f"Generating {household_count} household name stocks...")
    for stock_def in HOUSEHOLD_STOCKS[:household_count]:
        stock = generate_stock_archetype(
            stock_def["ticker"],
            stock_def["name"],
            stock_def["sector"],
            stock_def["type"]
        )
        stocks.append(stock)
        print(f"  ✓ {stock['ticker']} - {stock['company_name']}")
    
    # Generate synthetic stocks
    print(f"\nGenerating {synthetic_count} synthetic stocks...")
    for i in range(synthetic_count):
        stock = generate_synthetic_stock(i + 1)
        stocks.append(stock)
        if (i + 1) % 20 == 0:
            print(f"  ✓ Generated {i + 1}/{synthetic_count} synthetic stocks")
    
    print(f"\n✅ Total stocks generated: {len(stocks)}")
    return stocks

def insert_to_mongodb(stocks, mongo_uri, database_name="financial_data"):
    """Insert stocks into MongoDB"""
    
    print(f"\n📊 Connecting to MongoDB: {mongo_uri}")
    client = MongoClient(mongo_uri)
    db = client[database_name]
    collection = db.stock_metrics_flat
    
    # Clear existing demo data
    print("🧹 Clearing existing demo data...")
    delete_result = collection.delete_many({"is_demo_data": True})
    print(f"   Deleted {delete_result.deleted_count} existing demo records")
    
    # Insert new data
    print(f"💾 Inserting {len(stocks)} stock records...")
    result = collection.insert_many(stocks)
    print(f"✅ Successfully inserted {len(result.inserted_ids)} stocks")
    
    # Create indexes for common queries
    print("\n🔍 Creating indexes...")
    collection.create_index([("ticker", 1)])
    collection.create_index([("sector", 1)])
    collection.create_index([("pe_ratio", 1)])
    collection.create_index([("market_cap", -1)])
    collection.create_index([("is_large_cap", 1)])
    collection.create_index([("is_value_stock", 1)])
    print("✅ Indexes created")
    
    # Show summary statistics
    print("\n📊 Database Summary:")
    print(f"   Total stocks: {collection.count_documents({})}")
    print(f"   Demo stocks: {collection.count_documents({'is_demo_data': True})}")
    
    # Sector breakdown
    print("\n🏭 Sector Breakdown:")
    pipeline = [
        {"$group": {"_id": "$sector", "count": {"$sum": 1}}},
        {"$sort": {"count": -1}}
    ]
    for sector_stat in collection.aggregate(pipeline):
        print(f"   {sector_stat['_id']}: {sector_stat['count']} stocks")
    
    client.close()

def save_to_json(stocks, filename="stock_demo_data.json"):
    """Save stocks to JSON file for later import"""
    
    print(f"\n💾 Saving data to JSON file: {filename}")
    with open(filename, 'w') as f:
        json.dump(stocks, f, indent=2, default=str)
    print(f"✅ Saved {len(stocks)} stocks to {filename}")
    
    # Also create mongoimport command
    import_cmd = f"""
To import this data into MongoDB, run:

mongoimport --uri "mongodb://172.31.18.152:27017/financial_data" \\
  --collection stock_metrics_flat \\
  --file {filename} \\
  --jsonArray

Or if you need to delete existing demo data first:

mongosh mongodb://172.31.18.152:27017/financial_data --eval "db.stock_metrics_flat.deleteMany({{is_demo_data: true}})"
mongoimport --uri "mongodb://172.31.18.152:27017/financial_data" --collection stock_metrics_flat --file {filename} --jsonArray
"""
    print(import_cmd)

def main():
    """Main execution"""
    
    print("=" * 70)
    print("📈 STOCK METRICS FLAT - DEMO DATA GENERATOR")
    print("=" * 70)
    
    # Load config
    with open('/Users/hardiksrivastava/Ceneca/data-connector/discvr-deploy/config.yaml', 'r') as f:
        config = yaml.safe_load(f)
    
    mongo_uri = config['mongodb']['main']['uri']
    database_name = config['mongodb']['main']['database']
    
    print(f"\n🔧 Configuration:")
    print(f"   MongoDB URI: {mongo_uri}")
    print(f"   Database: {database_name}")
    print(f"   Collection: stock_metrics_flat")
    
    # Generate stocks
    print("\n" + "=" * 70)
    stocks = generate_all_stocks(household_count=20, synthetic_count=80)
    
    # Try to insert to MongoDB, fallback to JSON
    print("\n" + "=" * 70)
    try:
        insert_to_mongodb(stocks, mongo_uri, database_name)
    except Exception as e:
        print(f"⚠️  MongoDB connection failed: {str(e)[:100]}")
        print("\n🔄 Falling back to JSON export...")
        save_to_json(stocks, "/Users/hardiksrivastava/Ceneca/data-connector/discvr-deploy/stock_demo_data.json")
    
    print("\n" + "=" * 70)
    print("✅ DEMO DATA GENERATION COMPLETE!")
    print("=" * 70)
    
    # Sample queries to test
    print("\n💡 Sample queries to test:")
    print("   • Find tech stocks with PE < 30")
    print("   • Find dividend aristocrats")
    print("   • Find undervalued large caps")
    print("   • Screen by sector and growth rate")

if __name__ == "__main__":
    main()

