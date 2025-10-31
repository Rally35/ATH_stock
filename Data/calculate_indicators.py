"""
Technical Indicators Calculator for Polish Stocks
Calculates RSI, MACD, SMA, EMA, ATR, ATH proximity and other momentum indicators
"""

import os
import sys
from datetime import datetime, timedelta
from typing import Optional, Dict, List
import pandas as pd
import numpy as np
import psycopg2
from psycopg2.extras import execute_values
from dotenv import load_dotenv

# Load environment variables
load_dotenv()


class IndicatorCalculator:
    """Calculates and stores technical indicators for momentum trading"""
    
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
    
    def get_stock_list(self) -> List[tuple]:
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
    
    def get_historical_prices(self, stock_id: int, lookback_days: int = 730) -> Optional[pd.DataFrame]:
        """
        Fetch historical price data for a stock
        Lookback period: 730 days (2 years) to ensure enough data for 200-day SMA
        """
        try:
            # Get data from the last N days
            query = """
                SELECT date, open, high, low, close, volume
                FROM historical_prices
                WHERE stock_id = %s
                ORDER BY date ASC
            """
            
            df = pd.read_sql_query(query, self.conn, params=(stock_id,))
            
            if df.empty:
                return None
            
            # Convert date to datetime
            df['date'] = pd.to_datetime(df['date'])
            df = df.set_index('date')
            
            # Ensure numeric types
            for col in ['open', 'high', 'low', 'close']:
                df[col] = pd.to_numeric(df[col], errors='coerce')
            df['volume'] = pd.to_numeric(df['volume'], errors='coerce').fillna(0).astype(int)
            
            return df
            
        except Exception as e:
            print(f"  ✗ Error fetching prices: {e}")
            return None
    
    def calculate_rsi(self, prices: pd.Series, period: int = 14) -> pd.Series:
        """
        Calculate RSI (Relative Strength Index)
        RSI = 100 - (100 / (1 + RS))
        RS = Average Gain / Average Loss
        """
        delta = prices.diff()
        gain = (delta.where(delta > 0, 0)).fillna(0)
        loss = (-delta.where(delta < 0, 0)).fillna(0)
        
        avg_gain = gain.rolling(window=period, min_periods=period).mean()
        avg_loss = loss.rolling(window=period, min_periods=period).mean()
        
        rs = avg_gain / avg_loss
        rsi = 100 - (100 / (1 + rs))
        
        return rsi
    
    def calculate_sma(self, prices: pd.Series, period: int) -> pd.Series:
        """Calculate Simple Moving Average"""
        return prices.rolling(window=period, min_periods=period).mean()
    
    def calculate_ema(self, prices: pd.Series, period: int) -> pd.Series:
        """Calculate Exponential Moving Average"""
        return prices.ewm(span=period, adjust=False).mean()
    
    def calculate_macd(self, prices: pd.Series, fast: int = 12, slow: int = 26, signal: int = 9) -> Dict[str, pd.Series]:
        """
        Calculate MACD (Moving Average Convergence Divergence)
        MACD = EMA(12) - EMA(26)
        Signal = EMA(9) of MACD
        Histogram = MACD - Signal
        """
        ema_fast = self.calculate_ema(prices, fast)
        ema_slow = self.calculate_ema(prices, slow)
        
        macd = ema_fast - ema_slow
        macd_signal = self.calculate_ema(macd, signal)
        macd_histogram = macd - macd_signal
        
        return {
            'macd': macd,
            'macd_signal': macd_signal,
            'macd_histogram': macd_histogram
        }
    
    def calculate_atr(self, df: pd.DataFrame, period: int = 14) -> pd.Series:
        """
        Calculate ATR (Average True Range)
        TR = max(high - low, abs(high - prev_close), abs(low - prev_close))
        ATR = EMA of TR
        """
        high = df['high']
        low = df['low']
        close = df['close']
        prev_close = close.shift(1)
        
        tr1 = high - low
        tr2 = abs(high - prev_close)
        tr3 = abs(low - prev_close)
        
        tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
        atr = tr.rolling(window=period, min_periods=period).mean()
        
        return atr
    
    def calculate_ath_metrics(self, prices: pd.Series) -> Dict[str, pd.Series]:
        """
        Calculate All-Time High metrics for different periods
        Returns ATH values and distance from current ATH
        """
        # Calculate rolling ATH for different periods
        ath_1y = prices.rolling(window=252, min_periods=100).max()  # ~1 year trading days
        ath_2y = prices.rolling(window=504, min_periods=200).max()  # ~2 years
        ath_5y = prices.rolling(window=1260, min_periods=500).max() # ~5 years
        ath_all_time = prices.expanding().max()
        
        # Distance from 5-year ATH (as percentage)
        distance_from_ath_5y = (prices - ath_5y) / ath_5y
        
        return {
            'ath_1y': ath_1y,
            'ath_2y': ath_2y,
            'ath_5y': ath_5y,
            'ath_all_time': ath_all_time,
            'distance_from_ath_5y': distance_from_ath_5y
        }
    
    def calculate_volume_ma(self, volume: pd.Series, period: int = 20) -> pd.Series:
        """Calculate Volume Moving Average"""
        return volume.rolling(window=period, min_periods=period).mean()
    
    def calculate_all_indicators(self, df: pd.DataFrame) -> pd.DataFrame:
        """Calculate all technical indicators for a given price dataframe"""
        try:
            indicators = pd.DataFrame(index=df.index)
            
            # RSI
            indicators['rsi_14'] = self.calculate_rsi(df['close'], 14)
            
            # Moving Averages
            indicators['sma_50'] = self.calculate_sma(df['close'], 50)
            indicators['sma_200'] = self.calculate_sma(df['close'], 200)
            indicators['ema_20'] = self.calculate_ema(df['close'], 20)
            
            # MACD
            macd_data = self.calculate_macd(df['close'])
            indicators['macd'] = macd_data['macd']
            indicators['macd_signal'] = macd_data['macd_signal']
            indicators['macd_histogram'] = macd_data['macd_histogram']
            
            # ATR
            indicators['atr_14'] = self.calculate_atr(df, 14)
            
            # Volume MA
            indicators['volume_ma_20'] = self.calculate_volume_ma(df['volume'], 20)
            
            # ATH Metrics
            ath_data = self.calculate_ath_metrics(df['close'])
            indicators['ath_1y'] = ath_data['ath_1y']
            indicators['ath_2y'] = ath_data['ath_2y']
            indicators['ath_5y'] = ath_data['ath_5y']
            indicators['ath_all_time'] = ath_data['ath_all_time']
            indicators['distance_from_ath_5y'] = ath_data['distance_from_ath_5y']
            
            # Reset index to get date as column
            indicators = indicators.reset_index()
            
            return indicators
            
        except Exception as e:
            print(f"  ✗ Error calculating indicators: {e}")
            return pd.DataFrame()
    
    def store_indicators(self, stock_id: int, indicators_df: pd.DataFrame) -> int:
        """Store calculated indicators in database"""
        try:
            # Filter out rows where all indicators are NaN (not enough data yet)
            # Keep rows where at least one indicator has a value
            indicators_df = indicators_df.dropna(subset=[
                'rsi_14', 'sma_50', 'macd', 'atr_14', 'ath_1y'
            ], how='all')
            
            if indicators_df.empty:
                print(f"  ⚠ No valid indicators to store (need more historical data)")
                return 0
            
            # Prepare records for insertion
            records = []
            for _, row in indicators_df.iterrows():
                records.append((
                    stock_id,
                    row['date'].date() if hasattr(row['date'], 'date') else row['date'],
                    float(row['rsi_14']) if pd.notna(row['rsi_14']) else None,
                    float(row['sma_50']) if pd.notna(row['sma_50']) else None,
                    float(row['sma_200']) if pd.notna(row['sma_200']) else None,
                    float(row['ema_20']) if pd.notna(row['ema_20']) else None,
                    float(row['macd']) if pd.notna(row['macd']) else None,
                    float(row['macd_signal']) if pd.notna(row['macd_signal']) else None,
                    float(row['macd_histogram']) if pd.notna(row['macd_histogram']) else None,
                    float(row['atr_14']) if pd.notna(row['atr_14']) else None,
                    int(row['volume_ma_20']) if pd.notna(row['volume_ma_20']) else None,
                    float(row['ath_1y']) if pd.notna(row['ath_1y']) else None,
                    float(row['ath_2y']) if pd.notna(row['ath_2y']) else None,
                    float(row['ath_5y']) if pd.notna(row['ath_5y']) else None,
                    float(row['ath_all_time']) if pd.notna(row['ath_all_time']) else None,
                    float(row['distance_from_ath_5y']) if pd.notna(row['distance_from_ath_5y']) else None,
                ))
            
            # Upsert query
            insert_query = """
                INSERT INTO technical_indicators 
                (stock_id, date, rsi_14, sma_50, sma_200, ema_20, macd, macd_signal, 
                 macd_histogram, atr_14, volume_ma_20, ath_1y, ath_2y, ath_5y, 
                 ath_all_time, distance_from_ath_5y)
                VALUES %s
                ON CONFLICT (stock_id, date) 
                DO UPDATE SET
                    rsi_14 = EXCLUDED.rsi_14,
                    sma_50 = EXCLUDED.sma_50,
                    sma_200 = EXCLUDED.sma_200,
                    ema_20 = EXCLUDED.ema_20,
                    macd = EXCLUDED.macd,
                    macd_signal = EXCLUDED.macd_signal,
                    macd_histogram = EXCLUDED.macd_histogram,
                    atr_14 = EXCLUDED.atr_14,
                    volume_ma_20 = EXCLUDED.volume_ma_20,
                    ath_1y = EXCLUDED.ath_1y,
                    ath_2y = EXCLUDED.ath_2y,
                    ath_5y = EXCLUDED.ath_5y,
                    ath_all_time = EXCLUDED.ath_all_time,
                    distance_from_ath_5y = EXCLUDED.distance_from_ath_5y,
                    computed_at = CURRENT_TIMESTAMP
            """
            
            execute_values(self.cursor, insert_query, records)
            self.conn.commit()
            
            print(f"  ✓ Stored {len(records)} indicator records")
            return len(records)
            
        except Exception as e:
            self.conn.rollback()
            print(f"  ✗ Error storing indicators: {e}")
            return 0
    
    def process_stock(self, stock_id: int, symbol: str) -> bool:
        """Process a single stock: fetch data, calculate indicators, store results"""
        print(f"\n{'='*60}")
        print(f"Processing {symbol} (ID: {stock_id})")
        print(f"{'='*60}")
        
        # Fetch historical prices
        df = self.get_historical_prices(stock_id)
        
        if df is None or df.empty:
            print(f"  ✗ No price data available")
            return False
        
        print(f"  ✓ Loaded {len(df)} price records")
        print(f"  Date range: {df.index.min().date()} to {df.index.max().date()}")
        
        # Calculate indicators
        indicators_df = self.calculate_all_indicators(df)
        
        if indicators_df.empty:
            print(f"  ✗ Failed to calculate indicators")
            return False
        
        print(f"  ✓ Calculated indicators for {len(indicators_df)} dates")
        
        # Store in database
        stored = self.store_indicators(stock_id, indicators_df)
        
        return stored > 0
    
    def get_summary_stats(self) -> Dict:
        """Get summary statistics of calculated indicators"""
        try:
            self.cursor.execute("""
                SELECT 
                    COUNT(DISTINCT stock_id) as stocks_with_indicators,
                    COUNT(*) as total_indicator_records,
                    MIN(date) as earliest_date,
                    MAX(date) as latest_date
                FROM technical_indicators
            """)
            result = self.cursor.fetchone()
            
            return {
                'stocks_with_indicators': result[0],
                'total_records': result[1],
                'earliest_date': result[2],
                'latest_date': result[3]
            }
        except:
            return {}


def main():
    """Main execution function"""
    print("\n" + "="*60)
    print("Technical Indicators Calculator")
    print("Momentum Trading System for Polish Stocks")
    print("="*60 + "\n")
    
    # Initialize calculator
    calc = IndicatorCalculator()
    calc.connect()
    
    # Get list of stocks
    stocks = calc.get_stock_list()
    
    if not stocks:
        print("✗ No active stocks found in database")
        print("  Run load_data.py first to load historical prices")
        calc.close()
        sys.exit(1)
    
    print(f"Found {len(stocks)} active stocks to process\n")
    
    # Process each stock
    success_count = 0
    failure_count = 0
    
    for stock_id, symbol in stocks:
        try:
            if calc.process_stock(stock_id, symbol):
                success_count += 1
            else:
                failure_count += 1
        except Exception as e:
            print(f"✗ Unexpected error for {symbol}: {e}")
            failure_count += 1
    
    # Summary
    print("\n" + "="*60)
    print("Calculation Summary")
    print("="*60)
    print(f"✓ Successfully processed: {success_count} stocks")
    print(f"✗ Failed: {failure_count} stocks")
    print(f"Total: {len(stocks)} stocks")
    
    # Get database stats
    stats = calc.get_summary_stats()
    if stats:
        print("\nDatabase Statistics:")
        print(f"  Stocks with indicators: {stats['stocks_with_indicators']}")
        print(f"  Total indicator records: {stats['total_records']:,}")
        if stats['earliest_date'] and stats['latest_date']:
            print(f"  Date range: {stats['earliest_date']} to {stats['latest_date']}")
    
    # Close connection
    calc.close()
    print("\n✓ Indicator calculation complete\n")


if __name__ == "__main__":
    main()
