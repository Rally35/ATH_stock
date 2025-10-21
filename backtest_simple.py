"""
Simple Momentum Strategy Backtest
Tests the basic momentum strategy on historical data
"""

import os
import sys
import pandas as pd
import numpy as np
import psycopg2
from dotenv import load_dotenv
from datetime import datetime
from typing import Dict, List, Tuple

load_dotenv()


class MomentumBacktest:
    """Simple backtest for momentum trading strategy"""
    
    def __init__(self, initial_capital: float = 100000.0):
        """Initialize backtest with starting capital (default: 100k PLN)"""
        self.conn_params = {
            'host': os.getenv('DB_HOST', 'localhost'),
            'port': os.getenv('DB_PORT', '5432'),
            'database': os.getenv('DB_NAME', 'polish_stocks'),
            'user': os.getenv('DB_USER', 'trader'),
            'password': os.getenv('DB_PASSWORD', 'change_me_in_production')
        }
        self.conn = None
        self.initial_capital = initial_capital
        
    def connect(self):
        """Establish database connection"""
        try:
            self.conn = psycopg2.connect(**self.conn_params)
            print("✓ Database connection established")
        except Exception as e:
            print(f"✗ Database connection failed: {e}")
            sys.exit(1)
    
    def close(self):
        """Close database connection"""
        if self.conn:
            self.conn.close()
    
    def get_backtest_data(self, start_date: str, end_date: str) -> pd.DataFrame:
        """
        Get all necessary data for backtesting
        Returns: DataFrame with prices and indicators for all stocks
        """
        query = """
            SELECT 
                s.symbol,
                hp.date,
                hp.close,
                hp.volume,
                ti.rsi_14,
                ti.sma_50,
                ti.sma_200,
                ti.distance_from_ath_5y,
                ti.atr_14,
                ti.volume_ma_20,
                CASE 
                    WHEN ti.rsi_14 > 50 
                         AND ti.sma_50 > ti.sma_200 
                         AND ti.distance_from_ath_5y >= -0.05 
                    THEN TRUE 
                    ELSE FALSE 
                END as signal
            FROM stocks s
            JOIN historical_prices hp ON s.stock_id = hp.stock_id
            LEFT JOIN technical_indicators ti ON ti.stock_id = s.stock_id 
                AND ti.date = hp.date
            WHERE s.is_active = TRUE
                AND hp.date BETWEEN %s AND %s
                AND ti.rsi_14 IS NOT NULL
            ORDER BY hp.date, s.symbol
        """
        
        df = pd.read_sql_query(query, self.conn, params=(start_date, end_date))
        df['date'] = pd.to_datetime(df['date'])
        return df
    
    def calculate_position_size(self, capital: float, atr: float, 
                                price: float, risk_percent: float = 0.02) -> int:
        """
        Calculate position size based on ATR
        Risk 2% of capital per trade (adjustable)
        Stop loss at 2x ATR
        """
        if pd.isna(atr) or atr == 0:
            return 0
        
        risk_amount = capital * risk_percent
        stop_distance = 2 * atr  # 2x ATR stop
        
        if stop_distance == 0 or price == 0:
            return 0
        
        shares = int(risk_amount / stop_distance)
        
        # Don't use more than 20% of capital on one position
        max_shares = int((capital * 0.20) / price)
        
        return min(shares, max_shares)
    
    def run_backtest(self, df: pd.DataFrame, max_positions: int = 5) -> Dict:
        """
        Run simple momentum backtest
        Rules:
        - Buy when momentum signal appears
        - Hold max N positions at once
        - Exit when signal disappears OR stop loss hit
        - Position sizing based on ATR
        """
        capital = self.initial_capital
        positions = {}  # {symbol: {'shares': N, 'entry_price': X, 'entry_date': date, 'stop': Y}}
        trades = []
        equity_curve = []
        
        dates = sorted(df['date'].unique())
        
        print(f"\n{'='*60}")
        print(f"Running Backtest")
        print(f"{'='*60}")
        print(f"Period: {dates[0].date()} to {dates[-1].date()}")
        print(f"Initial Capital: {self.initial_capital:,.2f} PLN")
        print(f"Max Positions: {max_positions}")
        print(f"Risk per Trade: 2% of capital")
        print(f"Stop Loss: 2x ATR\n")
        
        for date in dates:
            day_data = df[df['date'] == date]
            
            # Calculate current portfolio value
            portfolio_value = capital
            for symbol, pos in positions.items():
                current_price = day_data[day_data['symbol'] == symbol]['close'].values
                if len(current_price) > 0:
                    portfolio_value += pos['shares'] * current_price[0]
            
            equity_curve.append({
                'date': date,
                'equity': portfolio_value
            })
            
            # Check exits (stop loss or signal exit)
            exits = []
            for symbol, pos in positions.items():
                stock_data = day_data[day_data['symbol'] == symbol]
                
                if len(stock_data) == 0:
                    continue
                
                current_price = stock_data['close'].values[0]
                has_signal = stock_data['signal'].values[0]
                
                # Exit conditions
                exit_reason = None
                if current_price <= pos['stop']:
                    exit_reason = 'STOP_LOSS'
                elif not has_signal:
                    exit_reason = 'SIGNAL_EXIT'
                
                if exit_reason:
                    # Execute exit
                    exit_value = pos['shares'] * current_price
                    capital += exit_value
                    
                    pnl = exit_value - (pos['shares'] * pos['entry_price'])
                    pnl_pct = (pnl / (pos['shares'] * pos['entry_price'])) * 100
                    
                    trades.append({
                        'symbol': symbol,
                        'entry_date': pos['entry_date'],
                        'exit_date': date,
                        'entry_price': pos['entry_price'],
                        'exit_price': current_price,
                        'shares': pos['shares'],
                        'pnl': pnl,
                        'pnl_pct': pnl_pct,
                        'exit_reason': exit_reason
                    })
                    
                    exits.append(symbol)
            
            # Remove exited positions
            for symbol in exits:
                del positions[symbol]
            
            # Look for new entries (if we have room)
            if len(positions) < max_positions:
                signals = day_data[day_data['signal'] == True]
                
                # Don't enter stocks we already hold
                signals = signals[~signals['symbol'].isin(positions.keys())]
                
                # Sort by distance from ATH (prioritize strongest momentum)
                signals = signals.sort_values('distance_from_ath_5y', ascending=False)
                
                slots_available = max_positions - len(positions)
                
                for _, row in signals.head(slots_available).iterrows():
                    symbol = row['symbol']
                    price = row['close']
                    atr = row['atr_14']
                    
                    # Calculate position size
                    shares = self.calculate_position_size(capital, atr, price)
                    
                    if shares > 0:
                        cost = shares * price
                        
                        if cost <= capital:
                            capital -= cost
                            
                            positions[symbol] = {
                                'shares': shares,
                                'entry_price': price,
                                'entry_date': date,
                                'stop': price - (2 * atr)  # 2x ATR stop
                            }
        
        # Close all remaining positions at end
        final_date = dates[-1]
        final_data = df[df['date'] == final_date]
        
        for symbol, pos in positions.items():
            stock_data = final_data[final_data['symbol'] == symbol]
            if len(stock_data) > 0:
                current_price = stock_data['close'].values[0]
                exit_value = pos['shares'] * current_price
                capital += exit_value
                
                pnl = exit_value - (pos['shares'] * pos['entry_price'])
                pnl_pct = (pnl / (pos['shares'] * pos['entry_price'])) * 100
                
                trades.append({
                    'symbol': symbol,
                    'entry_date': pos['entry_date'],
                    'exit_date': final_date,
                    'entry_price': pos['entry_price'],
                    'exit_price': current_price,
                    'shares': pos['shares'],
                    'pnl': pnl,
                    'pnl_pct': pnl_pct,
                    'exit_reason': 'FINAL_EXIT'
                })
        
        return {
            'trades': pd.DataFrame(trades),
            'equity_curve': pd.DataFrame(equity_curve),
            'final_capital': capital
        }
    
    def calculate_metrics(self, results: Dict) -> Dict:
        """Calculate performance metrics"""
        trades_df = results['trades']
        equity_df = results['equity_curve']
        
        if trades_df.empty:
            return {
                'total_trades': 0,
                'win_rate': 0,
                'avg_win': 0,
                'avg_loss': 0,
                'total_return': 0,
                'max_drawdown': 0
            }
        
        # Trade statistics
        total_trades = len(trades_df)
        winning_trades = len(trades_df[trades_df['pnl'] > 0])
        losing_trades = len(trades_df[trades_df['pnl'] < 0])
        
        win_rate = (winning_trades / total_trades * 100) if total_trades > 0 else 0
        
        avg_win = trades_df[trades_df['pnl'] > 0]['pnl_pct'].mean() if winning_trades > 0 else 0
        avg_loss = trades_df[trades_df['pnl'] < 0]['pnl_pct'].mean() if losing_trades > 0 else 0
        
        # Portfolio performance
        total_return = ((results['final_capital'] - self.initial_capital) / 
                       self.initial_capital * 100)
        
        # Max drawdown
        equity_df['cummax'] = equity_df['equity'].cummax()
        equity_df['drawdown'] = (equity_df['equity'] - equity_df['cummax']) / equity_df['cummax']
        max_drawdown = equity_df['drawdown'].min() * 100
        
        # Sharpe ratio (simplified - daily returns)
        equity_df['returns'] = equity_df['equity'].pct_change()
        sharpe = (equity_df['returns'].mean() / equity_df['returns'].std() * 
                 np.sqrt(252)) if equity_df['returns'].std() > 0 else 0
        
        return {
            'total_trades': total_trades,
            'winning_trades': winning_trades,
            'losing_trades': losing_trades,
            'win_rate': win_rate,
            'avg_win': avg_win,
            'avg_loss': avg_loss,
            'total_return': total_return,
            'max_drawdown': max_drawdown,
            'sharpe_ratio': sharpe,
            'final_capital': results['final_capital']
        }
    
    def print_results(self, results: Dict, metrics: Dict):
        """Print backtest results"""
        print(f"\n{'='*60}")
        print("Backtest Results")
        print(f"{'='*60}\n")
        
        print("Performance Metrics:")
        print(f"  Initial Capital:     {self.initial_capital:>15,.2f} PLN")
        print(f"  Final Capital:       {metrics['final_capital']:>15,.2f} PLN")
        print(f"  Total Return:        {metrics['total_return']:>15.2f}%")
        print(f"  Max Drawdown:        {metrics['max_drawdown']:>15.2f}%")
        print(f"  Sharpe Ratio:        {metrics['sharpe_ratio']:>15.2f}")
        
        print(f"\nTrade Statistics:")
        print(f"  Total Trades:        {metrics['total_trades']:>15}")
        print(f"  Winning Trades:      {metrics['winning_trades']:>15}")
        print(f"  Losing Trades:       {metrics['losing_trades']:>15}")
        print(f"  Win Rate:            {metrics['win_rate']:>15.2f}%")
        print(f"  Avg Win:             {metrics['avg_win']:>15.2f}%")
        print(f"  Avg Loss:            {metrics['avg_loss']:>15.2f}%")
        
        # Show sample trades
        trades_df = results['trades']
        if not trades_df.empty:
            print(f"\n{'='*60}")
            print("Sample Trades (First 10)")
            print(f"{'='*60}\n")
            
            sample = trades_df.head(10)[['symbol', 'entry_date', 'exit_date', 
                                        'entry_price', 'exit_price', 'pnl_pct', 
                                        'exit_reason']]
            print(sample.to_string(index=False))
        
        print(f"\n{'='*60}\n")


def main():
    """Main backtest execution"""
    print("\n" + "="*60)
    print("Momentum Strategy Backtest")
    print("="*60)
    
    # Configuration
    start_date = '2023-01-01'  # Last 2 years
    end_date = '2025-10-19'
    initial_capital = 100000.0  # 100k PLN
    max_positions = 5
    
    # Run backtest
    bt = MomentumBacktest(initial_capital=initial_capital)
    bt.connect()
    
    print("\nLoading data...")
    df = bt.get_backtest_data(start_date, end_date)
    print(f"✓ Loaded {len(df)} data points")
    
    results = bt.run_backtest(df, max_positions=max_positions)
    metrics = bt.calculate_metrics(results)
    
    bt.print_results(results, metrics)
    
    # Save results (optional)
    save = input("Save detailed results to CSV? (y/n): ").strip().lower()
    if save == 'y':
        # Create backtest directory if it doesn't exist
        import os
        os.makedirs('backtest', exist_ok=True)
        
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        trades_file = f"backtest/backtest_trades_{timestamp}.csv"
        equity_file = f"backtest/backtest_equity_{timestamp}.csv"
        
        results['trades'].to_csv(trades_file, index=False)
        results['equity_curve'].to_csv(equity_file, index=False)
        
        print(f"\n✓ Saved trades to: {trades_file}")
        print(f"✓ Saved equity curve to: {equity_file}")
    
    bt.close()
    print("\n✓ Backtest complete\n")


if __name__ == "__main__":
    main()