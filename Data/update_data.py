"""
Incremental Data Updater
Updates historical data by fetching only missing dates since last update
Runs much faster than full reload - perfect for daily updates
"""

import os
import sys
from datetime import datetime, timedelta
from typing import Optional, List, Tuple
import pandas as pd
from pandas_datareader import data as pdr
import psycopg2
from psycopg2.extras import execute_values
from dotenv import load_dotenv
import time

# Load environment variables
load_dotenv()


class IncrementalUpdater:
    """Updates stock data incrementally - only fetches missing dates"""
    
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
    
    def get_stock_list(self) -> List[Tuple[int, str]]:
        """Get list of active stocks"""
        try:
            self.cursor.execute("""
                SELECT stock_id, symbol 
                FROM stocks 
                WHERE is_active = TRUE
                ORDER BY symbol
            """)
            return self.cursor.fetchall()
        except Exception as e:
            print(f"✗ Error fetching stock list: {e}")
            return []
    
    def get_latest_date(self, stock_id: int) -> Optional[datetime]:
        """Get the latest date for which we have data for this stock"""
        try:
            self.cursor.execute("""
                SELECT MAX(date) 
                FROM historical_prices 
                WHERE stock_id = %s
            """, (stock_id,))
            
            result = self.cursor.fetchone()
            latest_date = result[0] if result and result[0] else None
            
            return latest_date
            
        except Exception as e:
            print(f"  ✗ Error getting latest date: {e}")
            return None
    
    def get_date_range_to_fetch(self, stock_id: int) -> Optional[Tuple[str, str]]:
        """
        Determine the date range that needs to be fetched
        Returns (start_date, end_date) or None if no update needed
        """
        latest_date = self.get_latest_date(stock_id)
        
        # End date is yesterday (today's data not available yet)
        end_date = datetime.now() - timedelta(days=1)
        
        if latest_date is None:
            # No data exists - fetch from default start date
            start_date_str = os.getenv('START_DATE', '2020-01-01')
            start_date = datetime.strptime(start_date_str, '%Y-%m-%d')
            print(f"  ⚠ No existing data - will fetch from {start_date.date()}")
        else:
            # Start from day after latest data
            start_date = latest_date + timedelta(days=1)
            print(f"  ℹ Latest data: {latest_date.date()}")
        
        # Check if update is needed
        # Convert to date objects if they aren't already
        start_date_obj = start_date.date() if hasattr(start_date, 'date') else start_date
        end_date_obj = end_date.date() if hasattr(end_date, 'date') else end_date
        
        if start_date_obj >= end_date_obj:
            print(f"  ✓ Data is up to date (no new dates to fetch)")
            return None
        
        print(f"  → Need to fetch: {start_date_obj} to {end_date_obj}")
        
        # Convert to datetime if needed for strftime
        if not hasattr(start_date, 'strftime'):
            start_date = datetime.combine(start_date, datetime.min.time())
        if not hasattr(end_date, 'strftime'):
            end_date = datetime.combine(end_date, datetime.min.time())
            
        return (start_date.strftime('%Y-%m-%d'), end_date.strftime('%Y-%m-%d'))
    
    def fetch_data(self, symbol: str, start_date: str, end_date: str) -> Optional[pd.DataFrame]:
        """
        Fetch data using pandas_datareader with Yahoo Finance
        """
        try:
            # Try Yahoo Finance first
            yahoo_symbol = f"{symbol}.WA"
            print(f"  Fetching from Yahoo Finance: {yahoo_symbol}")
            
            try:
                import yfinance as yf
                df = yf.download(yahoo_symbol, start=start_date, end=end_date, progress=False)
            except:
                # Fallback to pandas_datareader
                df = pdr.DataReader(yahoo_symbol, 'yahoo', start=start_date, end=end_date)
            
            if df.empty:
                print(f"  ⚠ No data returned from Yahoo Finance")
                # Try Stooq as backup
                return self.fetch_data_stooq(symbol, start_date, end_date)
            
            # Reset index to get date as column
            df = df.reset_index()
            
            # Standardize column names (handle both formats)
            column_mapping = {
                'Date': 'date',
                'Open': 'open',
                'High': 'high',
                'Low': 'low',
                'Close': 'close',
                'Volume': 'volume',
                'Adj Close': 'adjusted_close'
            }
            df = df.rename(columns=column_mapping)
            
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
                print(f"  ⚠ No valid data after cleaning")
                return None
            
            print(f"  ✓ Retrieved {len(df)} records from {df['date'].min().date()} to {df['date'].max().date()}")
            return df
            
        except Exception as e:
            print(f"  ✗ Error fetching data from Yahoo: {str(e)[:100]}")
            # Try Stooq as backup
            return self.fetch_data_stooq(symbol, start_date, end_date)
    
    def fetch_data_stooq(self, symbol: str, start_date: str, end_date: str) -> Optional[pd.DataFrame]:
        """Fallback: fetch data from Stooq"""
        try:
            stooq_symbol = f"{symbol}.PL"
            print(f"  Trying Stooq as backup: {stooq_symbol}")
            
            df = pdr.DataReader(stooq_symbol, 'stooq', start=start_date, end=end_date)
            
            if df.empty:
                print(f"  ✗ No data from Stooq either")
                return None
            
            # Reset index and standardize
            df = df.reset_index()
            df = df.rename(columns={
                'Date': 'date',
                'Open': 'open',
                'High': 'high',
                'Low': 'low',
                'Close': 'close',
                'Volume': 'volume'
            })
            
            df = df[['date', 'open', 'high', 'low', 'close', 'volume']]
            df['date'] = pd.to_datetime(df['date'])
            if df['date'].dt.tz is not None:
                df['date'] = df['date'].dt.tz_localize(None)
            
            df = df.sort_values('date')
            
            for col in ['open', 'high', 'low', 'close']:
                df[col] = pd.to_numeric(df[col], errors='coerce')
            df['volume'] = pd.to_numeric(df['volume'], errors='coerce').fillna(0).astype(int)
            
            df = df.dropna(subset=['open', 'high', 'low', 'close'])
            
            if not df.empty:
                print(f"  ✓ Retrieved {len(df)} records from Stooq")
            
            return df if not df.empty else None
            
        except Exception as e:
            print(f"  ✗ Error fetching from Stooq: {str(e)[:100]}")
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
                    float(row.get('adjusted_close', row['close']))  # Use close if adj_close not available
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
    
    def update_stock(self, stock_id: int, symbol: str) -> bool:
        """Update a single stock with missing data"""
        print(f"\n{'='*60}")
        print(f"Updating {symbol} (ID: {stock_id})")
        print(f"{'='*60}")
        
        # Determine what date range to fetch
        date_range = self.get_date_range_to_fetch(stock_id)
        
        if date_range is None:
            return True  # Already up to date
        
        start_date, end_date = date_range
        
        # Fetch missing data
        df = self.fetch_data(symbol, start_date, end_date)
        
        if df is None or df.empty:
            print(f"  ✗ No new data retrieved")
            return False
        
        # Load data into database
        inserted, _ = self.load_historical_data(stock_id, df)
        
        return inserted > 0
    
    def update_all_stocks(self, delay_seconds: int = 1) -> dict:
        """Update all active stocks"""
        stocks = self.get_stock_list()
        
        if not stocks:
            print("✗ No active stocks found in database")
            return {'success': 0, 'skipped': 0, 'failed': 0}
        
        success_count = 0
        skipped_count = 0
        failed_count = 0
        
        for i, (stock_id, symbol) in enumerate(stocks):
            try:
                result = self.update_stock(stock_id, symbol)
                
                # Check if up to date (no fetch needed)
                latest_date = self.get_latest_date(stock_id)
                yesterday = (datetime.now() - timedelta(days=1)).date()
                
                if latest_date and latest_date.date() >= yesterday:
                    skipped_count += 1
                elif result:
                    success_count += 1
                else:
                    failed_count += 1
                
                # Small delay to avoid rate limiting
                if i < len(stocks) - 1:
                    time.sleep(delay_seconds)
                    
            except Exception as e:
                print(f"✗ Unexpected error for {symbol}: {e}")
                failed_count += 1
        
        return {
            'success': success_count,
            'skipped': skipped_count,
            'failed': failed_count,
            'total': len(stocks)
        }


def main():
    """Main execution function"""
    print("\n" + "="*60)
    print("Incremental Data Updater")
    print("Fetches only missing data since last update")
    print("="*60 + "\n")
    
    # Initialize updater
    updater = IncrementalUpdater()
    updater.connect()
    
    # Get current time for reporting
    update_time = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    print(f"Update started: {update_time}\n")
    
    # Option to update single stock or all
    print("Update mode:")
    print("1. Update all stocks (recommended for daily updates)")
    print("2. Update single stock")
    print("3. Check status only (no updates)")
    
    choice = input("\nEnter choice (1-3) [default: 1]: ").strip() or "1"
    
    if choice == "1":
        # Update all stocks
        print("\nUpdating all stocks...\n")
        results = updater.update_all_stocks()
        
        # Summary
        print("\n" + "="*60)
        print("Update Summary")
        print("="*60)
        print(f"✓ Successfully updated: {results['success']} stocks")
        print(f"⊙ Already up to date: {results['skipped']} stocks")
        print(f"✗ Failed: {results['failed']} stocks")
        print(f"Total: {results['total']} stocks")
        
        if results['success'] > 0:
            print("\n⚠ Don't forget to recalculate indicators:")
            print("   python3 calculate_indicators.py")
        
    elif choice == "2":
        # Update single stock
        symbol = input("Enter stock symbol (e.g., PKO): ").strip().upper()
        
        updater.cursor.execute(
            "SELECT stock_id FROM stocks WHERE symbol = %s",
            (symbol,)
        )
        result = updater.cursor.fetchone()
        
        if result:
            stock_id = result[0]
            success = updater.update_stock(stock_id, symbol)
            
            if success:
                print(f"\n✓ {symbol} updated successfully")
                print("\n⚠ Don't forget to recalculate indicators:")
                print(f"   python3 calculate_indicators.py")
            else:
                print(f"\n✗ Failed to update {symbol}")
        else:
            print(f"\n✗ Stock '{symbol}' not found in database")
    
    else:
        # Just check status
        print("\nChecking status for all stocks...\n")
        stocks = updater.get_stock_list()
        
        print(f"{'Symbol':<10} {'Latest Date':<15} {'Status'}")
        print("-" * 60)
        
        yesterday = (datetime.now() - timedelta(days=1)).date()
        
        for stock_id, symbol in stocks:
            latest_date = updater.get_latest_date(stock_id)
            
            if latest_date is None:
                status = "NO DATA"
                date_str = "N/A"
            elif latest_date.date() >= yesterday:
                status = "✓ UP TO DATE"
                date_str = str(latest_date.date())
            else:
                days_behind = (yesterday - latest_date.date()).days
                status = f"⚠ {days_behind} days behind"
                date_str = str(latest_date.date())
            
            print(f"{symbol:<10} {date_str:<15} {status}")
    
    # Close connection
    updater.close()
    print("\n✓ Update complete\n")


if __name__ == "__main__":
    main()
