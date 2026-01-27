"""
Polymarket Data Client

Fetches leaderboard, trader positions, and market data from Polymarket.
"""

import requests
from typing import Optional
from dataclasses import dataclass
from datetime import datetime
import time


# API endpoints
BASE_URL = "https://data-api.polymarket.com"
CLOB_URL = "https://clob.polymarket.com"


@dataclass
class Trader:
    """Represents a trader on the leaderboard"""
    rank: int
    wallet: str
    username: Optional[str]
    volume: float
    pnl: float
    profile_image: Optional[str]
    x_username: Optional[str]
    verified: bool


@dataclass
class Position:
    """Represents a trader's position in a market"""
    wallet: str
    market_slug: str
    market_title: str
    outcome: str  # "Yes" or "No"
    size: float  # Number of shares
    avg_price: float
    current_price: float
    initial_value: float
    current_value: float
    pnl: float
    pnl_percent: float


@dataclass
class Trade:
    """Represents a single trade"""
    wallet: str
    market_slug: str
    market_title: str
    outcome: str
    side: str  # "BUY" or "SELL"
    size: float
    price: float
    timestamp: datetime


@dataclass
class Market:
    """Represents a prediction market"""
    condition_id: str
    slug: str
    title: str
    description: str
    outcomes: list[str]
    outcome_prices: list[float]
    volume: float
    liquidity: float
    end_date: Optional[datetime]
    resolved: bool


class PolymarketClient:
    """Client for fetching data from Polymarket APIs"""
    
    def __init__(self, rate_limit_delay: float = 0.5):
        self.session = requests.Session()
        self.rate_limit_delay = rate_limit_delay
        self._last_request = 0
    
    def _request(self, url: str, params: dict = None) -> dict:
        """Make rate-limited request"""
        # Rate limiting
        elapsed = time.time() - self._last_request
        if elapsed < self.rate_limit_delay:
            time.sleep(self.rate_limit_delay - elapsed)
        
        response = self.session.get(url, params=params)
        self._last_request = time.time()
        
        response.raise_for_status()
        return response.json()
    
    def get_leaderboard(
        self,
        window: str = "all",  # "1d", "7d", "30d", "all"
        limit: int = 100
    ) -> list[Trader]:
        """
        Fetch top traders from leaderboard.
        
        Args:
            window: Time window for rankings
            limit: Max number of traders to fetch (max 100)
        
        Returns:
            List of Trader objects sorted by rank
        """
        url = f"{BASE_URL}/v1/leaderboard"
        params = {
            "window": window,
            "limit": min(limit, 100)
        }
        
        data = self._request(url, params)
        
        traders = []
        for item in data:
            traders.append(Trader(
                rank=int(item.get("rank", 0)),
                wallet=item.get("proxyWallet", ""),
                username=item.get("userName"),
                volume=float(item.get("vol", 0)),
                pnl=float(item.get("pnl", 0)),
                profile_image=item.get("profileImage"),
                x_username=item.get("xUsername"),
                verified=item.get("verifiedBadge", False)
            ))
        
        return sorted(traders, key=lambda t: t.rank)
    
    def get_trader_positions(
        self,
        wallet: str,
        active_only: bool = True
    ) -> list[Position]:
        """
        Fetch current positions for a trader.
        
        Args:
            wallet: Trader's wallet address
            active_only: Only return open positions
        
        Returns:
            List of Position objects
        """
        url = f"{BASE_URL}/v1/positions"
        params = {
            "user": wallet,
            "sortBy": "CURRENT",
            "sortDirection": "DESC"
        }
        
        if active_only:
            params["sizeThreshold"] = 0.01  # Filter dust positions
        
        data = self._request(url, params)
        
        positions = []
        for item in data:
            positions.append(Position(
                wallet=wallet,
                market_slug=item.get("slug", ""),
                market_title=item.get("title", ""),
                outcome=item.get("outcome", ""),
                size=float(item.get("size", 0)),
                avg_price=float(item.get("avgPrice", 0)),
                current_price=float(item.get("curPrice", 0)),
                initial_value=float(item.get("initialValue", 0)),
                current_value=float(item.get("currentValue", 0)),
                pnl=float(item.get("cashPnl", 0)),
                pnl_percent=float(item.get("percentPnl", 0))
            ))
        
        return positions
    
    def get_trader_trades(
        self,
        wallet: str,
        limit: int = 100,
        market_slug: Optional[str] = None
    ) -> list[Trade]:
        """
        Fetch trade history for a trader.
        
        Args:
            wallet: Trader's wallet address
            limit: Max trades to fetch
            market_slug: Filter by specific market
        
        Returns:
            List of Trade objects
        """
        url = f"{BASE_URL}/v1/activity"
        params = {
            "user": wallet,
            "type": "TRADE",
            "limit": limit,
            "sortBy": "TIMESTAMP",
            "sortDirection": "DESC"
        }
        
        if market_slug:
            params["slug"] = market_slug
        
        data = self._request(url, params)
        
        trades = []
        for item in data:
            trades.append(Trade(
                wallet=wallet,
                market_slug=item.get("slug", ""),
                market_title=item.get("title", ""),
                outcome=item.get("outcome", ""),
                side=item.get("side", ""),
                size=float(item.get("size", 0)),
                price=float(item.get("price", 0)),
                timestamp=datetime.fromtimestamp(item.get("timestamp", 0))
            ))
        
        return trades
    
    def get_trader_stats(self, wallet: str) -> dict:
        """
        Get aggregated stats for a trader.
        
        Returns dict with:
            - total_trades
            - win_rate
            - total_pnl
            - avg_position_size
            - markets_traded
        """
        positions = self.get_trader_positions(wallet, active_only=False)
        trades = self.get_trader_trades(wallet, limit=500)
        
        # Calculate stats
        total_trades = len(trades)
        winning_positions = sum(1 for p in positions if p.pnl > 0)
        total_positions = len([p for p in positions if abs(p.pnl) > 0.01])
        
        win_rate = winning_positions / total_positions if total_positions > 0 else 0
        total_pnl = sum(p.pnl for p in positions)
        avg_position_size = sum(p.initial_value for p in positions) / len(positions) if positions else 0
        markets_traded = len(set(p.market_slug for p in positions))
        
        return {
            "wallet": wallet,
            "total_trades": total_trades,
            "total_positions": total_positions,
            "win_rate": win_rate,
            "total_pnl": total_pnl,
            "avg_position_size": avg_position_size,
            "markets_traded": markets_traded
        }
    
    def get_markets(
        self,
        active_only: bool = True,
        limit: int = 100
    ) -> list[Market]:
        """
        Fetch available markets.
        
        Args:
            active_only: Only return non-resolved markets
            limit: Max markets to fetch
        
        Returns:
            List of Market objects
        """
        url = f"{CLOB_URL}/markets"
        params = {"limit": limit}
        
        if active_only:
            params["closed"] = "false"
        
        data = self._request(url, params)
        
        markets = []
        for item in data:
            markets.append(Market(
                condition_id=item.get("condition_id", ""),
                slug=item.get("market_slug", ""),
                title=item.get("question", ""),
                description=item.get("description", ""),
                outcomes=item.get("outcomes", []),
                outcome_prices=[float(p) for p in item.get("outcomePrices", [])],
                volume=float(item.get("volume", 0)),
                liquidity=float(item.get("liquidity", 0)),
                end_date=datetime.fromisoformat(item["end_date_iso"]) if item.get("end_date_iso") else None,
                resolved=item.get("closed", False)
            ))
        
        return markets
    
    def get_market_by_slug(self, slug: str) -> Optional[Market]:
        """Get a specific market by its slug"""
        markets = self.get_markets(active_only=False, limit=1000)
        for market in markets:
            if market.slug == slug:
                return market
        return None


# Convenience functions
def fetch_top_traders(limit: int = 50, min_pnl: float = 1000) -> list[Trader]:
    """
    Fetch top traders filtered by minimum PnL.
    
    Args:
        limit: Max traders to consider
        min_pnl: Minimum profit to qualify
    
    Returns:
        Filtered list of profitable traders
    """
    client = PolymarketClient()
    traders = client.get_leaderboard(window="all", limit=limit)
    return [t for t in traders if t.pnl >= min_pnl]


def fetch_trader_positions_batch(wallets: list[str]) -> dict[str, list[Position]]:
    """
    Fetch positions for multiple traders.
    
    Args:
        wallets: List of wallet addresses
    
    Returns:
        Dict mapping wallet -> positions
    """
    client = PolymarketClient()
    results = {}
    
    for wallet in wallets:
        try:
            positions = client.get_trader_positions(wallet)
            results[wallet] = positions
        except Exception as e:
            print(f"Error fetching positions for {wallet}: {e}")
            results[wallet] = []
    
    return results


if __name__ == "__main__":
    # Test the client
    from rich import print as rprint
    from rich.table import Table
    
    client = PolymarketClient()
    
    # Fetch leaderboard
    print("\n📊 Fetching Polymarket Leaderboard...\n")
    traders = client.get_leaderboard(limit=20)
    
    table = Table(title="Top 20 Polymarket Traders")
    table.add_column("Rank", style="cyan")
    table.add_column("Username", style="green")
    table.add_column("PnL", style="yellow")
    table.add_column("Volume", style="blue")
    table.add_column("Verified", style="magenta")
    
    for t in traders[:20]:
        table.add_row(
            str(t.rank),
            t.username or t.wallet[:10] + "...",
            f"${t.pnl:,.2f}",
            f"${t.volume:,.2f}",
            "✓" if t.verified else ""
        )
    
    rprint(table)
    
    # Fetch positions for top trader
    if traders:
        print(f"\n📈 Fetching positions for top trader: {traders[0].username or traders[0].wallet[:10]}...\n")
        positions = client.get_trader_positions(traders[0].wallet)
        
        pos_table = Table(title=f"Positions for {traders[0].username or 'Top Trader'}")
        pos_table.add_column("Market", style="cyan", max_width=40)
        pos_table.add_column("Outcome", style="green")
        pos_table.add_column("Size", style="yellow")
        pos_table.add_column("Avg Price", style="blue")
        pos_table.add_column("Current", style="blue")
        pos_table.add_column("PnL", style="magenta")
        
        for p in positions[:10]:
            pnl_color = "green" if p.pnl > 0 else "red"
            pos_table.add_row(
                p.market_title[:40],
                p.outcome,
                f"{p.size:,.2f}",
                f"{p.avg_price:.2f}",
                f"{p.current_price:.2f}",
                f"[{pnl_color}]${p.pnl:,.2f}[/{pnl_color}]"
            )
        
        rprint(pos_table)
