"""
Stock Cleanup Utility
Identifies and removes stocks with no data or that are delisted
"""

import os
import sys
import psycopg2
from dotenv import load_dotenv
from datetime import datetime

load_dotenv()


class StockCleanup:
    """Manage stock database cleanup operations"""
    
    def __init__(self):
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
            print("✓ Database connection established\n")
        except Exception as e:
            print(f"✗ Database connection failed: {e}")
            sys.exit(1)
    
    def close(self):
        """Close database connection"""
        if self.cursor:
            self.cursor.close()
        if self.conn:
            self.conn.close()
    
    def get_stocks_without_data(self):
        """Find stocks that have no price data"""
        query = """
            SELECT s.stock_id, s.symbol, s.name
            FROM stocks s
            LEFT JOIN historical_prices hp ON s.stock_id = hp.stock_id
            WHERE hp.price_id IS NULL
            AND s.is_active = TRUE
            ORDER BY s.symbol
        """
        self.cursor.execute(query)
        return self.cursor.fetchall()
    
    def get_stocks_with_old_data(self, days_threshold=90):
        """Find stocks where latest data is very old (possibly delisted)"""
        query = """
            SELECT 
                s.stock_id, 
                s.symbol, 
                s.name,
                MAX(hp.date) as latest_date,
                CURRENT_DATE - MAX(hp.date) as days_old
            FROM stocks s
            JOIN historical_prices hp ON s.stock_id = hp.stock_id
            WHERE s.is_active = TRUE
            GROUP BY s.stock_id, s.symbol, s.name
            HAVING CURRENT_DATE - MAX(hp.date) > %s
            ORDER BY days_old DESC
        """
        self.cursor.execute(query, (days_threshold,))
        return self.cursor.fetchall()
    
    def get_stocks_with_minimal_data(self, min_records=100):
        """Find stocks with very few price records (likely bad data)"""
        query = """
            SELECT 
                s.stock_id,
                s.symbol,
                s.name,
                COUNT(hp.price_id) as record_count
            FROM stocks s
            JOIN historical_prices hp ON s.stock_id = hp.stock_id
            WHERE s.is_active = TRUE
            GROUP BY s.stock_id, s.symbol, s.name
            HAVING COUNT(hp.price_id) < %s
            ORDER BY record_count ASC
        """
        self.cursor.execute(query, (min_records,))
        return self.cursor.fetchall()
    
    def deactivate_stock(self, stock_id, symbol):
        """Mark stock as inactive (soft delete)"""
        try:
            self.cursor.execute("""
                UPDATE stocks 
                SET is_active = FALSE 
                WHERE stock_id = %s
            """, (stock_id,))
            self.conn.commit()
            print(f"  ✓ Deactivated {symbol}")
            return True
        except Exception as e:
            self.conn.rollback()
            print(f"  ✗ Error deactivating {symbol}: {e}")
            return False
    
    def delete_stock(self, stock_id, symbol):
        """Permanently delete stock and all its data (hard delete)"""
        try:
            # CASCADE will automatically delete related records
            self.cursor.execute("""
                DELETE FROM stocks WHERE stock_id = %s
            """, (stock_id,))
            self.conn.commit()
            print(f"  ✓ Deleted {symbol}")
            return True
        except Exception as e:
            self.conn.rollback()
            print(f"  ✗ Error deleting {symbol}: {e}")
            return False
    
    def print_table(self, title, headers, rows):
        """Print formatted table"""
        print(f"\n{'='*80}")
        print(f" {title}")
        print(f"{'='*80}")
        
        if not rows:
            print("None found")
            return
        
        # Print header
        header_line = " | ".join(f"{h:<15}" for h in headers)
        print(header_line)
        print("-" * len(header_line))
        
        # Print rows
        for row in rows[:50]:  # Limit to 50 for readability
            row_line = " | ".join(f"{str(v):<15}" for v in row)
            print(row_line)
        
        if len(rows) > 50:
            print(f"\n... and {len(rows) - 50} more")
        
        print(f"\nTotal: {len(rows)}")


def main():
    """Main cleanup function"""
    print("\n" + "="*80)
    print(" Stock Database Cleanup Utility")
    print("="*80)
    print(f" Date: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
    
    cleanup = StockCleanup()
    cleanup.connect()
    
    # 1. Find stocks with no data
    no_data = cleanup.get_stocks_without_data()
    cleanup.print_table(
        "Stocks with NO Price Data (Likely Delisted/Invalid)",
        ["ID", "Symbol", "Name"],
        [(s[0], s[1], s[2][:30] if s[2] else "N/A") for s in no_data]
    )
    
    # 2. Find stocks with old data
    old_data = cleanup.get_stocks_with_old_data(days_threshold=90)
    cleanup.print_table(
        "Stocks with OLD Data (>90 days, Possibly Delisted)",
        ["ID", "Symbol", "Name", "Latest Date", "Days Old"],
        [(s[0], s[1], s[2][:20] if s[2] else "N/A", s[3], s[4]) for s in old_data]
    )
    
    # 3. Find stocks with minimal data
    minimal_data = cleanup.get_stocks_with_minimal_data(min_records=100)
    cleanup.print_table(
        "Stocks with MINIMAL Data (<100 records)",
        ["ID", "Symbol", "Name", "Records"],
        [(s[0], s[1], s[2][:30] if s[2] else "N/A", s[3]) for s in minimal_data]
    )
    
    # Summary
    print(f"\n{'='*80}")
    print(" Summary")
    print(f"{'='*80}")
    print(f"Stocks with no data:       {len(no_data)}")
    print(f"Stocks with old data:      {len(old_data)}")
    print(f"Stocks with minimal data:  {len(minimal_data)}")
    
    # Total unique problem stocks
    problem_ids = set()
    for stock in no_data + old_data + minimal_data:
        problem_ids.add(stock[0])
    
    print(f"\nTotal unique problem stocks: {len(problem_ids)}")
    
    # Ask what to do
    print(f"\n{'='*80}")
    print(" Cleanup Options")
    print(f"{'='*80}")
    print("1. Deactivate stocks with NO data (soft delete - recommended)")
    print("2. Deactivate stocks with OLD data (>90 days)")
    print("3. Deactivate stocks with MINIMAL data (<100 records)")
    print("4. Deactivate ALL problem stocks")
    print("5. Permanently DELETE stocks with no data (hard delete)")
    print("6. Export list to CSV (no changes)")
    print("7. Exit without changes")
    
    choice = input("\nEnter choice (1-7): ").strip()
    
    if choice == "1":
        confirm = input(f"Deactivate {len(no_data)} stocks with no data? (yes/no): ").strip().lower()
        if confirm == "yes":
            count = 0
            for stock_id, symbol, name in no_data:
                if cleanup.deactivate_stock(stock_id, symbol):
                    count += 1
            print(f"\n✓ Deactivated {count} stocks")
    
    elif choice == "2":
        confirm = input(f"Deactivate {len(old_data)} stocks with old data? (yes/no): ").strip().lower()
        if confirm == "yes":
            count = 0
            for stock_id, symbol, name, _, _ in old_data:
                if cleanup.deactivate_stock(stock_id, symbol):
                    count += 1
            print(f"\n✓ Deactivated {count} stocks")
    
    elif choice == "3":
        confirm = input(f"Deactivate {len(minimal_data)} stocks with minimal data? (yes/no): ").strip().lower()
        if confirm == "yes":
            count = 0
            for stock_id, symbol, name, _ in minimal_data:
                if cleanup.deactivate_stock(stock_id, symbol):
                    count += 1
            print(f"\n✓ Deactivated {count} stocks")
    
    elif choice == "4":
        all_problems = []
        for stock in no_data:
            all_problems.append((stock[0], stock[1]))
        for stock in old_data:
            all_problems.append((stock[0], stock[1]))
        for stock in minimal_data:
            all_problems.append((stock[0], stock[1]))
        
        # Remove duplicates
        unique_problems = list(set(all_problems))
        
        confirm = input(f"Deactivate {len(unique_problems)} problem stocks? (yes/no): ").strip().lower()
        if confirm == "yes":
            count = 0
            for stock_id, symbol in unique_problems:
                if cleanup.deactivate_stock(stock_id, symbol):
                    count += 1
            print(f"\n✓ Deactivated {count} stocks")
    
    elif choice == "5":
        print("\n⚠️  WARNING: This will PERMANENTLY delete stocks and ALL their data!")
        confirm = input(f"Type 'DELETE {len(no_data)} STOCKS' to confirm: ").strip()
        if confirm == f"DELETE {len(no_data)} STOCKS":
            count = 0
            for stock_id, symbol, name in no_data:
                if cleanup.delete_stock(stock_id, symbol):
                    count += 1
            print(f"\n✓ Deleted {count} stocks permanently")
        else:
            print("Cancelled")
    
    elif choice == "6":
        # Export to CSV
        import csv
        filename = f"problem_stocks_{datetime.now().strftime('%Y%m%d')}.csv"
        
        with open(filename, 'w', newline='') as f:
            writer = csv.writer(f)
            writer.writerow(["Stock ID", "Symbol", "Name", "Issue", "Details"])
            
            for stock_id, symbol, name in no_data:
                writer.writerow([stock_id, symbol, name or "N/A", "No Data", "No price records"])
            
            for stock_id, symbol, name, latest, days in old_data:
                writer.writerow([stock_id, symbol, name or "N/A", "Old Data", f"{days} days old"])
            
            for stock_id, symbol, name, records in minimal_data:
                writer.writerow([stock_id, symbol, name or "N/A", "Minimal Data", f"{records} records"])
        
        print(f"\n✓ Exported to {filename}")
    
    else:
        print("\nNo changes made")
    
    cleanup.close()
    
    print("\n" + "="*80)
    print(" Next Steps")
    print("="*80)
    print("\nIf you deactivated stocks:")
    print("  1. They won't appear in update_data.py anymore")
    print("  2. Run: python3 update_data.py to update remaining stocks")
    print("  3. Run: python3 calculate_indicators.py")
    print("\nTo reactivate a stock later:")
    print("  UPDATE stocks SET is_active = TRUE WHERE symbol = 'SYMBOL';")
    print("\n" + "="*80 + "\n")


if __name__ == "__main__":
    main()
