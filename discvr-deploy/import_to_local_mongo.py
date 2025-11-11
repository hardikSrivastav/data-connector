"""
Import stock demo data into local MongoDB Docker container
"""

from pymongo import MongoClient
import json

def main():
    # Connect to local MongoDB container
    print("=" * 70)
    print("📦 IMPORTING TO LOCAL MONGODB DOCKER CONTAINER")
    print("=" * 70)
    
    mongo_uri = 'mongodb://localhost:27017/'
    print(f"\n🔗 Connecting to: {mongo_uri}")
    print("   Container: stock-demo-mongodb")
    
    client = MongoClient(mongo_uri)
    db = client['financial_data']
    collection = db['stock_metrics_flat']
    
    # Load the JSON data
    print('\n📂 Loading stock data from JSON...')
    with open('stock_demo_data.json', 'r') as f:
        stocks = json.load(f)
    
    print(f'✅ Loaded {len(stocks)} stocks')
    
    # Clear existing demo data
    print('\n🧹 Clearing existing demo data...')
    delete_result = collection.delete_many({'is_demo_data': True})
    print(f'   Deleted {delete_result.deleted_count} existing demo records')
    
    # Insert new data
    print(f'\n💾 Inserting {len(stocks)} stock records into local MongoDB...')
    result = collection.insert_many(stocks)
    print(f'✅ Successfully inserted {len(result.inserted_ids)} stocks')
    
    # Create indexes
    print('\n🔍 Creating indexes...')
    collection.create_index([('ticker', 1)])
    collection.create_index([('sector', 1)])
    collection.create_index([('pe_ratio', 1)])
    collection.create_index([('market_cap', -1)])
    collection.create_index([('is_large_cap', 1)])
    collection.create_index([('is_value_stock', 1)])
    collection.create_index([('is_growth_stock', 1)])
    collection.create_index([('revenue_growth_1y', 1)])
    collection.create_index([('dividend_yield', 1)])
    print('✅ Indexes created')
    
    # Show summary
    print('\n' + '=' * 70)
    print('📊 DATABASE SUMMARY')
    print('=' * 70)
    print(f'\n📈 Total stocks in database: {collection.count_documents({})}')
    print(f'🎲 Demo stocks: {collection.count_documents({"is_demo_data": True})}')
    
    # Sector breakdown
    print('\n🏭 SECTOR BREAKDOWN:')
    pipeline = [
        {'$group': {'_id': '$sector', 'count': {'$sum': 1}}},
        {'$sort': {'count': -1}}
    ]
    for sector_stat in collection.aggregate(pipeline):
        print(f'   {sector_stat["_id"]:30s}: {sector_stat["count"]:3d} stocks')
    
    # Sample queries
    print('\n' + '=' * 70)
    print('🔍 SAMPLE QUERY RESULTS')
    print('=' * 70)
    
    print('\n1️⃣  Tech stocks with PE < 30:')
    tech_low_pe = list(collection.find(
        {'sector': 'Technology', 'pe_ratio': {'$lt': 30}},
        {'ticker': 1, 'company_name': 1, 'pe_ratio': 1, '_id': 0}
    ).limit(5))
    for stock in tech_low_pe:
        print(f'    {stock["ticker"]:6s} - {stock["company_name"]:40s} PE: {stock["pe_ratio"]:6.2f}')
    
    print('\n2️⃣  Large cap dividend stocks:')
    div_stocks = list(collection.find(
        {'is_large_cap': True, 'is_dividend_stock': True},
        {'ticker': 1, 'company_name': 1, 'dividend_yield': 1, '_id': 0}
    ).limit(5))
    for stock in div_stocks:
        print(f'    {stock["ticker"]:6s} - {stock["company_name"]:40s} Yield: {stock["dividend_yield"]*100:.2f}%')
    
    print('\n3️⃣  Undervalued stocks:')
    undervalued = list(collection.find(
        {'is_undervalued': True},
        {'ticker': 1, 'company_name': 1, 'pe_ratio': 1, 'sector': 1, '_id': 0}
    ).limit(5))
    for stock in undervalued:
        print(f'    {stock["ticker"]:6s} - {stock["company_name"]:40s} PE: {stock["pe_ratio"]:6.2f} | {stock["sector"]}')
    
    print('\n4️⃣  High growth stocks (revenue growth > 15%):')
    growth_stocks = list(collection.find(
        {'revenue_growth_1y': {'$gt': 0.15}},
        {'ticker': 1, 'company_name': 1, 'revenue_growth_1y': 1, '_id': 0}
    ).limit(5))
    for stock in growth_stocks:
        print(f'    {stock["ticker"]:6s} - {stock["company_name"]:40s} Growth: {stock["revenue_growth_1y"]*100:.1f}%')
    
    print('\n5️⃣  Financially strong stocks:')
    strong = list(collection.find(
        {'is_financially_strong': True},
        {'ticker': 1, 'company_name': 1, 'current_ratio': 1, 'debt_to_equity': 1, '_id': 0}
    ).limit(5))
    for stock in strong:
        print(f'    {stock["ticker"]:6s} - {stock["company_name"]:40s} CR: {stock["current_ratio"]:.2f} | D/E: {stock["debt_to_equity"]:.2f}')
    
    client.close()
    
    print('\n' + '=' * 70)
    print('✅ LOCAL MONGODB IMPORT COMPLETE!')
    print('=' * 70)
    print('\n💡 You can now query this data using:')
    print('   - MongoDB Compass: mongodb://localhost:27017')
    print('   - mongosh: mongosh mongodb://localhost:27017/financial_data')
    print('   - Python: MongoClient("mongodb://localhost:27017/")')
    print('\n🐳 Docker container: stock-demo-mongodb')
    print('   Stop: docker stop stock-demo-mongodb')
    print('   Start: docker start stock-demo-mongodb')
    print('   Remove: docker-compose -f docker-compose-mongo.yml down -v')

if __name__ == '__main__':
    main()

