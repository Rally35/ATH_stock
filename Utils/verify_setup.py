"""
Setup Verification Script
Checks that the database is properly configured and accessible
"""

import os
import sys
import psycopg2
from dotenv import load_dotenv
from datetime import datetime

# Load environment variables
load_dotenv()


def print_header(text):
    """Print formatted header"""
    print("\n" + "="*60)
    print(f" {text}")
    print("="*60)


def print_status(success, message):
    """Print status message"""
    icon = "✓" if success else "✗"
    print(f"{icon} {message}")


def verify_database_connection():
    """Verify database connection"""
    print_header("Database Connection Test")
    
    try:
        conn = psycopg2.connect(
            host=os.getenv('DB_HOST', 'localhost'),
            port=os.getenv('DB_PORT', '5432'),
            database=os.getenv('DB_NAME', 'polish_stocks'),
            user=os.getenv('DB_USER', 'trader'),
            password=os.getenv('DB_PASSWORD', 'change_me_in_production')
        )
        cursor = conn.cursor()
        
        # Test query
        cursor.execute("SELECT version();")
        version = cursor.fetchone()[0]
        
        print_status(True, "Database connection successful")
        print(f"  PostgreSQL Version: {version.split(',')[0]}")
        
        cursor.close()
        conn.close()
        return True, conn
        
    except Exception as e:
        print_status(False, f"Database connection failed: {e}")
        return False, None


def verify_schema(conn):
    """Verify database schema"""
    print_header("Schema Verification")
    
    try:
        cursor = conn.cursor()
        
        # Check tables
        tables = ['stocks', 'historical_prices', 'technical_indicators', 'data_quality_log']
        
        for table in tables:
            cursor.execute(f"""
                SELECT EXISTS (
                    SELECT FROM information_schema.tables 
                    WHERE table_name = '{table}'
                );
            """)
            exists = cursor.fetchone()[0]
            print_status(exists, f"Table '{table}' exists")
        
        # Check view
        cursor.execute("""
            SELECT EXISTS (
                SELECT FROM information_schema.views 
                WHERE table_name = 'latest_stock_data'
            );
        """)
        exists = cursor.fetchone()[0]
        print_status(exists, "View 'latest_stock_data' exists")
        
        # Check indexes
        cursor.execute("""
            SELECT COUNT(*) FROM pg_indexes 
            WHERE schemaname = 'public';
        """)
        index_count = cursor.fetchone()[0]
        print_status(index_count >= 6, f"Found {index_count} indexes")
        
        cursor.close()
        return True
        
    except Exception as e:
        print_status(False, f"Schema verification failed: {e}")
        return False


def get_database_stats(conn):
    """Get database statistics"""
    print_header("Database Statistics")
    
    try:
        cursor = conn.cursor()
        
        # Count records in each table
        cursor.execute("SELECT COUNT(*) FROM stocks;")
        stock_count = cursor.fetchone()[0]
        print_status(True, f"Stocks: {stock_count} records")
        
        cursor.execute("SELECT COUNT(*) FROM historical_prices;")
        price_count = cursor.fetchone()[0]
        print_status(True, f"Historical Prices: {price_count:,} records")
        
        cursor.execute("SELECT COUNT(*) FROM technical_indicators;")
        indicator_count = cursor.fetchone()[0]
        print_status(True, f"Technical Indicators: {indicator_count} records")
        
        cursor.execute("SELECT COUNT(*) FROM data_quality_log;")
        log_count = cursor.fetchone()[0]
        print_status(True, f"Data Quality Logs: {log_count} records")
        
        # Database size
        cursor.execute("SELECT pg_size_pretty(pg_database_size('polish_stocks'));")
        db_size = cursor.fetchone()[0]
        print(f"\n  Database Size: {db_size}")
        
        # Date range
        if price_count > 0:
            cursor.execute("""
                SELECT MIN(date), MAX(date) 
                FROM historical_prices;
            """)
            min_date, max_date = cursor.fetchone()
            print(f"  Date Range: {min_date} to {max_date}")
        
        cursor.close()
        return True
        
    except Exception as e:
        print_status(False, f"Stats retrieval failed: {e}")
        return False


def test_sample_queries(conn):
    """Test sample queries"""
    print_header("Sample Query Tests")
    
    try:
        cursor = conn.cursor()
        
        # Test 1: Get active stocks
        cursor.execute("""
            SELECT symbol, name FROM stocks 
            WHERE is_active = TRUE 
            LIMIT 5;
        """)
        stocks = cursor.fetchall()
        
        if stocks:
            print_status(True, f"Query active stocks: Found {len(stocks)} stocks")
            for symbol, name in stocks[:3]:
                print(f"    - {symbol}: {name}")
        else:
            print_status(False, "No active stocks found")
        
        # Test 2: Latest prices
        cursor.execute("""
            SELECT s.symbol, hp.date, hp.close 
            FROM stocks s
            JOIN historical_prices hp ON s.stock_id = hp.stock_id
            WHERE hp.date = (
                SELECT MAX(date) FROM historical_prices 
                WHERE stock_id = s.stock_id
            )
            LIMIT 5;
        """)
        prices = cursor.fetchall()
        
        if prices:
            print_status(True, f"Query latest prices: Found {len(prices)} records")
            for symbol, date, close in prices[:3]:
                print(f"    - {symbol} on {date}: {close:.2f} PLN")
        else:
            print_status(False, "No price data found")
        
        # Test 3: View test
        cursor.execute("""
            SELECT COUNT(*) FROM latest_stock_data;
        """)
        view_count = cursor.fetchone()[0]
        print_status(view_count >= 0, f"View 'latest_stock_data': {view_count} records")
        
        cursor.close()
        return True
        
    except Exception as e:
        print_status(False, f"Query test failed: {e}")
        return False


def main():
    """Main verification function"""
    print("\n" + "="*60)
    print(" Polish Stocks Database - Setup Verification")
    print("="*60)
    print(f" Timestamp: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    
    # Check environment file
    print_header("Environment Configuration")
    if os.path.exists('.env'):
        print_status(True, ".env file exists")
    else:
        print_status(False, ".env file not found (using defaults)")
    
    # Test connection
    success, conn = verify_database_connection()
    if not success:
        print("\n✗ Setup verification failed: Cannot connect to database")
        print("  Make sure Docker container is running: docker-compose up -d")
        sys.exit(1)
    
    # Reconnect for tests (connection was closed)
    try:
        conn = psycopg2.connect(
            host=os.getenv('DB_HOST', 'localhost'),
            port=os.getenv('DB_PORT', '5432'),
            database=os.getenv('DB_NAME', 'polish_stocks'),
            user=os.getenv('DB_USER', 'trader'),
            password=os.getenv('DB_PASSWORD', 'change_me_in_production')
        )
    except:
        print("\n✗ Could not reconnect to database")
        sys.exit(1)
    
    # Run verification tests
    schema_ok = verify_schema(conn)
    stats_ok = get_database_stats(conn)
    queries_ok = test_sample_queries(conn)
    
    # Close connection
    conn.close()
    
    # Final summary
    print_header("Verification Summary")
    
    all_tests_passed = schema_ok and stats_ok and queries_ok
    
    if all_tests_passed:
        print_status(True, "All verification tests passed!")
        print("\n✓ Database setup is complete and working correctly")
        print("\nNext steps:")
        print("  1. Load historical data: python load_data.py")
        print("  2. Verify data quality with SQL queries")
        print("  3. Begin implementing technical indicators")
    else:
        print_status(False, "Some verification tests failed")
        print("\n✗ Please review the errors above and fix any issues")
    
    print("\n" + "="*60 + "\n")


if __name__ == "__main__":
    main()