"""
Data Collector

Orchestrates data collection from Polymarket and Kalshi.
Stores data in SQLite for analysis.
"""

import sqlite3
import json
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional
from dataclasses import asdict

from .polymarket import PolymarketClient, Trader, Position, fetch_top_traders
from .kalshi import KalshiClient, KalshiMarket


# Database path
DB_PATH = Path(__file__).parent.parent.parent / "data" / "predictor.db"


def init_database():
    """Initialize SQLite database with required tables."""
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    # Traders table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS traders (
            wallet TEXT PRIMARY KEY,
            platform TEXT NOT NULL,
            username TEXT,
            rank INTEGER,
            pnl REAL,
            volume REAL,
            win_rate REAL,
            total_trades INTEGER,
            markets_traded INTEGER,
            verified INTEGER,
            first_seen TEXT,
            last_updated TEXT,
            metadata TEXT
        )
    """)
    
    # Positions table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS positions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            wallet TEXT NOT NULL,
            platform TEXT NOT NULL,
            market_slug TEXT NOT NULL,
            market_title TEXT,
            outcome TEXT,
            size REAL,
            avg_price REAL,
            current_price REAL,
            pnl REAL,
            pnl_percent REAL,
            captured_at TEXT,
            UNIQUE(wallet, market_slug, outcome, captured_at)
        )
    """)
    
    # Markets table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS markets (
            id TEXT PRIMARY KEY,
            platform TEXT NOT NULL,
            slug TEXT,
            title TEXT,
            category TEXT,
            yes_price REAL,
            no_price REAL,
            volume REAL,
            liquidity REAL,
            status TEXT,
            end_date TEXT,
            last_updated TEXT
        )
    """)
    
    # Signals table (generated signals for trading)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS signals (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            market_id TEXT NOT NULL,
            platform TEXT NOT NULL,
            direction TEXT NOT NULL,  -- 'yes' or 'no'
            conviction REAL,  -- 0 to 1
            source_traders INTEGER,  -- number of traders supporting this signal
            avg_position_size REAL,
            ars_score REAL,  -- Adaptive Risk Stabilizer score
            created_at TEXT,
            expires_at TEXT,
            status TEXT DEFAULT 'active'
        )
    """)
    
    # Trades table (bot's executed trades)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS bot_trades (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            signal_id INTEGER,
            market_id TEXT NOT NULL,
            platform TEXT NOT NULL,
            direction TEXT NOT NULL,
            size REAL,
            price REAL,
            status TEXT,  -- 'pending', 'executed', 'cancelled', 'settled'
            pnl REAL,
            executed_at TEXT,
            settled_at TEXT,
            wallet_tx_id TEXT,
            FOREIGN KEY (signal_id) REFERENCES signals(id)
        )
    """)
    
    conn.commit()
    conn.close()
    print(f"✓ Database initialized at {DB_PATH}")


class DataCollector:
    """Orchestrates data collection from all sources."""
    
    def __init__(self):
        self.poly_client = PolymarketClient()
        self.kalshi_client = KalshiClient()
        self.conn = sqlite3.connect(DB_PATH)
        self.conn.row_factory = sqlite3.Row
    
    def close(self):
        """Close database connection."""
        self.conn.close()
    
    def collect_polymarket_leaderboard(
        self,
        limit: int = 100,
        min_pnl: float = 1000,
        min_trades: int = 50
    ) -> list[Trader]:
        """
        Collect top traders from Polymarket leaderboard.
        
        Args:
            limit: Max traders to fetch
            min_pnl: Minimum PnL to qualify
            min_trades: Minimum trades to qualify
        
        Returns:
            List of qualified traders
        """
        print(f"📊 Fetching Polymarket leaderboard (top {limit})...")
        traders = self.poly_client.get_leaderboard(limit=limit)
        
        # Filter and enrich with stats
        qualified = []
        for trader in traders:
            if trader.pnl < min_pnl:
                continue
            
            # Get detailed stats
            try:
                stats = self.poly_client.get_trader_stats(trader.wallet)
                
                if stats["total_trades"] < min_trades:
                    continue
                
                # Store in database
                self._store_trader(trader, stats, "polymarket")
                qualified.append(trader)
                
                print(f"  ✓ {trader.username or trader.wallet[:10]}: ${trader.pnl:,.0f} PnL, {stats['win_rate']:.1%} win rate")
                
            except Exception as e:
                print(f"  ✗ Error processing {trader.wallet[:10]}: {e}")
        
        self.conn.commit()
        print(f"  → Qualified traders: {len(qualified)}/{len(traders)}")
        return qualified
    
    def collect_trader_positions(
        self,
        wallets: list[str],
        platform: str = "polymarket"
    ) -> dict[str, list[Position]]:
        """
        Collect current positions for multiple traders.
        
        Args:
            wallets: List of wallet addresses
            platform: Trading platform
        
        Returns:
            Dict mapping wallet -> positions
        """
        print(f"📈 Collecting positions for {len(wallets)} traders...")
        
        all_positions = {}
        timestamp = datetime.now().isoformat()
        
        for wallet in wallets:
            try:
                if platform == "polymarket":
                    positions = self.poly_client.get_trader_positions(wallet)
                else:
                    positions = []  # Kalshi doesn't expose individual positions
                
                all_positions[wallet] = positions
                
                # Store positions
                for pos in positions:
                    self._store_position(pos, platform, timestamp)
                
                print(f"  ✓ {wallet[:10]}: {len(positions)} positions")
                
            except Exception as e:
                print(f"  ✗ Error for {wallet[:10]}: {e}")
                all_positions[wallet] = []
        
        self.conn.commit()
        return all_positions
    
    def collect_kalshi_markets(self, limit: int = 200) -> list[KalshiMarket]:
        """
        Collect active markets from Kalshi.
        
        Args:
            limit: Max markets to fetch
        
        Returns:
            List of markets
        """
        print(f"📊 Fetching Kalshi markets (limit {limit})...")
        markets = self.kalshi_client.get_all_open_markets(max_markets=limit)
        
        for market in markets:
            self._store_market(market, "kalshi")
        
        self.conn.commit()
        print(f"  → Fetched {len(markets)} markets")
        return markets
    
    def _store_trader(self, trader: Trader, stats: dict, platform: str):
        """Store trader in database."""
        cursor = self.conn.cursor()
        
        now = datetime.now().isoformat()
        
        cursor.execute("""
            INSERT INTO traders (
                wallet, platform, username, rank, pnl, volume,
                win_rate, total_trades, markets_traded, verified,
                first_seen, last_updated, metadata
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(wallet) DO UPDATE SET
                rank = excluded.rank,
                pnl = excluded.pnl,
                volume = excluded.volume,
                win_rate = excluded.win_rate,
                total_trades = excluded.total_trades,
                markets_traded = excluded.markets_traded,
                last_updated = excluded.last_updated
        """, (
            trader.wallet,
            platform,
            trader.username,
            trader.rank,
            trader.pnl,
            trader.volume,
            stats.get("win_rate", 0),
            stats.get("total_trades", 0),
            stats.get("markets_traded", 0),
            1 if trader.verified else 0,
            now,
            now,
            json.dumps({"x_username": trader.x_username, "profile_image": trader.profile_image})
        ))
    
    def _store_position(self, position: Position, platform: str, timestamp: str):
        """Store position snapshot in database."""
        cursor = self.conn.cursor()
        
        cursor.execute("""
            INSERT OR IGNORE INTO positions (
                wallet, platform, market_slug, market_title, outcome,
                size, avg_price, current_price, pnl, pnl_percent, captured_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            position.wallet,
            platform,
            position.market_slug,
            position.market_title,
            position.outcome,
            position.size,
            position.avg_price,
            position.current_price,
            position.pnl,
            position.pnl_percent,
            timestamp
        ))
    
    def _store_market(self, market: KalshiMarket, platform: str):
        """Store market in database."""
        cursor = self.conn.cursor()
        
        cursor.execute("""
            INSERT INTO markets (
                id, platform, slug, title, category,
                yes_price, no_price, volume, liquidity, status,
                end_date, last_updated
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(id) DO UPDATE SET
                yes_price = excluded.yes_price,
                no_price = excluded.no_price,
                volume = excluded.volume,
                status = excluded.status,
                last_updated = excluded.last_updated
        """, (
            market.ticker,
            platform,
            market.ticker,
            market.title,
            market.category,
            market.yes_price / 100,  # Convert cents to dollars
            market.no_price / 100,
            market.volume,
            market.open_interest,
            market.status,
            market.close_time.isoformat() if market.close_time else None,
            datetime.now().isoformat()
        ))
    
    def get_top_traders(
        self,
        platform: str = "polymarket",
        min_win_rate: float = 0.55,
        min_pnl: float = 5000,
        limit: int = 20
    ) -> list[dict]:
        """
        Get top traders from database.
        
        Args:
            platform: Trading platform
            min_win_rate: Minimum win rate
            min_pnl: Minimum PnL
            limit: Max traders to return
        
        Returns:
            List of trader dicts
        """
        cursor = self.conn.cursor()
        
        cursor.execute("""
            SELECT * FROM traders
            WHERE platform = ?
              AND win_rate >= ?
              AND pnl >= ?
            ORDER BY pnl DESC
            LIMIT ?
        """, (platform, min_win_rate, min_pnl, limit))
        
        return [dict(row) for row in cursor.fetchall()]
    
    def get_aggregated_positions(
        self,
        min_traders: int = 3,
        min_conviction: float = 0.6
    ) -> list[dict]:
        """
        Get market positions aggregated across top traders.
        
        Args:
            min_traders: Minimum traders holding position
            min_conviction: Minimum conviction score
        
        Returns:
            List of aggregated position signals
        """
        cursor = self.conn.cursor()
        
        # Get most recent positions snapshot
        cursor.execute("""
            SELECT 
                p.market_slug,
                p.market_title,
                p.outcome,
                COUNT(DISTINCT p.wallet) as trader_count,
                AVG(p.size) as avg_size,
                AVG(p.current_price) as avg_price,
                SUM(p.size * p.current_price) as total_value,
                GROUP_CONCAT(DISTINCT p.wallet) as traders
            FROM positions p
            JOIN traders t ON p.wallet = t.wallet
            WHERE p.captured_at = (
                SELECT MAX(captured_at) FROM positions
            )
            AND t.win_rate >= 0.55
            AND p.size > 0
            GROUP BY p.market_slug, p.outcome
            HAVING trader_count >= ?
            ORDER BY trader_count DESC, total_value DESC
        """, (min_traders,))
        
        results = []
        for row in cursor.fetchall():
            row_dict = dict(row)
            
            # Calculate conviction based on trader agreement
            total_traders = len(row_dict["traders"].split(","))
            # Higher conviction if more high-quality traders agree
            conviction = min(total_traders / 10, 1.0)  # Scale: 10 traders = 100% conviction
            
            if conviction >= min_conviction:
                row_dict["conviction"] = conviction
                results.append(row_dict)
        
        return results


def run_collection_cycle():
    """Run a full data collection cycle."""
    print("\n" + "=" * 60)
    print("🚀 Starting Data Collection Cycle")
    print("=" * 60 + "\n")
    
    # Initialize
    init_database()
    collector = DataCollector()
    
    try:
        # 1. Collect Polymarket leaderboard
        traders = collector.collect_polymarket_leaderboard(
            limit=100,
            min_pnl=5000,
            min_trades=50
        )
        
        # 2. Collect positions for top traders
        wallets = [t.wallet for t in traders[:30]]  # Top 30
        collector.collect_trader_positions(wallets)
        
        # 3. Collect Kalshi markets
        collector.collect_kalshi_markets(limit=200)
        
        # 4. Generate aggregated signals
        print("\n📊 Generating aggregated signals...")
        signals = collector.get_aggregated_positions(min_traders=3)
        
        print(f"\n✓ Found {len(signals)} potential signals:")
        for sig in signals[:10]:
            print(f"  • {sig['market_title'][:40]}: {sig['outcome']} ({sig['trader_count']} traders, {sig['conviction']:.0%} conviction)")
        
    finally:
        collector.close()
    
    print("\n" + "=" * 60)
    print("✅ Collection cycle complete!")
    print("=" * 60 + "\n")


if __name__ == "__main__":
    run_collection_cycle()
