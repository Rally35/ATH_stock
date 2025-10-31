"""
Stock Analysis & Screening Tool
Analyze current momentum signals and find trading opportunities
"""

import os
import sys
import pandas as pd
import psycopg2
from dotenv import load_dotenv
from datetime import datetime, timedelta

load_dotenv()


class StockAnalyzer:
    """Analyze stocks for momentum trading opportunities"""
    
    def __init__(self):
        self.conn_params = {
            'host': os.getenv('DB_HOST', 'localhost'),
            'port': os.getenv('DB_PORT', '5432'),
            'database': os.getenv('DB_NAME', 'polish_stocks'),
            'user': os.getenv('DB_USER', 'trader'),
            'password': os.getenv('DB_PASSWORD', 'change_me_in_production')
        }
        self.conn = None
        
    def connect(self):
        """Establish database connection"""
        try:
            self.conn = psycopg2.connect(**self.conn_params)
            print("✓ Database connection established\n")
        except Exception as e:
            print(f"✗ Database connection failed: {e}")
            sys.exit(1)
    
    def close(self):
        """Close database connection"""
        if self.conn:
            self.conn.close()
    
    def get_momentum_signals(self, days_back: int = 30) -> pd.DataFrame:
        """
        Get stocks with momentum signals
        Criteria: RSI > 50, SMA50 > SMA200, within 5% of ATH
        """
        query = """
            SELECT 
                s.symbol,
                s.name,
                ti.date,
                hp.close as price,
                ti.rsi_14,
                ti.sma_50,
                ti.sma_200,
                ti.distance_from_ath_5y,
                ti.ath_5y,
                hp.volume,
                ti.volume_ma_20,
                ti.macd,
                ti.macd_signal,
                CASE 
                    WHEN ti.rsi_14 > 50 
                         AND ti.sma_50 > ti.sma_200 
                         AND ti.distance_from_ath_5y >= -0.05 
                    THEN TRUE 
                    ELSE FALSE 
                END as momentum_signal
            FROM stocks s
            JOIN historical_prices hp ON s.stock_id = hp.stock_id
            JOIN technical_indicators ti ON ti.stock_id = s.stock_id 
                AND ti.date = hp.date
            WHERE s.is_active = TRUE
                AND ti.date >= CURRENT_DATE - INTERVAL '%s days'
            ORDER BY ti.date DESC, s.symbol
        """
        
        df = pd.read_sql_query(query, self.conn, params=(days_back,))
        return df
    
    def get_latest_signals(self) -> pd.DataFrame:
        """Get latest momentum signals for all stocks"""
        query = """
            SELECT * FROM latest_stock_data
            ORDER BY 
                momentum_signal DESC,
                distance_from_ath_5y DESC,
                symbol
        """
        
        df = pd.read_sql_query(query, self.conn)
        return df
    
    def get_near_ath_stocks(self, threshold: float = 0.05) -> pd.DataFrame:
        """Find stocks near all-time highs"""
        query = """
            SELECT 
                s.symbol,
                s.name,
                hp.date,
                hp.close,
                ti.ath_5y,
                ti.distance_from_ath_5y,
                ti.rsi_14,
                ti.macd,
                hp.volume,
                ti.volume_ma_20
            FROM stocks s
            JOIN LATERAL (
                SELECT * FROM historical_prices 
                WHERE stock_id = s.stock_id 
                ORDER BY date DESC 
                LIMIT 1
            ) hp ON TRUE
            JOIN technical_indicators ti ON ti.stock_id = s.stock_id 
                AND ti.date = hp.date
            WHERE ti.distance_from_ath_5y >= %s
            ORDER BY ti.distance_from_ath_5y DESC
        """
        
        df = pd.read_sql_query(query, self.conn, params=(-threshold,))
        return df
    
    def get_golden_crosses(self) -> pd.DataFrame:
        """Find stocks with recent golden cross (SMA50 > SMA200)"""
        query = """
            WITH latest_data AS (
                SELECT 
                    s.stock_id,
                    s.symbol,
                    s.name,
                    ti.date,
                    ti.sma_50,
                    ti.sma_200,
                    hp.close,
                    ti.rsi_14,
                    LAG(ti.sma_50) OVER (PARTITION BY s.stock_id ORDER BY ti.date) as prev_sma_50,
                    LAG(ti.sma_200) OVER (PARTITION BY s.stock_id ORDER BY ti.date) as prev_sma_200
                FROM stocks s
                JOIN historical_prices hp ON s.stock_id = hp.stock_id
                JOIN technical_indicators ti ON ti.stock_id = s.stock_id 
                    AND ti.date = hp.date
                WHERE s.is_active = TRUE
                    AND ti.date >= CURRENT_DATE - INTERVAL '60 days'
                    AND ti.sma_50 IS NOT NULL
                    AND ti.sma_200 IS NOT NULL
            )
            SELECT 
                symbol,
                name,
                date,
                close,
                sma_50,
                sma_200,
                rsi_14
            FROM latest_data
            WHERE sma_50 > sma_200 
                AND prev_sma_50 <= prev_sma_200
            ORDER BY date DESC
        """
        
        df = pd.read_sql_query(query, self.conn)
        return df
    
    def get_stock_statistics(self) -> pd.DataFrame:
        """Get overall statistics for all stocks"""
        query = """
            SELECT 
                s.symbol,
                s.name,
                COUNT(hp.price_id) as total_days,
                MIN(hp.date) as first_date,
                MAX(hp.date) as last_date,
                ROUND(AVG(hp.volume)::numeric, 0) as avg_volume,
                MIN(hp.close) as min_price,
                MAX(hp.close) as max_price,
                (SELECT close FROM historical_prices 
                 WHERE stock_id = s.stock_id 
                 ORDER BY date DESC LIMIT 1) as latest_price
            FROM stocks s
            LEFT JOIN historical_prices hp ON s.stock_id = hp.stock_id
            WHERE s.is_active = TRUE
            GROUP BY s.stock_id, s.symbol, s.name
            ORDER BY s.symbol
        """
        
        df = pd.read_sql_query(query, self.conn)
        return df
    
    def print_header(self, title: str):
        """Print formatted header"""
        print("\n" + "="*80)
        print(f" {title}")
        print("="*80)
    
    def print_dataframe(self, df: pd.DataFrame, title: str, max_rows: int = 20):
        """Print formatted dataframe"""
        self.print_header(title)
        
        if df.empty:
            print("No data found")
            return
        
        # Configure pandas display
        pd.set_option('display.max_columns', None)
        pd.set_option('display.width', None)
        pd.set_option('display.max_colwidth', 30)
        
        print(f"\nShowing {min(len(df), max_rows)} of {len(df)} records\n")
        print(df.head(max_rows).to_string(index=False))
        
        if len(df) > max_rows:
            print(f"\n... and {len(df) - max_rows} more rows")


def main():
    """Main analysis function"""
    print("\n" + "="*80)
    print(" Polish Stocks - Momentum Analysis & Screening")
    print("="*80)
    print(f" Analysis Date: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    
    analyzer = StockAnalyzer()
    analyzer.connect()
    
    # 1. Database Statistics
    stats_df = analyzer.get_stock_statistics()
    analyzer.print_dataframe(stats_df, "📊 Stock Statistics Overview", max_rows=50)
    
    # 2. Current Momentum Signals
    latest_df = analyzer.get_latest_signals()
    momentum_stocks = latest_df[latest_df['momentum_signal'] == True]
    
    analyzer.print_header("🚀 Current Momentum Signals")
    if not momentum_stocks.empty:
        print(f"\n✓ Found {len(momentum_stocks)} stocks with momentum signals!\n")
        print(momentum_stocks[['symbol', 'name', 'close', 'rsi_14', 
                               'distance_from_ath_5y']].to_string(index=False))
    else:
        print("\n⚠ No stocks currently showing momentum signals")
        print("Criteria: RSI > 50, SMA50 > SMA200, within 5% of 5Y ATH")
    
    # 3. Stocks Near ATH
    near_ath_df = analyzer.get_near_ath_stocks(threshold=0.10)
    analyzer.print_header("📈 Stocks Near All-Time High (within 10%)")
    if not near_ath_df.empty:
        print(f"\n✓ Found {len(near_ath_df)} stocks near ATH\n")
        display_df = near_ath_df[['symbol', 'name', 'close', 'ath_5y', 
                                   'distance_from_ath_5y', 'rsi_14']].copy()
        display_df['distance_from_ath_5y'] = display_df['distance_from_ath_5y'].apply(
            lambda x: f"{x*100:.2f}%"
        )
        print(display_df.head(20).to_string(index=False))
    else:
        print("\nNo stocks within 10% of ATH")
    
    # 4. Recent Golden Crosses
    golden_df = analyzer.get_golden_crosses()
    analyzer.print_header("✨ Recent Golden Crosses (Last 60 Days)")
    if not golden_df.empty:
        print(f"\n✓ Found {len(golden_df)} golden crosses\n")
        print(golden_df[['symbol', 'name', 'date', 'close', 
                        'rsi_14']].to_string(index=False))
    else:
        print("\nNo recent golden crosses")
    
    # 5. Summary & Recommendations
    analyzer.print_header("💡 Summary & Recommendations")
    
    total_stocks = len(stats_df)
    momentum_count = len(momentum_stocks)
    near_ath_count = len(near_ath_df)
    golden_count = len(golden_df)
    
    print(f"""
Summary:
  • Total Active Stocks: {total_stocks}
  • Momentum Signals: {momentum_count}
  • Near ATH (10%): {near_ath_count}
  • Recent Golden Crosses: {golden_count}

Recommendations:
""")
    
    if momentum_count > 0:
        print("  ✓ STRONG: Focus on stocks with momentum signals")
        print(f"    → Review: {', '.join(momentum_stocks['symbol'].head(5).tolist())}")
    
    if near_ath_count > 5:
        print(f"  ✓ OPPORTUNITY: {near_ath_count} stocks approaching breakout levels")
        print("    → Watch for volume confirmation on ATH breaks")
    
    if golden_count > 0:
        print(f"  ✓ TREND CHANGE: {golden_count} recent bullish crossovers")
        print("    → These may develop into momentum plays")
    
    if momentum_count == 0 and near_ath_count == 0:
        print("  ⚠ CAUTION: Limited momentum opportunities currently")
        print("    → Wait for better setups or consider defensive positioning")
    
    print("\nNext Steps:")
    print("  1. Run backtest on momentum strategy: python3 backtest_simple.py")
    print("  2. Set up alerts for ATH breakouts")
    print("  3. Review individual stock charts for confirmation")
    
    analyzer.close()
    print("\n" + "="*80 + "\n")


if __name__ == "__main__":
    main()
