# Incremental Data Update Guide

## Overview

`update_data.py` is a smart data updater that only fetches **missing data** since your last update. This makes daily updates much faster than reloading everything.

## Key Features

✅ **Incremental Updates** - Only fetches dates you don't have  
✅ **Automatic Date Detection** - Finds the last date in your database  
✅ **Dual Data Source** - Yahoo Finance (primary) + Stooq (backup)  
✅ **Three Update Modes** - All stocks, single stock, or status check  
✅ **Up-to-Date Detection** - Skips stocks that don't need updating  
✅ **Safe UPSERT** - Won't create duplicates, updates existing data  

## Usage

### Daily Update (Recommended)

Run this every day after market close:

```bash
python3 update_data.py
```

Then choose option **1** (Update all stocks)

**What happens:**
1. Checks each stock's latest date in database
2. Fetches only missing dates from latest → yesterday
3. Inserts new data (or updates if dates overlap)
4. Reports which stocks were updated

**Typical output:**
```
============================================================
Incremental Data Updater
Fetches only missing data since last update
============================================================

Update mode:
1. Update all stocks (recommended for daily updates)
2. Update single stock
3. Check status only (no updates)

Enter choice (1-3) [default: 1]: 1

============================================================
Updating PKO (ID: 1)
============================================================
  ℹ Latest data: 2025-10-18
  → Need to fetch: 2025-10-19 to 2025-10-20
  Fetching from Yahoo Finance: PKO.WA
  ✓ Retrieved 2 records from 2025-10-19 to 2025-10-20
  ✓ Loaded 2 price records into database

============================================================
Updating PZU (ID: 2)
============================================================
  ℹ Latest data: 2025-10-18
  → Need to fetch: 2025-10-19 to 2025-10-20
  Fetching from Yahoo Finance: PZU.WA
  ✓ Retrieved 2 records from 2025-10-19 to 2025-10-20
  ✓ Loaded 2 price records into database

...

============================================================
Update Summary
============================================================
✓ Successfully updated: 18 stocks
⊙ Already up to date: 2 stocks
✗ Failed: 0 stocks
Total: 20 stocks

⚠ Don't forget to recalculate indicators:
   python3 calculate_indicators.py
```

### Update Single Stock

If you just want to update one stock:

```bash
python3 update_data.py
# Choose option 2
# Enter symbol: PKO
```

### Check Status Without Updating

To see which stocks need updates:

```bash
python3 update_data.py
# Choose option 3
```

**Output:**
```
Symbol     Latest Date      Status
------------------------------------------------------------
ALE        2025-10-20       ✓ UP TO DATE
PKO        2025-10-18       ⚠ 2 days behind
CDR        2025-10-20       ✓ UP TO DATE
PZU        2025-10-15       ⚠ 5 days behind
```

## When to Use This vs load_data.py

### Use `update_data.py` when:
- ✅ Running **daily updates** (fastest)
- ✅ Database already has historical data
- ✅ Just need to **catch up** on recent dates
- ✅ Stocks temporarily failed and need to be refreshed

### Use `load_data.py` when:
- ✅ **First time setup** (loading all history)
- ✅ Adding a **new stock** to database
- ✅ Need to **reload** entire history (data corruption)
- ✅ Changing date range significantly

## How It Works

### 1. Date Detection
```python
# For stock PKO with latest date 2025-10-18
latest_date = get_latest_date(stock_id)  # Returns: 2025-10-18
start_date = latest_date + 1 day         # Becomes: 2025-10-19
end_date = yesterday                     # Today - 1 day: 2025-10-20

# Fetches only: 2025-10-19 to 2025-10-20 (2 days instead of 5 years!)
```

### 2. Data Sources

**Priority 1: Yahoo Finance**
- Format: `SYMBOL.WA` (e.g., `PKO.WA`)
- Most reliable for Polish stocks
- Includes adjusted close prices

**Priority 2: Stooq (Automatic Fallback)**
- Format: `SYMBOL.PL` (e.g., `PKO.PL`)
- Used if Yahoo fails
- Basic OHLCV data

### 3. Database Update (UPSERT)

```sql
INSERT INTO historical_prices (...)
VALUES (...)
ON CONFLICT (stock_id, date) 
DO UPDATE SET
    -- Updates existing records if dates overlap
    -- Inserts new records if dates are new
```

Safe to run multiple times - won't create duplicates!

## Automation

### Linux/Mac Cron Job

Update daily at 6 PM (after market close):

```bash
crontab -e
```

Add this line:
```bash
0 18 * * 1-5 cd /path/to/project && python3 update_data.py <<< "1" && python3 calculate_indicators.py
```

This will:
1. Run update at 6 PM on weekdays (Mon-Fri)
2. Automatically choose option 1 (update all)
3. Then recalculate indicators

### Windows Task Scheduler

Create a batch file `daily_update.bat`:
```batch
@echo off
cd C:\path\to\project
echo 1 | python update_data.py
python calculate_indicators.py
pause
```

Schedule it to run daily at 6 PM.

## After Updating

### Always Recalculate Indicators

After loading new price data, you must recalculate indicators:

```bash
python3 calculate_indicators.py
```

This updates:
- RSI, MACD, ATR (based on new prices)
- Moving averages (SMA, EMA)
- All-time highs (may have new ATH!)
- Distance from ATH

### Verify Update Success

```bash
# Check latest dates in database
docker exec -it polish_stocks_db psql -U trader -d polish_stocks

SELECT 
    s.symbol,
    MAX(hp.date) as latest_price,
    MAX(ti.date) as latest_indicator
FROM stocks s
LEFT JOIN historical_prices hp ON s.stock_id = hp.stock_id
LEFT JOIN technical_indicators ti ON ti.stock_id = s.stock_id
GROUP BY s.symbol
ORDER BY s.symbol;
```

Expected:
- `latest_price` should be yesterday or today
- `latest_indicator` should match or be close to `latest_price`

## Troubleshooting

### Issue: "Already up to date" for all stocks

**Cause:** Market was closed (weekend/holiday) or you already ran update today.

**Solution:** This is normal! Run again tomorrow.

### Issue: Some stocks fail to update

**Possible causes:**
1. Stock delisted or symbol changed
2. Data source temporarily down
3. Network connection issues

**Solutions:**
```bash
# Try updating just that stock
python3 update_data.py
# Choose option 2, enter symbol

# If still fails, try full reload
python3 load_data.py
# Edit .env to include only failing symbol
```

### Issue: "No data returned"

**Cause:** Symbol format incorrect or stock not available on data source.

**Solution:**
```bash
# Verify symbol works
python3 find_yahoo_symbols.py

# Check if stock is actually traded
# Visit: https://finance.yahoo.com/quote/SYMBOL.WA
```

### Issue: Duplicate data or wrong dates

**Cause:** Clock/timezone issues or data source returning bad data.

**Solution:**
```bash
# Check latest dates
python3 update_data.py
# Choose option 3 (status check)

# If needed, remove bad data
python3 manage_database.py
# Delete specific stock and reload
```

## Performance

### Speed Comparison

**Full Reload** (`load_data.py`):
- 20 stocks × 5 years = ~25,000 records
- Takes: 3-5 minutes
- Network: ~10 MB download

**Incremental Update** (`update_data.py`):
- 20 stocks × 1 day = ~20 records
- Takes: 10-15 seconds
- Network: ~50 KB download

**→ 20x faster for daily updates!**

### Database Growth

Daily update adds:
- Price records: ~20 rows (one per stock)
- Database growth: ~2 KB/day
- Annual growth: ~730 KB/year

Very efficient!

## Best Practices

### 1. Daily Routine (Recommended)

```bash
# After market close (5-6 PM Polish time)
python3 update_data.py          # Fetch new prices
python3 calculate_indicators.py # Update indicators
python3 analyze_stocks.py       # Check for signals
```

### 2. Weekly Check

```bash
# Verify data quality
python3 update_data.py
# Choose option 3 (status check)

# Should show all stocks up to date
```

### 3. Monthly Full Recalculation

```bash
# Recalculate ALL indicators from scratch
python3 manage_database.py
# Choose option 1 (clear indicators)

python3 calculate_indicators.py
# Ensures consistency
```

### 4. Before Backtesting

Always ensure data is current:
```bash
python3 update_data.py          # Update prices
python3 calculate_indicators.py # Update indicators
python3 backtest_simple.py      # Run backtest
```

## Integration with Other Scripts

### Workflow Integration

```python
# Example: Automated daily workflow script

import subprocess

# 1. Update prices
subprocess.run(["python3", "update_data.py"], input="1\n", text=True)

# 2. Calculate indicators  
subprocess.run(["python3", "calculate_indicators.py"])

# 3. Check for signals
subprocess.run(["python3", "analyze_stocks.py"])

# 4. Send email/alert if signals found
# ... your alert logic here ...
```

## FAQ

**Q: Can I run this multiple times per day?**  
A: Yes! It's safe. If data already exists, it will skip or update.

**Q: What if I miss several days?**  
A: It will catch up automatically. Fetches from last date → yesterday.

**Q: Does it work on weekends?**  
A: Yes, but will show "already up to date" (no trading on weekends).

**Q: What time should I run it?**  
A: After market close (~5 PM Polish time). Data available ~6 PM.

**Q: Do I need to update indicators every time?**  
A: Yes! New prices → new indicators. Always run `calculate_indicators.py` after.

**Q: Can I update just one stock?**  
A: Yes! Choose option 2 and enter the symbol.

## Summary

`update_data.py` is your **daily maintenance tool**. Use it to:
- ✅ Keep data current (daily updates)
- ✅ Stay efficient (only fetch what's needed)
- ✅ Monitor data status (option 3)
- ✅ Fix individual stocks (option 2)

Combined with `calculate_indicators.py`, you have a complete daily update workflow!

---

**Next Step:** Set up automated daily updates with cron/Task Scheduler for hands-free operation.
