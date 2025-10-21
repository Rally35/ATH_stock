-- Create schema for Polish stocks momentum trading system
-- This schema stores historical OHLCV data and computed technical indicators

-- Table: stocks - Master list of Polish stocks
CREATE TABLE IF NOT EXISTS stocks (
    stock_id SERIAL PRIMARY KEY,
    symbol VARCHAR(20) NOT NULL UNIQUE,
    name VARCHAR(200),
    exchange VARCHAR(50) DEFAULT 'WSE',
    sector VARCHAR(100),
    is_active BOOLEAN DEFAULT TRUE,
    added_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    last_updated TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Table: historical_prices - OHLCV data
CREATE TABLE IF NOT EXISTS historical_prices (
    price_id BIGSERIAL PRIMARY KEY,
    stock_id INTEGER NOT NULL REFERENCES stocks(stock_id) ON DELETE CASCADE,
    date DATE NOT NULL,
    open NUMERIC(12, 4) NOT NULL,
    high NUMERIC(12, 4) NOT NULL,
    low NUMERIC(12, 4) NOT NULL,
    close NUMERIC(12, 4) NOT NULL,
    volume BIGINT NOT NULL,
    adjusted_close NUMERIC(12, 4),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(stock_id, date)
);

-- Table: technical_indicators - Computed technical indicators
CREATE TABLE IF NOT EXISTS technical_indicators (
    indicator_id BIGSERIAL PRIMARY KEY,
    stock_id INTEGER NOT NULL REFERENCES stocks(stock_id) ON DELETE CASCADE,
    date DATE NOT NULL,
    rsi_14 NUMERIC(8, 4),
    sma_50 NUMERIC(12, 4),
    sma_200 NUMERIC(12, 4),
    ema_20 NUMERIC(12, 4),
    macd NUMERIC(12, 4),
    macd_signal NUMERIC(12, 4),
    macd_histogram NUMERIC(12, 4),
    atr_14 NUMERIC(12, 4),
    volume_ma_20 BIGINT,
    ath_1y NUMERIC(12, 4),
    ath_2y NUMERIC(12, 4),
    ath_5y NUMERIC(12, 4),
    ath_all_time NUMERIC(12, 4),
    distance_from_ath_5y NUMERIC(8, 4),
    computed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(stock_id, date)
);

-- Table: data_quality_log - Track data loading and quality issues
CREATE TABLE IF NOT EXISTS data_quality_log (
    log_id SERIAL PRIMARY KEY,
    stock_id INTEGER REFERENCES stocks(stock_id),
    log_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    log_type VARCHAR(50), -- 'data_load', 'missing_data', 'anomaly', 'validation_error'
    severity VARCHAR(20), -- 'info', 'warning', 'error'
    message TEXT,
    details JSONB
);

-- Indexes for performance optimization
CREATE INDEX IF NOT EXISTS idx_historical_prices_stock_date ON historical_prices(stock_id, date DESC);
CREATE INDEX IF NOT EXISTS idx_historical_prices_date ON historical_prices(date DESC);
CREATE INDEX IF NOT EXISTS idx_technical_indicators_stock_date ON technical_indicators(stock_id, date DESC);
CREATE INDEX IF NOT EXISTS idx_stocks_symbol ON stocks(symbol);
CREATE INDEX IF NOT EXISTS idx_stocks_active ON stocks(is_active) WHERE is_active = TRUE;
CREATE INDEX IF NOT EXISTS idx_data_quality_log_date ON data_quality_log(log_date DESC);

-- Create view for latest prices with indicators
CREATE OR REPLACE VIEW latest_stock_data AS
SELECT 
    s.symbol,
    s.name,
    s.sector,
    hp.date,
    hp.close,
    hp.volume,
    ti.rsi_14,
    ti.sma_50,
    ti.sma_200,
    ti.macd,
    ti.macd_signal,
    ti.atr_14,
    ti.ath_5y,
    ti.distance_from_ath_5y,
    CASE 
        WHEN ti.rsi_14 > 50 AND ti.sma_50 > ti.sma_200 
             AND ti.distance_from_ath_5y <= 0.05 
        THEN TRUE 
        ELSE FALSE 
    END AS momentum_signal
FROM stocks s
JOIN LATERAL (
    SELECT * FROM historical_prices 
    WHERE stock_id = s.stock_id 
    ORDER BY date DESC 
    LIMIT 1
) hp ON TRUE
LEFT JOIN technical_indicators ti ON ti.stock_id = s.stock_id AND ti.date = hp.date
WHERE s.is_active = TRUE
ORDER BY hp.date DESC, s.symbol;

COMMENT ON TABLE stocks IS 'Master list of Polish stocks traded on Warsaw Stock Exchange';
COMMENT ON TABLE historical_prices IS 'Historical OHLCV data in PLN';
COMMENT ON TABLE technical_indicators IS 'Computed technical indicators for momentum strategy';
COMMENT ON TABLE data_quality_log IS 'Data quality tracking and audit log';
COMMENT ON VIEW latest_stock_data IS 'Latest prices with technical indicators and momentum signals';