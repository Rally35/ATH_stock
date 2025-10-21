"""
Historical Data Loader using pandas_datareader for Polish Stocks
Uses pandas_datareader with Stooq backend - the proper way to access Stooq data
"""

import os
import sys
from datetime import datetime
from typing import Optional, Tuple
import pandas as pd
from pandas_datareader import data as pdr
import psycopg2
from psycopg2.extras import execute_values
from dotenv import load_dotenv
import time

# Load environment variables
load_dotenv()


class DataReaderLoader:
    """Handles loading historical stock data using pandas_datareader"""
    
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
    
    def fetch_data_pandas_datareader(self, symbol: str, start_date: str, end_date: str) -> Optional[pd.DataFrame]:
        """
        Fetch data using pandas_datareader with Stooq backend
        This is the official way to access Stooq data programmatically
        """
        try:
            stooq_symbol = f"{symbol}.PL"
            print(f"  Fetching via pandas_datareader (Stooq): {stooq_symbol}")
            
            # Use pandas_datareader with Stooq
            df = pdr.DataReader(
                stooq_symbol,
                'stooq',
                start=start_date,
                end=end_date
            )
            
            if df.empty:
                print(f"  ⚠ No data returned for {symbol}")
                return None
            
            # Reset index to get date as column
            df = df.reset_index()
            
            # Rename columns to standard format
            df = df.rename(columns={
                'Date': 'date',
                'Open': 'open',
                'High': 'high',
                'Low': 'low',
                'Close': 'close',
                'Volume': 'volume'
            })
            
            # Select only needed columns
            df = df[['date', 'open', 'high', 'low', 'close', 'volume']]
            
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
                print(f"  ⚠ No valid data after cleaning for {symbol}")
                return None
            
            print(f"  ✓ Retrieved {len(df)} records from {df['date'].min().date()} to {df['date'].max().date()}")
            return df
            
        except Exception as e:
            print(f"  ✗ Error fetching data for {symbol}: {str(e)[:100]}")
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
                    float(row['close'])
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
    
    def log_data_quality(self, stock_id: int, log_type: str, severity: str, message: str, details: dict = None):
        """Log data quality issues"""
        try:
            import json
            self.cursor.execute(
                """
                INSERT INTO data_quality_log (stock_id, log_type, severity, message, details)
                VALUES (%s, %s, %s, %s, %s)
                """,
                (stock_id, log_type, severity, message, json.dumps(details) if details else None)
            )
            self.conn.commit()
        except:
            pass
    
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
        df = self.fetch_data_pandas_datareader(symbol, start_date, end_date)
        
        if df is None or df.empty:
            self.log_data_quality(
                stock_id, 'data_load', 'error',
                f'No data retrieved',
                {'symbol': symbol, 'date_range': f'{start_date} to {end_date}'}
            )
            return False
        
        # Load data into database
        inserted, _ = self.load_historical_data(stock_id, df)
        
        if inserted > 0:
            self.log_data_quality(
                stock_id, 'data_load', 'info',
                f'Successfully loaded {inserted} records',
                {'symbol': symbol, 'records': inserted}
            )
            return True
        
        return False


def main():
    """Main execution function"""
    print("\n" + "="*60)
    print("Polish Stocks Data Loader")
    print("Using pandas_datareader with Stooq backend")
    print("="*60 + "\n")
    
    # Configuration
    start_date = os.getenv('START_DATE', '2020-01-01')
    end_date = os.getenv('END_DATE', datetime.now().strftime('%Y-%m-%d'))
    symbols_str = os.getenv('STOCK_SYMBOLS', 'PKO,PZU,KGH')
    
    symbols = [s.strip() for s in symbols_str.split(',')]
    
    print(f"Configuration:")
    print(f"  Date Range: {start_date} to {end_date}")
    print(f"  Symbols: {', '.join(symbols)}")
    print(f"  Method: pandas_datareader + Stooq\n")
    
    # Initialize loader
    loader = DataReaderLoader()
    loader.connect()
    
    # Load data for each symbol
    success_count = 0
    failure_count = 0
    
    for i, symbol in enumerate(symbols):
        try:
            if loader.load_stock_data(symbol, start_date, end_date):
                success_count += 1
            else:
                failure_count += 1
            
            # Small delay to avoid rate limiting
            if i < len(symbols) - 1:
                time.sleep(1)
                
        except Exception as e:
            print(f"✗ Unexpected error for {symbol}: {e}")
            failure_count += 1
    
    # Summary
    print("\n" + "="*60)
    print("Loading Summary")
    print("="*60)
    print(f"✓ Successfully loaded: {success_count} stocks")
    print(f"✗ Failed: {failure_count} stocks")
    print(f"Total: {len(symbols)} stocks")
    
    # Close connection
    loader.close()
    print("\n✓ Data loading complete\n")


if __name__ == "__main__":
    main()