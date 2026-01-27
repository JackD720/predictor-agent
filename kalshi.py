"""
Kalshi Data Client

Fetches market data and trades from Kalshi.
Note: Kalshi's leaderboard is opt-in and not as accessible via API,
so we focus on market data and public trade history.
"""

import requests
from typing import Optional
from dataclasses import dataclass
from datetime import datetime
import time


# API endpoints - uses elections subdomain but works for all markets
BASE_URL = "https://api.elections.kalshi.com/trade-api/v2"


@dataclass
class KalshiMarket:
    """Represents a Kalshi prediction market"""
    ticker: str
    event_ticker: str
    title: str
    subtitle: str
    yes_price: float  # in cents
    no_price: float
    volume: int
    open_interest: int
    status: str  # "open", "closed", "settled"
    result: Optional[str]  # "yes", "no", None
    close_time: Optional[datetime]
    category: str


@dataclass
class KalshiTrade:
    """Represents a public trade on Kalshi"""
    trade_id: str
    ticker: str
    side: str  # "yes" or "no"
    price: int  # in cents
    count: int  # number of contracts
    timestamp: datetime


@dataclass
class KalshiOrderbook:
    """Represents orderbook state"""
    ticker: str
    yes_bids: list[tuple[int, int]]  # (price_cents, quantity)
    no_bids: list[tuple[int, int]]


class KalshiClient:
    """Client for fetching data from Kalshi public APIs"""
    
    def __init__(self, rate_limit_delay: float = 0.5):
        self.session = requests.Session()
        self.rate_limit_delay = rate_limit_delay
        self._last_request = 0
    
    def _request(self, endpoint: str, params: dict = None) -> dict:
        """Make rate-limited request"""
        # Rate limiting
        elapsed = time.time() - self._last_request
        if elapsed < self.rate_limit_delay:
            time.sleep(self.rate_limit_delay - elapsed)
        
        url = f"{BASE_URL}{endpoint}"
        response = self.session.get(url, params=params)
        self._last_request = time.time()
        
        response.raise_for_status()
        return response.json()
    
    def get_markets(
        self,
        status: str = "open",
        limit: int = 100,
        cursor: Optional[str] = None,
        series_ticker: Optional[str] = None
    ) -> tuple[list[KalshiMarket], Optional[str]]:
        """
        Fetch markets from Kalshi.
        
        Args:
            status: "open", "closed", or "settled"
            limit: Max markets per page (max 1000)
            cursor: Pagination cursor
            series_ticker: Filter by series
        
        Returns:
            Tuple of (markets list, next cursor)
        """
        params = {
            "status": status,
            "limit": min(limit, 1000)
        }
        
        if cursor:
            params["cursor"] = cursor
        if series_ticker:
            params["series_ticker"] = series_ticker
        
        data = self._request("/markets", params)
        
        markets = []
        for item in data.get("markets", []):
            markets.append(KalshiMarket(
                ticker=item.get("ticker", ""),
                event_ticker=item.get("event_ticker", ""),
                title=item.get("title", ""),
                subtitle=item.get("subtitle", ""),
                yes_price=item.get("yes_price", 0),
                no_price=item.get("no_price", 0),
                volume=item.get("volume", 0),
                open_interest=item.get("open_interest", 0),
                status=item.get("status", ""),
                result=item.get("result"),
                close_time=datetime.fromisoformat(item["close_time"].replace("Z", "+00:00")) if item.get("close_time") else None,
                category=item.get("category", "")
            ))
        
        next_cursor = data.get("cursor")
        return markets, next_cursor
    
    def get_all_open_markets(self, max_markets: int = 500) -> list[KalshiMarket]:
        """
        Fetch all open markets with pagination.
        
        Args:
            max_markets: Maximum total markets to fetch
        
        Returns:
            List of all open markets
        """
        all_markets = []
        cursor = None
        
        while len(all_markets) < max_markets:
            markets, cursor = self.get_markets(
                status="open",
                limit=min(200, max_markets - len(all_markets)),
                cursor=cursor
            )
            all_markets.extend(markets)
            
            if not cursor or not markets:
                break
        
        return all_markets
    
    def get_market(self, ticker: str) -> Optional[KalshiMarket]:
        """
        Get a specific market by ticker.
        
        Args:
            ticker: Market ticker (e.g., "KXHIGHNY-25JAN26-B35")
        
        Returns:
            KalshiMarket or None if not found
        """
        try:
            data = self._request(f"/markets/{ticker}")
            item = data.get("market", {})
            
            return KalshiMarket(
                ticker=item.get("ticker", ""),
                event_ticker=item.get("event_ticker", ""),
                title=item.get("title", ""),
                subtitle=item.get("subtitle", ""),
                yes_price=item.get("yes_price", 0),
                no_price=item.get("no_price", 0),
                volume=item.get("volume", 0),
                open_interest=item.get("open_interest", 0),
                status=item.get("status", ""),
                result=item.get("result"),
                close_time=datetime.fromisoformat(item["close_time"].replace("Z", "+00:00")) if item.get("close_time") else None,
                category=item.get("category", "")
            )
        except Exception as e:
            print(f"Error fetching market {ticker}: {e}")
            return None
    
    def get_trades(
        self,
        ticker: Optional[str] = None,
        limit: int = 100,
        cursor: Optional[str] = None,
        min_ts: Optional[int] = None,
        max_ts: Optional[int] = None
    ) -> tuple[list[KalshiTrade], Optional[str]]:
        """
        Fetch public trade history.
        
        Args:
            ticker: Filter by market ticker
            limit: Max trades per page
            cursor: Pagination cursor
            min_ts: Minimum timestamp (Unix seconds)
            max_ts: Maximum timestamp (Unix seconds)
        
        Returns:
            Tuple of (trades list, next cursor)
        """
        params = {"limit": min(limit, 1000)}
        
        if ticker:
            params["ticker"] = ticker
        if cursor:
            params["cursor"] = cursor
        if min_ts:
            params["min_ts"] = min_ts
        if max_ts:
            params["max_ts"] = max_ts
        
        data = self._request("/markets/trades", params)
        
        trades = []
        for item in data.get("trades", []):
            trades.append(KalshiTrade(
                trade_id=item.get("trade_id", ""),
                ticker=item.get("ticker", ""),
                side=item.get("taker_side", ""),
                price=item.get("yes_price", 0),
                count=item.get("count", 0),
                timestamp=datetime.fromtimestamp(item.get("created_time", 0) / 1000) if item.get("created_time") else datetime.now()
            ))
        
        next_cursor = data.get("cursor")
        return trades, next_cursor
    
    def get_orderbook(self, ticker: str, depth: int = 10) -> Optional[KalshiOrderbook]:
        """
        Get current orderbook for a market.
        
        Args:
            ticker: Market ticker
            depth: Number of price levels to fetch
        
        Returns:
            KalshiOrderbook or None
        """
        try:
            data = self._request(f"/markets/{ticker}/orderbook", {"depth": depth})
            orderbook = data.get("orderbook", {})
            
            return KalshiOrderbook(
                ticker=ticker,
                yes_bids=[(b[0], b[1]) for b in orderbook.get("yes", [])],
                no_bids=[(b[0], b[1]) for b in orderbook.get("no", [])]
            )
        except Exception as e:
            print(f"Error fetching orderbook for {ticker}: {e}")
            return None
    
    def get_market_history(
        self,
        ticker: str,
        days: int = 7
    ) -> list[KalshiTrade]:
        """
        Get trade history for a specific market.
        
        Args:
            ticker: Market ticker
            days: Number of days of history
        
        Returns:
            List of trades
        """
        min_ts = int((datetime.now().timestamp() - days * 86400))
        
        all_trades = []
        cursor = None
        
        while True:
            trades, cursor = self.get_trades(
                ticker=ticker,
                limit=500,
                cursor=cursor,
                min_ts=min_ts
            )
            all_trades.extend(trades)
            
            if not cursor or not trades:
                break
        
        return all_trades
    
    def analyze_market_sentiment(self, ticker: str) -> dict:
        """
        Analyze recent trading sentiment for a market.
        
        Returns:
            Dict with buy/sell pressure, volume trends
        """
        trades = self.get_market_history(ticker, days=1)
        
        if not trades:
            return {"error": "No trades found"}
        
        # Analyze
        yes_volume = sum(t.count for t in trades if t.side == "yes")
        no_volume = sum(t.count for t in trades if t.side == "no")
        total_volume = yes_volume + no_volume
        
        avg_yes_price = sum(t.price * t.count for t in trades if t.side == "yes") / yes_volume if yes_volume else 0
        avg_no_price = sum(t.price * t.count for t in trades if t.side == "no") / no_volume if no_volume else 0
        
        return {
            "ticker": ticker,
            "total_trades": len(trades),
            "total_volume": total_volume,
            "yes_volume": yes_volume,
            "no_volume": no_volume,
            "yes_ratio": yes_volume / total_volume if total_volume else 0,
            "avg_yes_price": avg_yes_price,
            "avg_no_price": avg_no_price,
            "sentiment": "bullish" if yes_volume > no_volume else "bearish"
        }


def fetch_high_volume_markets(min_volume: int = 10000) -> list[KalshiMarket]:
    """
    Fetch markets with high trading volume.
    
    Args:
        min_volume: Minimum volume threshold
    
    Returns:
        List of high-volume markets sorted by volume
    """
    client = KalshiClient()
    markets = client.get_all_open_markets(max_markets=500)
    
    high_volume = [m for m in markets if m.volume >= min_volume]
    return sorted(high_volume, key=lambda m: m.volume, reverse=True)


if __name__ == "__main__":
    # Test the client
    from rich import print as rprint
    from rich.table import Table
    
    client = KalshiClient()
    
    # Fetch open markets
    print("\n📊 Fetching Kalshi Markets...\n")
    markets, _ = client.get_markets(status="open", limit=20)
    
    table = Table(title="Top 20 Kalshi Markets by Volume")
    table.add_column("Ticker", style="cyan", max_width=25)
    table.add_column("Title", style="green", max_width=35)
    table.add_column("Yes ¢", style="yellow")
    table.add_column("No ¢", style="yellow")
    table.add_column("Volume", style="blue")
    table.add_column("Category", style="magenta")
    
    # Sort by volume
    markets_sorted = sorted(markets, key=lambda m: m.volume, reverse=True)
    
    for m in markets_sorted[:20]:
        table.add_row(
            m.ticker[:25],
            m.title[:35],
            f"{m.yes_price}",
            f"{m.no_price}",
            f"{m.volume:,}",
            m.category
        )
    
    rprint(table)
    
    # Get orderbook for top market
    if markets_sorted:
        print(f"\n📈 Orderbook for {markets_sorted[0].ticker}...\n")
        orderbook = client.get_orderbook(markets_sorted[0].ticker)
        
        if orderbook:
            ob_table = Table(title=f"Orderbook: {markets_sorted[0].title[:50]}")
            ob_table.add_column("YES Bids", style="green")
            ob_table.add_column("NO Bids", style="red")
            
            max_levels = max(len(orderbook.yes_bids), len(orderbook.no_bids))
            for i in range(min(5, max_levels)):
                yes_str = f"{orderbook.yes_bids[i][0]}¢ x {orderbook.yes_bids[i][1]}" if i < len(orderbook.yes_bids) else ""
                no_str = f"{orderbook.no_bids[i][0]}¢ x {orderbook.no_bids[i][1]}" if i < len(orderbook.no_bids) else ""
                ob_table.add_row(yes_str, no_str)
            
            rprint(ob_table)
