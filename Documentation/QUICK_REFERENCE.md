# Quick Reference Guide

## 🚀 Setup (First Time)

```bash
# 1. Quick automated setup
chmod +x quick_start.sh
./quick_start.sh

# OR manual setup:
cp .env.example .env
docker-compose up -d
pip install -r requirements.txt
python3 verify_setup.py
```

## 📊 Finding Valid Stock Symbols

```bash
# IMPORTANT: Run this BEFORE loading data!
python3 find_yahoo_symbols.py

# Copy the output symbols to .env file
# Example output:
# STOCK_SYMBOLS=PKNORLEN,PZU,KGHM,CDPROJEKT,PEKAO
```

## 💾 Loading Data

```bash
# Load historical data
python3 load_data.py

# Quick test with single stock (edit .env first):
# STOCK_SYMBOLS=PKNORLEN
python3 load_data.py
```

## 🐳 Docker Commands

```bash
# Start database
docker-compose up -d

# Stop database
docker-compose down

# View logs
docker-compose logs -f postgres

# Check status
docker-compose ps

# Restart database
docker-compose restart postgres

# Remove everything (including data!)
docker-compose down -v
```

## 🗄️ Database Access

```bash
# Connect to database via Docker
docker exec -it polish_stocks_db psql -U trader -d polish_stocks

# Connect via local psql (if installed)
psql -h localhost -U trader -d polish_stocks
# Password: check DB_PASSWORD in .env
```

## 📈 Useful SQL Queries

### Check loaded data
```sql
-- Count stocks
SELECT COUNT(*) FROM stocks;

-- View all stocks with record counts
SELECT 
    s.symbol, 
    s.name,
    COUNT(hp.price_id) as records,
    MIN(hp.date) as first_date,
    MAX(hp.date) as last_date
FROM stocks s
LEFT JOIN historical_prices hp ON s.stock_id = hp.stock_id
GROUP BY s.symbol, s.name
ORDER BY s.symbol;

-- Latest prices
SELECT * FROM latest_stock_data
ORDER BY date DESC;
```

### Check for data gaps
```sql
-- Find stocks with no price data
SELECT symbol, name 
FROM stocks 
WHERE stock_id NOT IN (SELECT DISTINCT stock_id FROM historical_prices);

-- Recent data quality logs
SELECT log_date, severity, message 
FROM data_quality_log 
ORDER BY log_date DESC 
LIMIT 10;
```

### Database statistics
```sql
-- Database size
SELECT pg_size_pretty(pg_database_size('polish_stocks'));

-- Records per table
SELECT 'stocks' as table_name, COUNT(*) FROM stocks
UNION ALL
SELECT 'historical_prices', COUNT(*) FROM historical_prices
UNION ALL
SELECT 'data_quality_log', COUNT(*) FROM data_quality_log;
```

## 🔍 Verification

```bash
# Verify database setup
python3 verify_setup.py

# Check if data loaded successfully
docker exec -it polish_stocks_db psql -U trader -d polish_stocks -c \
  "SELECT COUNT(*) as price_records FROM historical_prices;"
```

## 💾 Backup & Restore

```bash
# Backup database
docker exec polish_stocks_db pg_dump -U trader polish_stocks > backup.sql

# Restore from backup
cat backup.sql | docker exec -i polish_stocks_db psql -U trader -d polish_stocks

# Backup with timestamp
docker exec polish_stocks_db pg_dump -U trader polish_stocks > \
  backup_$(date +%Y%m%d_%H%M%S).sql
```

## ⚙️ Configuration

### Edit .env file
```bash
nano .env
# or
vim .env
```

### Key settings:
```bash
# Data source (yahoo recommended)
DATA_SOURCE=yahoo

# Date range
START_DATE=2020-01-01
END_DATE=2025-10-19

# Stock symbols (no .WA suffix needed)
STOCK_SYMBOLS=PKNORLEN,PZU,KGHM,CDPROJEKT

# Database credentials
DB_PASSWORD=your_secure_password
```

## 🔧 Troubleshooting Quick Fixes

```bash
# Can't connect to database?
docker-compose restart postgres
sleep 5
python3 verify_setup.py

# No data loading?
# 1. Find valid symbols first
python3 find_yahoo_symbols.py

# 2. Update .env with working symbols
nano .env

# 3. Try with just one stock
# Set: STOCK_SYMBOLS=PKNORLEN
python3 load_data.py

# Python package issues?
pip install --upgrade -r requirements.txt

# Clean start (deletes all data!)
docker-compose down -v
./quick_start.sh
```

## 📁 File Structure

```
.
├── docker-compose.yml          # Docker configuration
├── .env                        # Your configuration (don't commit!)
├── .env.example               # Configuration template
├── requirements.txt           # Python dependencies
├── init_db/
│   └── 01_create_schema.sql  # Database schema
├── load_data.py              # Data loading script
├── find_yahoo_symbols.py     # Symbol finder
├── verify_setup.py           # Setup verification
├── quick_start.sh            # Automated setup
└── README.md                 # Full documentation
```

## 🎯 Typical Workflow

1. **First time setup:**
   ```bash
   ./quick_start.sh
   ```

2. **Find valid symbols:**
   ```bash
   python3 find_yahoo_symbols.py
   # Copy symbols to .env
   ```

3. **Load data:**
   ```bash
   python3 load_data.py
   ```

4. **Verify:**
   ```bash
   python3 verify_setup.py
   ```

5. **Check results:**
   ```bash
   docker exec -it polish_stocks_db psql -U trader -d polish_stocks
   SELECT * FROM latest_stock_data;
   ```

## 🔄 Daily Updates

To update with latest prices:

```bash
# Update END_DATE in .env to today
# Then run:
python3 load_data.py

# The script automatically handles duplicates
# Only new data will be added
```

## 📞 Need Help?

1. Check logs: `docker-compose logs postgres`
2. Run verification: `python3 verify_setup.py`
3. Test symbols: `python3 find_yahoo_symbols.py`
4. Review README.md for detailed troubleshooting