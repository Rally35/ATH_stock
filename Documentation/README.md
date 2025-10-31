# Polish Stocks Momentum Trading System - Database Setup

A PostgreSQL-based database system for storing and managing historical stock data for Polish equities, designed to support momentum trading strategies based on academic research.

## 📋 Project Overview

This setup provides the foundational database infrastructure for a momentum trading system targeting Polish stocks on the Warsaw Stock Exchange (WSE). The system is designed to:

- Store historical OHLCV (Open, High, Low, Close, Volume) data in PLN
- Track technical indicators (RSI, MACD, ATR, moving averages)
- Monitor all-time high (ATH) proximity for momentum signals
- Support data quality tracking and audit logging

### Current Implementation Status

**✅ Completed:**
- PostgreSQL database with optimized schema
- Historical price data storage
- Technical indicators table structure
- Data quality logging system
- Python data loader for Stooq and Yahoo Finance
- Docker containerization

**🔄 Future Phases (Not Included Yet):**
- Technical indicator calculation engine
- Backtesting framework
- Live trading signal generation
- Risk management system
- Portfolio tracking

## 🏗️ Architecture

### Database Schema

```
stocks
├── stock_id (PK)
├── symbol
├── name
├── sector
└── is_active

historical_prices
├── price_id (PK)
├── stock_id (FK)
├── date
├── open, high, low, close
├── volume
└── adjusted_close

technical_indicators
├── indicator_id (PK)
├── stock_id (FK)
├── date
├── rsi_14, sma_50, sma_200
├── macd, macd_signal
├── atr_14
├── ath_1y, ath_2y, ath_5y
└── distance_from_ath_5y

data_quality_log
├── log_id (PK)
├── stock_id (FK)
├── log_type
├── severity
└── message
```

### Key Features

- **Optimized Indexing**: Fast queries on stock_id and date combinations
- **Data Integrity**: Foreign key constraints and unique constraints prevent duplicates
- **Upsert Support**: Automatic handling of duplicate data during updates
- **Materialized View**: `latest_stock_data` for quick access to current market state
- **Audit Trail**: Complete logging of data loads and quality issues

## 🚀 Quick Start

### Prerequisites

- Docker and Docker Compose installed
- Python 3.9+ (for running the data loader)
- Internet connection (for fetching stock data)

### Installation Steps

1. **Clone the repository and navigate to project directory**

```bash
cd polish-stocks-momentum
```

2. **Create environment configuration**

```bash
cp .env.example .env
# Edit .env with your preferred settings
```

3. **Start the PostgreSQL database**

```bash
docker-compose up -d
```

4. **Verify database is running**

```bash
docker-compose ps
docker-compose logs postgres
```

5. **Install Python dependencies**

```bash
pip install -r requirements.txt
```

6. **Load historical data**

```bash
python load_data.py
```

### Default Configuration

- **Database Name**: `polish_stocks`
- **Username**: `trader`
- **Password**: `change_me_in_production` (⚠️ Change this!)
- **Port**: `5432`
- **Default Stocks**: WIG20 components (PKO, PZU, PKN, PEO, KGH, etc.)
- **Date Range**: 2020-01-01 to present
- **Data Source**: Stooq (primary), Yahoo Finance (fallback)

## 📊 Data Sources

### Yahoo Finance (Primary - Recommended)
- **Pros**: Reliable API, well-documented, adjusted prices, good Polish market coverage
- **Format**: Symbol format `SYMBOL.WA` (e.g., `PKO.WA` for PKO Bank Polski)
- **Currency**: Returns prices in PLN for Polish stocks
- **Note**: The data loader automatically adds `.WA` suffix, so use base symbols in .env

### Finding the Right Yahoo Finance Symbols

Run the symbol finder script to identify valid Yahoo Finance tickers:

```bash
python3 find_yahoo_symbols.py
```

This script will:
- Test various symbol formats for common WIG20 stocks
- Show which symbols work and their company names
- Generate a ready-to-use list for your `.env` file
- Display recent price data to verify accuracy

### Stooq (Alternative)
- **Pros**: Comprehensive Polish market coverage, free, no API key required
- **Cons**: Less reliable, occasional downtime, basic CSV format
- **Format**: Symbol format `SYMBOL.PL` (e.g., `PKO.PL`)
- **URL Pattern**: `https://stooq.pl/q/d/l/?s=PKO.PL&d1=YYYYMMDD&d2=YYYYMMDD&i=d`

## 🔧 Configuration

### Environment Variables

Edit `.env` file to customize:

```bash
# Database
DB_HOST=localhost
DB_PORT=5432
DB_NAME=polish_stocks
DB_USER=trader
DB_PASSWORD=your_secure_password_here

# Data Loading
DATA_SOURCE=stooq  # Options: stooq, yahoo
START_DATE=2020-01-01
END_DATE=2025-10-19

# Stock Symbols (comma-separated)
STOCK_SYMBOLS=PKO,PZU,PKN,PEO,KGH,CCC,CDR,JSW,LPP
```

### WIG20 Components

Current major WIG20 components (base symbols for Yahoo Finance):
- **PKO** or **PKOBP** - PKO Bank Polski
- **PZU** - Powszechny Zakład Ubezpieczeń
- **PKNORLEN** - PKN Orlen
- **PEKAO** - Bank Pekao
- **KGHM** - KGHM Polska Miedź
- **CDPROJEKT** - CD Projekt
- **SANPL** - Santander Bank Polska
- **ORANGEPL** - Orange Polska
- **PGE** - PGE Polska Grupa Energetyczna
- **DINOPL** - Dino Polska
- **ALIOR** - Alior Bank
- **LPP** - LPP S.A.

**Important**: Run `python3 find_yahoo_symbols.py` to get the exact symbols that work with Yahoo Finance, as ticker formats can vary.

Update `STOCK_SYMBOLS` in `.env` with valid symbols from the finder script.

## 💾 Database Operations

### Connect to Database

```bash
# Using Docker
docker exec -it polish_stocks_db psql -U trader -d polish_stocks

# Using local psql
psql -h localhost -U trader -d polish_stocks
```

### Useful SQL Queries

**Check loaded stocks:**
```sql
SELECT symbol, name, 
       (SELECT COUNT(*) FROM historical_prices WHERE stock_id = s.stock_id) as price_records
FROM stocks s
ORDER BY symbol;
```

**View latest market data:**
```sql
SELECT * FROM latest_stock_data
ORDER BY date DESC, symbol;
```

**Check data quality logs:**
```sql
SELECT log_date, severity, message, details
FROM data_quality_log
ORDER BY log_date DESC
LIMIT 20;
```

**Find stocks with momentum signals:**
```sql
SELECT symbol, close, rsi_14, distance_from_ath_5y
FROM latest_stock_data
WHERE momentum_signal = TRUE;
```

## 📈 Data Loader Usage

### Basic Usage

```bash
# Load data with default settings from .env
python load_data.py
```

### Custom Loading

Edit `load_data.py` or modify `.env` for:
- Different date ranges
- Alternative data sources
- Specific stock symbols
- Custom sectors/classifications

### Loading Process

The loader performs these steps for each stock:

1. **Add Stock to Database**: Creates entry in `stocks` table
2. **Fetch Historical Data**: Downloads from Yahoo Finance (or Stooq)
3. **Validate Data**: Checks for completeness and anomalies
4. **Load to Database**: Inserts/updates `historical_prices` table
5. **Log Results**: Records success/failure in `data_quality_log`

### Finding Valid Symbols

**Before loading data, run the symbol finder:**

```bash
python3 find_yahoo_symbols.py
```

This will test various symbol formats and show you exactly which ones work. Copy the working symbols to your `.env` file.

### Example Output

```
============================================================
Loading data for PKNORLEN
============================================================
✓ Added stock: PKNORLEN (ID: 1)
  Fetching from Yahoo Finance: PKNORLEN.WA
  ✓ Retrieved 1456 records from 2020-01-02 to 2025-10-18
  ✓ Loaded 1456 price records

============================================================
Loading Summary
============================================================
✓ Successfully loaded: 9 stocks
✗ Failed: 1 stocks
Total: 10 stocks

✓ Data loading complete
```

## 🔍 Monitoring & Maintenance

### Database Health Check

```bash
docker-compose ps
docker exec polish_stocks_db pg_isready -U trader
```

### View Logs

```bash
docker-compose logs -f postgres
```

### Backup Database

```bash
docker exec polish_stocks_db pg_dump -U trader polish_stocks > backup_$(date +%Y%m%d).sql
```

### Restore Database

```bash
cat backup_20251019.sql | docker exec -i polish_stocks_db psql -U trader -d polish_stocks
```

### Clean Up

```bash
# Stop containers
docker-compose down

# Remove data volumes (WARNING: Deletes all data!)
docker-compose down -v
```

## ⚠️ Security Considerations

**Before Production Use:**

1. **Change Default Password**: Update `DB_PASSWORD` in `.env`
2. **Restrict Database Access**: Modify `docker-compose.yml` to limit port exposure
3. **Use Docker Secrets**: For production, use Docker secrets instead of environment variables
4. **Enable SSL**: Configure PostgreSQL to use SSL connections
5. **Regular Backups**: Implement automated backup strategy

## 🐛 Troubleshooting

### Database Connection Failed

```bash
# Check if container is running
docker-compose ps

# Restart database
docker-compose restart postgres

# Check logs
docker-compose logs postgres
```

### No Data Retrieved from Yahoo Finance

**Run the symbol finder first:**
```bash
python3 find_yahoo_symbols.py
```

This will show you:
- Which symbols are valid
- The exact format Yahoo Finance expects
- Recent price data to verify functionality

**Common issues:**
- **Wrong symbol format**: Yahoo Finance for Polish stocks requires `.WA` suffix (added automatically by script)
- **Symbol variations**: Some companies have multiple possible tickers (e.g., PKO vs PKOBP)
- **Delisted stocks**: Some older WIG20 components may no longer be available
- **Network issues**: Yahoo Finance occasionally has rate limits or temporary outages

**Solutions:**
1. Use the symbol finder to get valid symbols
2. Update your `.env` file with symbols that the finder confirms work
3. Try a smaller batch of stocks first (5-10 symbols)
4. Check if symbols are still actively traded on WSE

### All Stocks Failed to Load

If all 20 stocks failed:

1. **Verify symbols are correct:**
   ```bash
   python3 find_yahoo_symbols.py
   ```

2. **Test with a single known stock:**
   Edit `.env` to test just one stock:
   ```bash
   STOCK_SYMBOLS=PKNORLEN
   ```

3. **Check Yahoo Finance directly:**
   Visit https://finance.yahoo.com/quote/PKNORLEN.WA to verify the stock exists

4. **Try alternative data source:**
   Change in `.env`:
   ```bash
   DATA_SOURCE=stooq
   ```

5. **Check network connectivity:**
   ```bash
   curl -I https://finance.yahoo.com
   ```

### Import Errors in Python

```bash
# Reinstall dependencies
pip install --upgrade -r requirements.txt

# Verify Python version
python --version  # Should be 3.9+
```

### Stooq Data Issues (if using Stooq)

- Verify internet connection
- Check if symbol format is correct (`SYMBOL.PL`)
- Stooq occasionally has downtime - try again later
- Consider switching to Yahoo Finance: `DATA_SOURCE=yahoo`

## 📚 Next Steps

After setting up the database:

1. **Verify Data Quality**: Run queries to check data completeness
2. **Calculate Technical Indicators**: Implement RSI, MACD, ATR calculations
3. **Develop Backtesting Framework**: Test momentum strategies on historical data
4. **Build Signal Generation**: Create real-time trading signal system
5. **Implement Risk Management**: Position sizing and stop-loss logic
6. **Portfolio Tracking**: Monitor active positions and performance

## 📖 Academic Foundation

This system is based on comprehensive academic research supporting momentum trading strategies:

### Key Research Findings

- **Zaremba & Konieczka (2017)**: Momentum strategies generate 1.39% monthly excess returns in Polish markets
- **Hill (2019)**: RSI >50-70 combined with momentum signals effectively identifies strong uptrends
- **Zarattini et al. (2024)**: All-time high breakouts remain profitable across 75 years of data
- **Hurst, Ooi & Pedersen (2017)**: Time-series momentum shows positive Sharpe ratios over 137 years

### Strategy Components

1. **RSI Momentum Filter**: RSI > 50 indicates bull market conditions
2. **ATH Proximity**: Stocks within 5% of 5-year all-time highs
3. **Volume Confirmation**: Above-average volume on breakouts
4. **Trend Confirmation**: 50-day SMA > 200-day SMA (golden cross)
5. **Risk Management**: 2% portfolio risk per trade, 10x ATR trailing stops

## 🤝 Contributing

This is a personal trading system foundation. If you fork this project:

- Test thoroughly with paper trading before live use
- Adjust parameters for your risk tolerance
- Consider Polish market specifics (liquidity, volatility)
- Always maintain proper risk management

## ⚖️ Disclaimer

**This system is for educational and research purposes only.**

- Past performance does not guarantee future results
- Trading involves substantial risk of loss
- No trading system is guaranteed to be profitable
- Always consult with financial professionals before trading
- The authors are not responsible for trading losses

## 📄 License

This project is provided as-is for educational purposes. Use at your own risk.

## 📞 Support

For issues with:
- **Database setup**: Check Docker and PostgreSQL logs
- **Data loading**: Verify symbols and data source availability
- **Python dependencies**: Ensure Python 3.9+ and all packages installed

## 🔗 Useful Resources

- [Stooq Data API Documentation](https://stooq.com/db/h/)
- [Warsaw Stock Exchange](https://www.gpw.pl/en)
- [PostgreSQL Documentation](https://www.postgresql.org/docs/)
- [Docker Compose Reference](https://docs.docker.com/compose/)

## 📊 Database Statistics

Once data is loaded, check your database stats:

```sql
-- Total records by table
SELECT 
    'stocks' as table_name, COUNT(*) as records FROM stocks
UNION ALL
SELECT 
    'historical_prices', COUNT(*) FROM historical_prices
UNION ALL
SELECT 
    'technical_indicators', COUNT(*) FROM technical_indicators;

-- Data coverage by stock
SELECT 
    s.symbol,
    MIN(hp.date) as first_date,
    MAX(hp.date) as last_date,
    COUNT(*) as trading_days,
    ROUND(AVG(hp.volume), 0) as avg_volume
FROM stocks s
JOIN historical_prices hp ON s.stock_id = hp.stock_id
GROUP BY s.symbol
ORDER BY s.symbol;

-- Database size
SELECT pg_size_pretty(pg_database_size('polish_stocks')) as database_size;
```

---

**Version**: 1.0.0 (Database Setup Phase)  
**Last Updated**: October 2025  
**Status**: ✅ Production Ready for Data Storage# ATH_stock
