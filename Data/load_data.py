"""
Improved Data Loader for Polish Stocks
Uses Yahoo Finance with proper symbol mapping
Much more reliable than Stooq
"""

import os
import sys
from datetime import datetime
from typing import Optional, Tuple
import pandas as pd
import psycopg2
from psycopg2.extras import execute_values
from dotenv import load_dotenv
import time

# Try to import wig20_symbols
try:
    from DATA.wig20_symbols import get_yahoo_symbol, get_company_name
    HAS_SYMBOL_MAPPER = True
except ImportError:
    HAS_SYMBOL_MAPPER = False
    print("⚠ Warning: wig20_symbols.py not found. Will use basic symbol format.")

# Load environment variables
load_dotenv()


class ImprovedDataLoader:
    """Loads historical stock data using Yahoo Finance"""
    
    def __init__(self):
        """Initialize database connection"""
        self.conn_params = {
            'host': os.getenv('DB_HOST', 'localhost'),
            'port': os.getenv('DB_PORT', '5432'),
            'database': os.getenv('DB_NAME', 'polish_stocks'),
            'user': os.getenv('DB_USER', 'trader'),
            'password': os.getenv('DB_PASSWORD', 'change_me_in_production')
        }
        self.conn = None
        self.cursor = None
        
    def connect(self):
        """Establish database connection"""
        try:
            self.conn = psycopg2.connect(**self.conn_params)
            self.cursor = self.conn.cursor()
            print("✓ Database connection established")
        except Exception as e:
            print(f"✗ Database connection failed: {e}")
            sys.exit(1)
    
    def close(self):
        """Close database connection"""
        if self.cursor:
            self.cursor.close()
        if self.conn:
            self.conn.close()
            print("✓ Database connection closed")
    
    def add_stock(self, symbol: str, name: str = None, sector: str = None) -> int:
        """Add stock to database if not exists, return stock_id"""
        try:
            self.cursor.execute(
                "SELECT stock_id FROM stocks WHERE symbol = %s",
                (symbol,)
            )
            result = self.cursor.fetchone()
            
            if result:
                return result[0]
            
            # Get company name from mapper if available
            if name is None and HAS_SYMBOL_MAPPER:
                name = get_company_name(symbol)
            
            self.cursor.execute(
                """
                INSERT INTO stocks (symbol, name, sector)
                VALUES (%s, %s, %s)
                RETURNING stock_id
                """,
                (symbol, name, sector)
            )
            stock_id = self.cursor.fetchone()[0]
            self.conn.commit()
            print(f"✓ Added stock: {symbol} (ID: {stock_id})")
            return stock_id
            
        except Exception as e:
            self.conn.rollback()
            print(f"✗ Error adding stock {symbol}: {e}")
            return None
    
    def fetch_data_yahoo(self, symbol: str, start_date: str, end_date: str) -> Optional[pd.DataFrame]:
        """
        Fetch data using yfinance
        """
        try:
            # Determine Yahoo Finance symbol
            if HAS_SYMBOL_MAPPER:
                yahoo_symbol = get_yahoo_symbol(symbol)
                if yahoo_symbol is None:
                    # Try basic format as fallback
                    yahoo_symbol = f"{symbol}.WA"
                    print(f"  ⚠ No mapping for {symbol}, trying {yahoo_symbol}")
            else:
                yahoo_symbol = f"{symbol}.WA"
            
            print(f"  Fetching from Yahoo Finance: {yahoo_symbol}")
            
            import yfinance as yf
            ticker = yf.Ticker(yahoo_symbol)
            df = ticker.history(start=start_date, end=end_date, auto_adjust=False)
            
            if df.empty:
                print(f"  ✗ No data returned for {yahoo_symbol}")
                return None
            
            # Reset index to get date as column
            df = df.reset_index()
            
            # Standardize column names
            df = df.rename(columns={
                'Date': 'date',
                'Open': 'open',
                'High': 'high',
                'Low': 'low',
                'Close': 'close',
                'Volume': 'volume',
                'Adj Close': 'adjusted_close'
            })
            
            # Select only needed columns
            columns = ['date', 'open', 'high', 'low', 'close', 'volume']
            if 'adjusted_close' in df.columns:
                columns.append('adjusted_close')
            
            df = df[columns]
            
            # Ensure proper date handling
            df['date'] = pd.to_datetime(df['date'])
            if df['date'].dt.tz is not None:
                df['date'] = df['date'].dt.tz_localize(None)
            
            # Sort by date
            df = df.sort_values('date')
            
            # Ensure numeric types
            for col in ['open', 'high', 'low', 'close']:
                df[col] = pd.to_numeric(df[col], errors='coerce')
            df['volume'] = pd.to_numeric(df['volume'], errors='coerce').fillna(0).astype(int)
            
            # Remove rows with missing price data
            df = df.dropna(subset=['open', 'high', 'low', 'close'])
            
            if df.empty:
                print(f"  ✗ No valid data after cleaning")
                return None
            
            print(f"  ✓ Retrieved {len(df)} records from {df['date'].min().date()} to {df['date'].max().date()}")
            return df
            
        except Exception as e:
            print(f"  ✗ Error fetching data: {str(e)[:150]}")
            return None
    
    def load_historical_data(self, stock_id: int, df: pd.DataFrame) -> Tuple[int, int]:
        """Load historical price data into database"""
        try:
            records = []
            for _, row in df.iterrows():
                records.append((
                    stock_id,
                    row['date'].date(),
                    float(row['open']),
                    float(row['high']),
                    float(row['low']),
                    float(row['close']),
                    int(row['volume']),
                    float(row.get('adjusted_close', row['close']))
                ))
            
            insert_query = """
                INSERT INTO historical_prices 
                (stock_id, date, open, high, low, close, volume, adjusted_close)
                VALUES %s
                ON CONFLICT (stock_id, date) 
                DO UPDATE SET
                    open = EXCLUDED.open,
                    high = EXCLUDED.high,
                    low = EXCLUDED.low,
                    close = EXCLUDED.close,
                    volume = EXCLUDED.volume,
                    adjusted_close = EXCLUDED.adjusted_close,
                    created_at = CURRENT_TIMESTAMP
            """
            
            execute_values(self.cursor, insert_query, records)
            self.conn.commit()
            
            print(f"  ✓ Loaded {len(records)} price records into database")
            return len(records), 0
            
        except Exception as e:
            self.conn.rollback()
            print(f"  ✗ Error loading data: {e}")
            return 0, 0
    
    def load_stock_data(self, symbol: str, start_date: str, end_date: str, name: str = None, sector: str = None):
        """Complete workflow to load stock data"""
        print(f"\n{'='*60}")
        print(f"Loading data for {symbol}")
        print(f"{'='*60}")
        
        # Add stock to database
        stock_id = self.add_stock(symbol, name, sector)
        if not stock_id:
            return False
        
        # Fetch data
        df = self.fetch_data_yahoo(symbol, start_date, end_date)
        
        if df is None or df.empty:
            return False
        
        # Load data into database
        inserted, _ = self.load_historical_data(stock_id, df)
        
        return inserted > 0


    def get_stocks_from_database(self):
        """Get list of stocks from database"""
        try:
            self.cursor.execute("""
                SELECT stock_id, symbol
                FROM stocks
                WHERE is_active = TRUE
                ORDER BY symbol
            """)
            return self.cursor.fetchall()
        except Exception as e:
            print(f"✗ Error fetching stocks from database: {e}")
            return []


def main():
    """Main execution function"""
    print("\n" + "="*60)
    print("Polish Stocks Data Loader (Yahoo Finance)")
    print("="*60 + "\n")
    
    # Check if yfinance is installed
    try:
        import yfinance
    except ImportError:
        print("✗ yfinance not installed!")
        print("  Install it with: pip install yfinance")
        sys.exit(1)
    
    # Initialize loader
    loader = ImprovedDataLoader()
    loader.connect()
    
    # Configuration
    start_date = os.getenv('START_DATE', '2020-01-01')
    end_date = os.getenv('END_DATE', datetime.now().strftime('%Y-%m-%d'))
    
    # Check for stocks in database first
    db_stocks = loader.get_stocks_from_database()
    
    print("Load Mode:")
    print("1. Load data for stocks ALREADY in database (recommended)")
    print("2. Add NEW stocks from .env file")
    print("3. Do both (update existing + add new)")
    
    choice = input("\nEnter choice (1-3) [default: 1]: ").strip() or "1"
    print()
    
    symbols_to_load = []
    
    if choice in ["1", "3"]:
        # Load data for existing stocks
        if db_stocks:
            print(f"Found {len(db_stocks)} stocks in database:")
            for stock_id, symbol in db_stocks[:10]:
                print(f"  - {symbol}")
            if len(db_stocks) > 10:
                print(f"  ... and {len(db_stocks) - 10} more")
            print()
            
            symbols_to_load.extend([symbol for stock_id, symbol in db_stocks])
        else:
            print("⚠ No stocks found in database")
            if choice == "1":
                print("  Switch to option 2 to add stocks from .env")
                loader.close()
                return
    
    if choice in ["2", "3"]:
        # Add new stocks from .env
        symbols_str = os.getenv('STOCK_SYMBOLS', '')
        if symbols_str:
            env_symbols = [s.strip() for s in symbols_str.split(',') if s.strip()]
            
            # Only add symbols not already in database
            db_symbol_set = set(symbol for _, symbol in db_stocks)
            new_symbols = [s for s in env_symbols if s not in db_symbol_set]
            
            if new_symbols:
                print(f"\nNew stocks from .env file ({len(new_symbols)}):")
                for symbol in new_symbols[:10]:
                    print(f"  - {symbol}")
                if len(new_symbols) > 10:
                    print(f"  ... and {len(new_symbols) - 10} more")
                print()
                
                symbols_to_load.extend(new_symbols)
            else:
                print("\n✓ All stocks from .env are already in database")
        else:
            print("⚠ No STOCK_SYMBOLS found in .env file")
    
    if not symbols_to_load:
        print("✗ No stocks to load!")
        loader.close()
        return
    
    # Remove duplicates while preserving order
    seen = set()
    symbols_to_load = [x for x in symbols_to_load if not (x in seen or seen.add(x))]
    
    print(f"Configuration:")
    print(f"  Date Range: {start_date} to {end_date}")
    print(f"  Total stocks to load: {len(symbols_to_load)}")
    print(f"  Data Source: Yahoo Finance")
    
    if HAS_SYMBOL_MAPPER:
        print(f"  Symbol Mapper: ✓ Active (using wig20_symbols.py)")
    else:
        print(f"  Symbol Mapper: ✗ Not found (using basic .WA format)")
        print(f"  Tip: Create wig20_symbols.py for better symbol mapping")
    print()
    
    # Confirm before proceeding
    if len(symbols_to_load) > 50:
        confirm = input(f"⚠ Loading {len(symbols_to_load)} stocks will take ~{len(symbols_to_load) * 0.5:.0f} seconds. Continue? (y/n): ").strip().lower()
        if confirm != 'y':
            print("Cancelled")
            loader.close()
            return
    
    # Load data for each symbol
    success_count = 0
    failure_count = 0
    
    for i, symbol in enumerate(symbols_to_load):
        try:
            if loader.load_stock_data(symbol, start_date, end_date):
                success_count += 1
            else:
                failure_count += 1
            
            # Small delay to avoid rate limiting
            if i < len(symbols_to_load) - 1:
                time.sleep(0.5)
                
        except Exception as e:
            print(f"✗ Unexpected error for {symbol}: {e}")
            failure_count += 1
    
    # Summary
    print("\n" + "="*60)
    print("Loading Summary")
    print("="*60)
    print(f"✓ Successfully loaded: {success_count} stocks")
    print(f"✗ Failed: {failure_count} stocks")
    print(f"Total: {len(symbols_to_load)} stocks")
    
    if success_count > 0:
        print("\n✓ Next steps:")
        print("  1. Calculate indicators: python3 calculate_indicators.py")
        print("  2. Analyze stocks: python3 analyze_stocks.py")
        print("  3. Run backtest: python3 backtest_simple.py")
    
    # Close connection
    loader.close()
    print("\n✓ Data loading complete\n")


if __name__ == "__main__":
    main()
