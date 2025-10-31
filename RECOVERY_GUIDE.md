# 🚨 STOOQ DATA LOADER ISSUE - RECOVERY GUIDE

## Problem Summary

**Issue:** Stooq API is not returning any data (⚠ No data returned for all symbols)

**Root Cause:** 
- Stooq's pandas_datareader backend has become unreliable
- API changes or rate limiting
- Service degradation

**Impact:** 419 stocks failed to load, 0 stocks successfully loaded

---

## 🔧 IMMEDIATE FIX - Use Yahoo Finance Instead

### Step 1: Clean Up Failed Attempts

```bash
# Remove all stocks with no data
python3 cleanup_stocks.py
# Choose option 1 (Deactivate stocks with no data)
# Type: yes
```

### Step 2: Get Valid Symbol List

```bash
# Run the symbol mapper to see valid stocks
python3 wig20_symbols.py
```

**You'll see:**
```
VALID POLISH STOCK SYMBOLS FOR YAHOO FINANCE
================================================

📊 WIG20 Stocks (Most Liquid - RECOMMENDED):
  PKO    → PKOBP.WA            PKO Bank Polski
  PEO    → PEKAO.WA            Bank Pekao
  ALR    → ALIOR.WA            Alior Bank
  ... etc

For your .env file (WIG20 only):
STOCK_SYMBOLS=PKO,PEO,ALR,BHW,MBK,SPL,ING,PKN,PGE,PGN,LPP,JSW,KGH,CDR,11B,ALE,ACP,DNP,OPL,BDX,PZU
```

### Step 3: Update Your .env File

```bash
# Edit .env
nano .env

# Replace STOCK_SYMBOLS with:
STOCK_SYMBOLS=PKO,PEO,ALR,BHW,MBK,SPL,ING,PKN,PGE,PGN,LPP,JSW,KGH,CDR,11B,ALE,ACP,DNP,OPL,BDX,PZU

# These are the 21 most liquid WIG20 stocks with verified Yahoo Finance symbols
```

### Step 4: Load Data with Yahoo Finance

```bash
# Use the new Yahoo Finance loader
python3 load_data_yahoo.py
```

**Expected output:**
```
============================================================
Polish Stocks Data Loader (Yahoo Finance)
============================================================

Configuration:
  Date Range: 2020-01-01 to 2025-10-20
  Symbols: PKO, PEO, ALR, BHW, MBK...
  Data Source: Yahoo Finance
  Symbol Mapper: ✓ Active

============================================================
Loading data for PKO
============================================================
✓ Added stock: PKO (ID: 1)
  Fetching from Yahoo Finance: PKOBP.WA
  ✓ Retrieved 1456 records from 2020-01-02 to 2025-10-18
  ✓ Loaded 1456 price records into database

...

============================================================
Loading Summary
============================================================
✓ Successfully loaded: 21 stocks
✗ Failed: 0 stocks
Total: 21 stocks
```

### Step 5: Calculate Indicators

```bash
python3 calculate_indicators.py
```

---

## 📋 What Changed

### OLD (Broken):
- ❌ Used `load_data_datareader.py`
- ❌ Relied on Stooq API (unreliable)
- ❌ Symbol format: `SYMBOL.PL`
- ❌ No data returned

### NEW (Working):
- ✅ Use `load_data_yahoo.py`
- ✅ Relies on Yahoo Finance (reliable)
- ✅ Symbol format: Properly mapped (e.g., `PKO` → `PKOBP.WA`)
- ✅ Data loads successfully

---

## 🎯 Recommended Symbol List

### Best Option: WIG20 Only (21 stocks)
```
STOCK_SYMBOLS=PKO,PEO,ALR,BHW,MBK,SPL,ING,PKN,PGE,PGN,LPP,JSW,KGH,CDR,11B,ALE,ACP,DNP,OPL,BDX,PZU
```

**Why?**
- ✅ Most liquid (easy to trade)
- ✅ Best data availability
- ✅ Verified Yahoo Finance symbols
- ✅ Enough for momentum strategy
- ✅ Fast to load (15-20 minutes)

### Alternative: Top 10 Most Liquid
```
STOCK_SYMBOLS=PKO,PZU,PKN,KGH,PEO,ALE,CDR,PGE,DNP,JSW
```

**Why?**
- ✅ Even faster (5-10 minutes)
- ✅ Highest volume stocks
- ✅ Best for beginners

---

## 🔄 Complete Recovery Workflow

```bash
# 1. Clean database
python3 cleanup_stocks.py
# Choose option 5 (DELETE all stocks with no data)
# Type: DELETE [NUMBER] STOCKS

# 2. Check valid symbols
python3 wig20_symbols.py

# 3. Update .env with valid symbols
nano .env
# Set: STOCK_SYMBOLS=PKO,PEO,ALR,BHW,MBK,SPL,ING,PKN,PGE,PGN,LPP,JSW,KGH,CDR,11B,ALE,ACP,DNP,OPL,BDX,PZU

# 4. Load data with Yahoo Finance
python3 load_data_yahoo.py

# 5. Calculate indicators
python3 calculate_indicators.py

# 6. Verify success
python3 verify_setup.py

# 7. Analyze
python3 analyze_stocks.py
```

---

## 📊 Database Status Check

```bash
# Check current state
docker exec -it polish_stocks_db psql -U trader -d polish_stocks

# Run these queries:
SELECT COUNT(*) FROM stocks WHERE is_active = TRUE;
SELECT COUNT(*) FROM historical_prices;
SELECT COUNT(*) FROM technical_indicators;

# Should show:
# Active stocks: 21 (or however many you loaded)
# Historical prices: 30,000+ (21 stocks × ~1,400 days)
# Technical indicators: 25,000+ (after calculate_indicators.py)
```

---

## ⚠️ Important Notes

### Why Stooq Stopped Working:
1. API changes without notice
2. Rate limiting (too many requests)
3. Service deprecation
4. Data format changes

### Why Yahoo Finance is Better:
1. ✅ More reliable (maintained by Yahoo)
2. ✅ Better Polish stock coverage
3. ✅ Includes adjusted prices
4. ✅ Free API with reasonable limits
5. ✅ Active development (yfinance library)

### Symbol Mapping:
- Stooq: `PKO.PL` ❌ (not working)
- Yahoo: `PKOBP.WA` ✅ (working)
- Need proper mapper for each stock

---

## 🛠️ Files You Need

### New Files (Download from outputs):
1. **wig20_symbols.py** - Symbol mapper for Yahoo Finance
2. **load_data_yahoo.py** - New data loader using Yahoo Finance
3. **cleanup_stocks.py** - Clean up failed stocks

### Keep Using:
- **calculate_indicators.py** - Still works great
- **update_data.py** - Updated, now uses Yahoo Finance
- **analyze_stocks.py** - No changes needed
- **backtest_simple.py** - No changes needed

### Can Delete (Optional):
- `load_data_datareader.py` - Old Stooq loader (broken)
- `find_yahoo_symbols.py` - Replaced by wig20_symbols.py

---

## 🎯 Expected Timeline

```
Step 1: Cleanup (2 minutes)
  └─> python3 cleanup_stocks.py

Step 2: Update config (2 minutes)
  └─> Edit .env file

Step 3: Load data (15-20 minutes for WIG20)
  └─> python3 load_data_yahoo.py

Step 4: Calculate indicators (2-3 minutes)
  └─> python3 calculate_indicators.py

Step 5: Verify (1 minute)
  └─> python3 verify_setup.py

Total: ~25 minutes to full recovery
```

---

## ✅ Success Criteria

After following this guide, you should have:
- ✓ 21 WIG20 stocks in database
- ✓ ~30,000 historical price records
- ✓ ~25,000 technical indicator records
- ✓ Data from 2020-01-01 to yesterday
- ✓ All stocks up to date
- ✓ Ready to run backtest

---

## 🆘 If Still Having Issues

### Issue: Yahoo Finance also fails
**Solution:**
```bash
# Check internet connection
ping finance.yahoo.com

# Check if yfinance installed
pip show yfinance

# Reinstall yfinance
pip install --upgrade yfinance
```

### Issue: Some symbols still fail
**Solution:**
Use the symbol mapper - it has verified symbols. Don't try random 3-letter codes.

### Issue: Database full of failed stocks
**Solution:**
```bash
# Nuclear option - reset database
docker-compose down -v
docker-compose up -d
sleep 5

# Reload schema
docker exec -i polish_stocks_db psql -U trader -d polish_stocks < init_db/01_create_schema.sql

# Start fresh
python3 load_data_yahoo.py
```

---

## 📞 Next Steps After Recovery

Once you have data loaded:

1. **Analyze current opportunities:**
   ```bash
   python3 analyze_stocks.py
   ```

2. **Run backtest:**
   ```bash
   python3 backtest_simple.py
   ```

3. **Set up daily updates:**
   ```bash
   # update_data.py now uses Yahoo Finance automatically
   python3 update_data.py
   ```

4. **Continue with your roadmap:**
   - Parameter optimization
   - Signal generation
   - Paper trading

---

**Bottom Line:** Stop using Stooq, switch to Yahoo Finance, use only WIG20 stocks with proper symbol mapping. You'll be operational in 25 minutes! 🚀
