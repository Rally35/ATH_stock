# Technical Indicators Calculator - Usage Guide

## Overview

The `calculate_indicators.py` script calculates technical indicators for all stocks in the database and stores them in the `technical_indicators` table. This is a critical step before implementing any trading strategies.

## Calculated Indicators

### Momentum Indicators
- **RSI (14)**: Relative Strength Index - measures overbought/oversold conditions (0-100)
- **MACD**: Moving Average Convergence Divergence with signal line and histogram
- **ATR (14)**: Average True Range - measures volatility

### Moving Averages
- **SMA 50**: 50-day Simple Moving Average
- **SMA 200**: 200-day Simple Moving Average
- **EMA 20**: 20-day Exponential Moving Average

### Volume Analysis
- **Volume MA (20)**: 20-day volume moving average

### All-Time High Metrics
- **ATH 1Y**: All-time high over 1 year (252 trading days)
- **ATH 2Y**: All-time high over 2 years (504 trading days)
- **ATH 5Y**: All-time high over 5 years (1260 trading days)
- **ATH All-Time**: Highest price ever recorded
- **Distance from ATH 5Y**: Percentage distance from 5-year high

## Usage

### Basic Usage

```bash
python3 calculate_indicators.py
```

This will:
1. Connect to the database
2. Find all active stocks
3. Calculate all indicators for each stock
4. Store results in `technical_indicators` table
5. Show summary statistics

### Expected Output

```
============================================================
Technical Indicators Calculator
Momentum Trading System for Polish Stocks
============================================================

Found 20 active stocks to process

============================================================
Processing ALE (ID: 1)
============================================================
  ✓ Loaded 1456 price records
  Date range: 2020-01-02 to 2025-10-18
  ✓ Calculated indicators for 1456 dates
  ✓ Stored 1256 indicator records

...

============================================================
Calculation Summary
============================================================
✓ Successfully processed: 20 stocks
✗ Failed: 0 stocks
Total: 20 stocks

Database Statistics:
  Stocks with indicators: 20
  Total indicator records: 25,120
  Date range: 2020-01-02 to 2025-10-18

✓ Indicator calculation complete
```

## Data Requirements

### Minimum Historical Data Needed

For accurate indicator calculation, you need:
- **RSI (14)**: At least 14 days of data
- **SMA 50**: At least 50 days of data
- **SMA 200**: At least 200 days of data (most restrictive)
- **MACD**: At least 26 days of data

**Recommendation**: Have at least 200+ trading days (about 10 months) of historical price data before running this script.

## Updating Indicators

The script uses **UPSERT** logic, so you can run it multiple times:
- New dates will be added
- Existing dates will be updated with recalculated values
- No duplicate records will be created

### Update Workflow

```bash
# 1. Load new price data
python3 load_data.py

# 2. Recalculate indicators (includes new data)
python3 calculate_indicators.py
```

## Verification

### Check Indicator Data

```bash
# Connect to database
docker exec -it polish_stocks_db psql -U trader -d polish_stocks
```

```sql
-- View latest indicators for all stocks
SELECT * FROM latest_stock_data
ORDER BY date DESC, symbol;

-- Check specific stock's indicators
SELECT date, close, rsi_14, sma_50, sma_200, distance_from_ath_5y
FROM technical_indicators ti
JOIN stocks s ON s.stock_id = ti.stock_id
WHERE s.symbol = 'PKO'
ORDER BY date DESC
LIMIT 20;

-- Find momentum signals
SELECT 
    s.symbol,
    ti.date,
    ti.rsi_14,
    ti.distance_from_ath_5y,
    hp.close
FROM technical_indicators ti
JOIN stocks s ON s.stock_id = ti.stock_id
JOIN historical_prices hp ON hp.stock_id = ti.stock_id AND hp.date = ti.date
WHERE ti.rsi_14 > 50 
  AND ti.sma_50 > ti.sma_200
  AND ti.distance_from_ath_5y > -0.05
  AND ti.date > CURRENT_DATE - INTERVAL '30 days'
ORDER BY ti.date DESC, s.symbol;
```

## Troubleshooting

### Issue: "No valid indicators to store"

**Cause**: Not enough historical data for the stock.

**Solution**: 
- Need at least 200 trading days for SMA 200
- Check: `SELECT COUNT(*) FROM historical_prices WHERE stock_id = X;`
- Load more historical data if needed

### Issue: Many NULL values in indicators

**Cause**: Recent dates don't have enough lookback period.

**Expected Behavior**: 
- First 14 days: No RSI
- First 50 days: No SMA 50
- First 200 days: No SMA 200
- This is normal and correct

### Issue: Calculation very slow

**Cause**: Large amount of data (normal for stocks with 5+ years of daily data).

**Optimization**:
- Process runs once per stock
- Typical speed: 1-2 seconds per stock per year of data
- 20 stocks with 5 years = ~3-5 minutes total

## Technical Details

### Algorithm Details

**RSI Calculation**:
```
RS = Average Gain / Average Loss (over 14 periods)
RSI = 100 - (100 / (1 + RS))
```

**MACD Calculation**:
```
MACD Line = EMA(12) - EMA(26)
Signal Line = EMA(9) of MACD Line
Histogram = MACD Line - Signal Line
```

**ATR Calculation**:
```
True Range = max(High - Low, |High - Prev Close|, |Low - Prev Close|)
ATR = SMA(14) of True Range
```

**Distance from ATH**:
```
Distance = (Current Price - ATH) / ATH
Example: -0.05 = 5% below ATH
         0.00 = At ATH (breakout!)
```

## Integration with Trading Strategy

### Momentum Signal Criteria (from research)

The view `latest_stock_data` automatically calculates momentum signals:

```sql
momentum_signal = TRUE when:
  - RSI > 50 (bull market)
  - SMA 50 > SMA 200 (uptrend)
  - Distance from ATH <= 5% (near all-time high)
```

Example query:
```sql
SELECT symbol, close, rsi_14, distance_from_ath_5y
FROM latest_stock_data
WHERE momentum_signal = TRUE;
```

## Next Steps After Running

1. **Verify Data Quality**
   ```bash
   python3 verify_setup.py
   ```

2. **Analyze Results**
   - Check which stocks have momentum signals
   - Identify stocks near all-time highs
   - Review RSI and MACD patterns

3. **Begin Backtesting**
   - Use the calculated indicators
   - Test momentum strategies
   - Evaluate performance

## Performance Notes

- **Memory Usage**: ~100-200 MB for 20 stocks with 5 years of data
- **CPU Usage**: Moderate (pandas calculations)
- **Runtime**: ~1-5 minutes for typical WIG20 portfolio
- **Database Growth**: ~1,000 records per stock per year

## Maintenance

### Regular Updates

Run this script:
- **Daily**: After loading new price data
- **Weekly**: For data quality checks
- **Monthly**: For full recalculation (ensure consistency)

### Monitoring

```sql
-- Check latest computation dates
SELECT 
    s.symbol,
    MAX(ti.computed_at) as last_updated
FROM stocks s
LEFT JOIN technical_indicators ti ON s.stock_id = ti.stock_id
GROUP BY s.symbol
ORDER BY last_updated DESC NULLS LAST;
```

## Support

If you encounter issues:
1. Check database connection: `python3 verify_setup.py`
2. Verify price data exists: Check `historical_prices` table
3. Review error messages in console output
4. Check PostgreSQL logs: `docker-compose logs postgres`
