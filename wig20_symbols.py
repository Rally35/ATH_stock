"""
WIG20 Stock Symbol Mapper
Maps Polish stock symbols to Yahoo Finance tickers
Only includes liquid, tradeable WIG20 stocks
"""

# WIG20 stocks with verified Yahoo Finance symbols
# Format: 'SHORT_SYMBOL': ('YAHOO_SYMBOL', 'Company Name')

WIG20_STOCKS = {
    # Banking & Finance
    'PKO': ('PKOBP.WA', 'PKO Bank Polski'),
    'PEO': ('PEKAO.WA', 'Bank Pekao'),
    'ALR': ('ALIOR.WA', 'Alior Bank'),
    'BHW': ('BHW.WA', 'Bank Handlowy'),
    'MBK': ('MBANK.WA', 'mBank'),
    'SPL': ('SANPL.WA', 'Santander Polska'),
    'ING': ('INGBSK.WA', 'ING Bank Śląski'),
    
    # Energy
    'PKN': ('PKNORLEN.WA', 'PKN Orlen'),
    'PGE': ('PGE.WA', 'PGE'),
    'PGN': ('PGNIG.WA', 'PGNiG'),
    'LPP': ('LPP.WA', 'LPP'),
    'JSW': ('JSW.WA', 'JSW'),
    'KGH': ('KGHM.WA', 'KGHM'),
    
    # Technology & Retail
    'CDR': ('CDPROJEKT.WA', 'CD Projekt'),
    '11B': ('11BIT.WA', '11 bit studios'),
    'ALE': ('ALLEGRO.WA', 'Allegro'),
    'ACP': ('ASSECOPOL.WA', 'Asseco Poland'),
    'DNP': ('DINOPL.WA', 'Dino Polska'),
    
    # Telecom
    'OPL': ('ORANGEPL.WA', 'Orange Polska'),
    
    # Construction & Industry
    'BDX': ('BUDIMEX.WA', 'Budimex'),
    
    # Insurance
    'PZU': ('PZU.WA', 'PZU'),
}

# Additional liquid stocks (WIG30)
ADDITIONAL_LIQUID = {
    'CCC': ('CCC.WA', 'CCC'),
    'EUR': ('EUROCASH.WA', 'Eurocash'),
    'KTY': ('KETY.WA', 'Kęty'),
    'LWB': ('LIVECHAT.WA', 'LiveChat Software'),
    'XTB': ('XTB.WA', 'XTB'),
    'TEN': ('TSGAMES.WA', 'Ten Square Games'),
}

# All valid stocks combined
ALL_VALID_STOCKS = {**WIG20_STOCKS, **ADDITIONAL_LIQUID}


def get_yahoo_symbol(short_symbol: str) -> str:
    """
    Convert short symbol to Yahoo Finance symbol
    Example: 'PKO' -> 'PKOBP.WA'
    """
    if short_symbol in ALL_VALID_STOCKS:
        return ALL_VALID_STOCKS[short_symbol][0]
    return None


def get_company_name(short_symbol: str) -> str:
    """Get company name for a symbol"""
    if short_symbol in ALL_VALID_STOCKS:
        return ALL_VALID_STOCKS[short_symbol][1]
    return None


def get_all_symbols() -> dict:
    """Get all valid symbols"""
    return ALL_VALID_STOCKS


def get_wig20_symbols() -> dict:
    """Get only WIG20 symbols"""
    return WIG20_STOCKS


def print_valid_symbols():
    """Print all valid symbols for .env file"""
    print("\n" + "="*70)
    print("VALID POLISH STOCK SYMBOLS FOR YAHOO FINANCE")
    print("="*70)
    
    print("\n📊 WIG20 Stocks (Most Liquid - RECOMMENDED):")
    print("-" * 70)
    wig20_list = []
    for short, (yahoo, name) in WIG20_STOCKS.items():
        print(f"  {short:<6} → {yahoo:<20} {name}")
        wig20_list.append(short)
    
    print("\n💡 For your .env file (WIG20 only):")
    print(f"STOCK_SYMBOLS={','.join(wig20_list)}")
    
    print("\n\n📈 Additional Liquid Stocks (WIG30):")
    print("-" * 70)
    additional_list = []
    for short, (yahoo, name) in ADDITIONAL_LIQUID.items():
        print(f"  {short:<6} → {yahoo:<20} {name}")
        additional_list.append(short)
    
    print("\n💡 For your .env file (All liquid stocks):")
    all_symbols = wig20_list + additional_list
    print(f"STOCK_SYMBOLS={','.join(all_symbols)}")
    
    print("\n" + "="*70)
    print(f"Total valid symbols: {len(ALL_VALID_STOCKS)}")
    print("="*70 + "\n")


if __name__ == "__main__":
    print_valid_symbols()
