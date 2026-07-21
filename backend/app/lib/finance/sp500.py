"""Curated S&P 500 constituent list for the heatmap — port of src/lib/finance/sp500.ts."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass
class SP500Stock:
    symbol: str
    name: str
    sector: str


SP500_STOCKS: list[SP500Stock] = [
    # Technology
    SP500Stock("AAPL", "Apple", "Technology"),
    SP500Stock("MSFT", "Microsoft", "Technology"),
    SP500Stock("NVDA", "NVIDIA", "Technology"),
    SP500Stock("GOOGL", "Alphabet", "Technology"),
    SP500Stock("META", "Meta", "Technology"),
    SP500Stock("AVGO", "Broadcom", "Technology"),
    SP500Stock("ORCL", "Oracle", "Technology"),
    SP500Stock("CSCO", "Cisco", "Technology"),
    SP500Stock("ADBE", "Adobe", "Technology"),
    SP500Stock("CRM", "Salesforce", "Technology"),
    SP500Stock("INTC", "Intel", "Technology"),
    SP500Stock("AMD", "AMD", "Technology"),
    SP500Stock("IBM", "IBM", "Technology"),
    SP500Stock("QCOM", "Qualcomm", "Technology"),
    SP500Stock("NOW", "ServiceNow", "Technology"),
    # Consumer Discretionary
    SP500Stock("AMZN", "Amazon", "Consumer Discretionary"),
    SP500Stock("TSLA", "Tesla", "Consumer Discretionary"),
    SP500Stock("HD", "Home Depot", "Consumer Discretionary"),
    SP500Stock("MCD", "McDonald's", "Consumer Discretionary"),
    SP500Stock("NKE", "Nike", "Consumer Discretionary"),
    SP500Stock("SBUX", "Starbucks", "Consumer Discretionary"),
    SP500Stock("LOW", "Lowe's", "Consumer Discretionary"),
    SP500Stock("TJX", "TJX Companies", "Consumer Discretionary"),
    SP500Stock("BKNG", "Booking Holdings", "Consumer Discretionary"),
    SP500Stock("CMG", "Chipotle", "Consumer Discretionary"),
    # Communication Services
    SP500Stock("NFLX", "Netflix", "Communication Services"),
    SP500Stock("DIS", "Disney", "Communication Services"),
    SP500Stock("CMCSA", "Comcast", "Communication Services"),
    SP500Stock("VZ", "Verizon", "Communication Services"),
    SP500Stock("T", "AT&T", "Communication Services"),
    SP500Stock("TMUS", "T-Mobile", "Communication Services"),
    # Financials
    SP500Stock("BRK.B", "Berkshire Hathaway", "Financials"),
    SP500Stock("JPM", "JPMorgan Chase", "Financials"),
    SP500Stock("V", "Visa", "Financials"),
    SP500Stock("MA", "Mastercard", "Financials"),
    SP500Stock("BAC", "Bank of America", "Financials"),
    SP500Stock("WFC", "Wells Fargo", "Financials"),
    SP500Stock("GS", "Goldman Sachs", "Financials"),
    SP500Stock("MS", "Morgan Stanley", "Financials"),
    SP500Stock("AXP", "American Express", "Financials"),
    SP500Stock("BLK", "BlackRock", "Financials"),
    SP500Stock("C", "Citigroup", "Financials"),
    SP500Stock("SCHW", "Charles Schwab", "Financials"),
    # Healthcare
    SP500Stock("LLY", "Eli Lilly", "Healthcare"),
    SP500Stock("UNH", "UnitedHealth", "Healthcare"),
    SP500Stock("JNJ", "Johnson & Johnson", "Healthcare"),
    SP500Stock("ABBV", "AbbVie", "Healthcare"),
    SP500Stock("MRK", "Merck", "Healthcare"),
    SP500Stock("PFE", "Pfizer", "Healthcare"),
    SP500Stock("TMO", "Thermo Fisher", "Healthcare"),
    SP500Stock("ABT", "Abbott", "Healthcare"),
    SP500Stock("DHR", "Danaher", "Healthcare"),
    SP500Stock("AMGN", "Amgen", "Healthcare"),
    # Consumer Staples
    SP500Stock("WMT", "Walmart", "Consumer Staples"),
    SP500Stock("PG", "Procter & Gamble", "Consumer Staples"),
    SP500Stock("KO", "Coca-Cola", "Consumer Staples"),
    SP500Stock("PEP", "PepsiCo", "Consumer Staples"),
    SP500Stock("COST", "Costco", "Consumer Staples"),
    SP500Stock("PM", "Philip Morris", "Consumer Staples"),
    SP500Stock("MO", "Altria", "Consumer Staples"),
    SP500Stock("CL", "Colgate-Palmolive", "Consumer Staples"),
    # Energy
    SP500Stock("XOM", "Exxon Mobil", "Energy"),
    SP500Stock("CVX", "Chevron", "Energy"),
    SP500Stock("COP", "ConocoPhillips", "Energy"),
    SP500Stock("SLB", "Schlumberger", "Energy"),
    SP500Stock("EOG", "EOG Resources", "Energy"),
    SP500Stock("MPC", "Marathon Petroleum", "Energy"),
    # Industrials
    SP500Stock("BA", "Boeing", "Industrials"),
    SP500Stock("UPS", "UPS", "Industrials"),
    SP500Stock("HON", "Honeywell", "Industrials"),
    SP500Stock("CAT", "Caterpillar", "Industrials"),
    SP500Stock("GE", "General Electric", "Industrials"),
    SP500Stock("MMM", "3M", "Industrials"),
    SP500Stock("LMT", "Lockheed Martin", "Industrials"),
    SP500Stock("RTX", "Raytheon", "Industrials"),
    # Materials
    SP500Stock("LIN", "Linde", "Materials"),
    SP500Stock("APD", "Air Products", "Materials"),
    SP500Stock("SHW", "Sherwin-Williams", "Materials"),
    SP500Stock("FCX", "Freeport-McMoRan", "Materials"),
    SP500Stock("NEM", "Newmont", "Materials"),
    # Real Estate
    SP500Stock("AMT", "American Tower", "Real Estate"),
    SP500Stock("PLD", "Prologis", "Real Estate"),
    SP500Stock("CCI", "Crown Castle", "Real Estate"),
    SP500Stock("EQIX", "Equinix", "Real Estate"),
    SP500Stock("SPG", "Simon Property", "Real Estate"),
    # Utilities
    SP500Stock("NEE", "NextEra Energy", "Utilities"),
    SP500Stock("DUK", "Duke Energy", "Utilities"),
    SP500Stock("SO", "Southern Company", "Utilities"),
    SP500Stock("D", "Dominion Energy", "Utilities"),
    SP500Stock("AEP", "American Electric", "Utilities"),
]
