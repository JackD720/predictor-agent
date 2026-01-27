"""
Signal Generator

Analyzes top trader positions and generates trading signals
based on consensus among consistently profitable traders.
"""

from dataclasses import dataclass
from typing import Optional
from collections import defaultdict
import time

from polymarket import PolymarketClient, Trader, Position
from stabilizer import AdaptiveRiskStabilizer, ARSConfig, create_ars


@dataclass
class Signal:
    """A trading signal based on top trader consensus"""
    market_slug: str
    market_title: str
    direction: str  # "Yes" or "No"
    conviction: float  # 0-1 based on trader agreement
    num_traders: int  # How many top traders hold this position
    total_size: float  # Combined position size in dollars
    avg_entry_price: float
    current_price: float
    expected_edge: float  # Current price vs avg entry
    traders: list[str]  # Usernames of traders holding this
    
    # ARS fields
    ars_score: float = 0.0  # 0-1, higher = better opportunity
    recommended_size: float = 0.0  # Recommended position size
    entry_quality: str = "unknown"  # "good", "fair", "late"
    
    def __str__(self):
        return f"{self.direction} on '{self.market_title[:40]}' | {self.conviction:.0%} conviction | {self.num_traders} traders | ${self.total_size:,.0f} total"


@dataclass 
class TraderScore:
    """Scored trader for ranking"""
    wallet: str
    username: str
    pnl: float
    volume: float
    win_rate: float  # Estimated from positions
    consistency: float  # Score 0-1
    final_score: float


class SignalGenerator:
    """Generates trading signals from top trader consensus"""
    
    def __init__(self):
        self.client = PolymarketClient()
        self.ars = create_ars()  # Adaptive Risk Stabilizer
        self.traders: list[Trader] = []
        self.trader_scores: list[TraderScore] = []
        self.positions: dict[str, list[Position]] = {}
        
    def fetch_top_traders(self, limit: int = 50) -> list[Trader]:
        """Fetch and store top traders from leaderboard"""
        print(f"\n📊 Fetching top {limit} traders...")
        self.traders = self.client.get_leaderboard(limit=limit)
        print(f"   Found {len(self.traders)} traders")
        return self.traders
    
    def score_traders(self, min_pnl: float = 10000) -> list[TraderScore]:
        """
        Score traders by consistency, not just PnL.
        
        Factors:
        - PnL (but diminishing returns after certain point)
        - Volume efficiency (PnL / Volume ratio)
        - Win rate from positions
        """
        print(f"\n🎯 Scoring traders (min PnL: ${min_pnl:,})...")
        
        scored = []
        for trader in self.traders:
            if trader.pnl < min_pnl:
                continue
            
            # Volume efficiency (how much profit per dollar traded)
            efficiency = trader.pnl / trader.volume if trader.volume > 0 else 0
            
            # Normalize PnL (diminishing returns after $100k)
            pnl_score = min(trader.pnl / 100000, 1.0)
            
            # Efficiency score (good traders make 5-15% on volume)
            efficiency_score = min(efficiency / 0.10, 1.0)
            
            # Combined score
            final_score = (pnl_score * 0.4) + (efficiency_score * 0.6)
            
            scored.append(TraderScore(
                wallet=trader.wallet,
                username=trader.username or trader.wallet[:10],
                pnl=trader.pnl,
                volume=trader.volume,
                win_rate=0,  # Will calculate from positions
                consistency=efficiency_score,
                final_score=final_score
            ))
        
        # Sort by final score (not raw PnL)
        self.trader_scores = sorted(scored, key=lambda x: x.final_score, reverse=True)
        
        print(f"   Qualified traders: {len(self.trader_scores)}")
        for i, t in enumerate(self.trader_scores[:10]):
            print(f"   {i+1}. {t.username}: ${t.pnl:,.0f} PnL, {t.consistency:.1%} efficiency, {t.final_score:.2f} score")
        
        return self.trader_scores
    
    def fetch_positions(self, top_n: int = 20) -> dict[str, list[Position]]:
        """Fetch positions for top N scored traders"""
        print(f"\n📈 Fetching positions for top {top_n} traders...")
        
        self.positions = {}
        for i, trader in enumerate(self.trader_scores[:top_n]):
            try:
                positions = self.client.get_trader_positions(trader.wallet)
                # Filter to meaningful positions (>$100 value)
                positions = [p for p in positions if p.current_value > 100]
                self.positions[trader.wallet] = positions
                print(f"   {i+1}. {trader.username}: {len(positions)} positions")
                time.sleep(0.3)  # Rate limiting
            except Exception as e:
                print(f"   ✗ Error for {trader.username}: {e}")
                self.positions[trader.wallet] = []
        
        return self.positions
    
    def evaluate_entry_quality(self, avg_entry: float, current_price: float) -> tuple[str, float]:
        """
        Evaluate if it's still a good time to enter.
        
        Returns:
            (quality_label, quality_score)
            - "good": Entry close to current price, traders haven't profited much yet
            - "fair": Some profit taken, but still reasonable entry
            - "late": Traders already up big, probably too late
        """
        if avg_entry <= 0 or current_price <= 0:
            return "unknown", 0.5
        
        # Calculate how much price has moved since avg entry
        price_move = (current_price - avg_entry) / avg_entry
        
        if price_move < 0.15:  # Less than 15% move
            return "good", 1.0
        elif price_move < 0.50:  # 15-50% move
            return "fair", 0.7
        elif price_move < 1.0:  # 50-100% move
            return "late", 0.4
        else:  # More than 100% move (doubled+)
            return "very_late", 0.1
    
    def filter_resolved_markets(self, signals: list[Signal]) -> list[Signal]:
        """Filter out markets that are likely resolved (price at 0, 1, or very close)"""
        filtered = []
        for sig in signals:
            # If price is at extreme (likely resolved), skip
            if sig.current_price >= 0.98 or sig.current_price <= 0.02:
                continue
            filtered.append(sig)
        return filtered
    
    def apply_ars_scoring(self, signals: list[Signal]) -> list[Signal]:
        """Apply ARS scoring to filter and rank signals"""
        print(f"\n🔒 Applying ARS filtering to {len(signals)} signals...")
        
        scored_signals = []
        
        for sig in signals:
            # Get trader data for ARS
            supporting_traders = []
            for wallet, positions in self.positions.items():
                trader = next((t for t in self.trader_scores if t.wallet == wallet), None)
                if not trader:
                    continue
                for pos in positions:
                    if pos.market_slug == sig.market_slug and pos.outcome == sig.direction:
                        supporting_traders.append({
                            'wallet': wallet,
                            'position_size': pos.current_value,
                            'pnl': pos.pnl,
                            'win_rate': trader.consistency
                        })
            
            # Calculate entry quality
            entry_quality, entry_score = self.evaluate_entry_quality(
                sig.avg_entry_price, 
                sig.current_price
            )
            sig.entry_quality = entry_quality
            
            # Process through ARS
            ars_signal = self.ars.process_signal(
                market_id=sig.market_slug,
                market_title=sig.market_title,
                direction=sig.direction,
                supporting_traders=supporting_traders,
                current_exposure=0.0
            )
            
            # Combine scores
            # Weight: 40% ARS conviction, 30% entry quality, 30% trader agreement
            sig.ars_score = (
                ars_signal.ars_conviction * 0.4 +
                entry_score * 0.3 +
                sig.conviction * 0.3
            )
            sig.recommended_size = ars_signal.recommended_size
            
            scored_signals.append(sig)
        
        # Sort by ARS score
        scored_signals = sorted(scored_signals, key=lambda x: x.ars_score, reverse=True)
        
        return scored_signals
    
    def aggregate_signals(self, min_traders: int = 2, min_conviction: float = 0.1) -> list[Signal]:
        """
        Aggregate positions to find consensus signals.
        
        A signal is generated when multiple top traders hold the same position.
        """
        print(f"\n🔍 Aggregating signals (min {min_traders} traders, {min_conviction:.0%} conviction)...")
        
        # Group positions by market + direction
        market_positions = defaultdict(list)
        
        for wallet, positions in self.positions.items():
            trader = next((t for t in self.trader_scores if t.wallet == wallet), None)
            if not trader:
                continue
                
            for pos in positions:
                key = (pos.market_slug, pos.outcome)
                market_positions[key].append({
                    'trader': trader,
                    'position': pos
                })
        
        # Generate signals where multiple traders agree
        signals = []
        total_traders = len(self.positions)
        
        print(f"   Total unique market-positions: {len(market_positions)}")
        
        # Show markets with most trader overlap
        overlap_counts = [(k, len(v)) for k, v in market_positions.items()]
        overlap_counts.sort(key=lambda x: x[1], reverse=True)
        print(f"   Top overlapping positions:")
        for (slug, outcome), count in overlap_counts[:10]:
            print(f"      {count} traders: {outcome} on {slug[:40]}")
        
        for (market_slug, outcome), holdings in market_positions.items():
            num_traders = len(holdings)
            
            if num_traders < min_traders:
                continue
            
            # Calculate conviction (what % of top traders hold this)
            conviction = num_traders / total_traders
            
            if conviction < min_conviction:
                continue
            
            # Aggregate stats
            total_size = sum(h['position'].current_value for h in holdings)
            total_shares = sum(h['position'].size for h in holdings)
            avg_entry = sum(h['position'].avg_price * h['position'].size for h in holdings) / total_shares if total_shares > 0 else 0
            current_price = holdings[0]['position'].current_price
            
            # Expected edge (if avg entry is below current, they're in profit)
            expected_edge = (current_price - avg_entry) / avg_entry if avg_entry > 0 else 0
            
            signal = Signal(
                market_slug=market_slug,
                market_title=holdings[0]['position'].market_title,
                direction=outcome,
                conviction=conviction,
                num_traders=num_traders,
                total_size=total_size,
                avg_entry_price=avg_entry,
                current_price=current_price,
                expected_edge=expected_edge,
                traders=[h['trader'].username for h in holdings]
            )
            signals.append(signal)
        
        # Sort by conviction then total size
        signals = sorted(signals, key=lambda x: (x.conviction, x.total_size), reverse=True)
        
        return signals
    
    def run(self, top_traders: int = 30, min_agreement: int = 2) -> list[Signal]:
        """Run the full signal generation pipeline"""
        print("=" * 60)
        print("🚀 SIGNAL GENERATOR (with ARS filtering)")
        print("=" * 60)
        
        # 1. Fetch leaderboard
        self.fetch_top_traders(limit=50)
        
        # 2. Score traders by consistency
        self.score_traders(min_pnl=10000)
        
        # 3. Get positions for top traders
        self.fetch_positions(top_n=top_traders)
        
        # 4. Find consensus signals
        raw_signals = self.aggregate_signals(min_traders=min_agreement, min_conviction=0.05)
        print(f"\n   Raw signals found: {len(raw_signals)}")
        
        # 5. Filter resolved markets
        active_signals = self.filter_resolved_markets(raw_signals)
        print(f"   After filtering resolved: {len(active_signals)}")
        
        # 6. Apply ARS scoring
        scored_signals = self.apply_ars_scoring(active_signals)
        
        print("=" * 60)
        print(f"✅ Generated {len(scored_signals)} trading signals")
        print("=" * 60)
        
        return scored_signals


def print_actionable_signals(signals: list[Signal]):
    """Print signals in actionable format"""
    
    # Filter to only good/fair entry quality
    actionable = [s for s in signals if s.entry_quality in ['good', 'fair']]
    
    print("\n" + "=" * 60)
    print("📋 ACTIONABLE SIGNALS (Good Entry Opportunities)")
    print("=" * 60)
    
    if not actionable:
        print("\n⚠️  No good entry opportunities right now.")
        print("   All signals have 'late' entry - traders already up big.")
        print("   Check back later for fresh opportunities.\n")
        
        # Still show top signals for reference
        print("📊 Top signals (for reference - late entry):\n")
        for i, sig in enumerate(signals[:5]):
            print(f"{i+1}. {sig.direction.upper()} on '{sig.market_title[:50]}'")
            print(f"   Entry: {sig.entry_quality.upper()} | ARS Score: {sig.ars_score:.2f}")
            print(f"   Traders: {sig.num_traders} | Price: {sig.current_price:.2f}")
            print(f"   ⚠️  Traders avg entry: {sig.avg_entry_price:.2f} (already +{sig.expected_edge:.0%})")
            print()
        return
    
    print(f"\n🎯 Found {len(actionable)} actionable signals:\n")
    
    for i, sig in enumerate(actionable[:10]):
        edge_str = f"+{sig.expected_edge:.0%}" if sig.expected_edge > 0 else f"{sig.expected_edge:.0%}"
        
        print(f"{i+1}. {sig.direction.upper()} on '{sig.market_title}'")
        print(f"   ┌─ ARS Score: {sig.ars_score:.2f} | Entry Quality: {sig.entry_quality.upper()}")
        print(f"   ├─ Traders: {sig.num_traders} ({sig.conviction:.0%} of top traders)")
        print(f"   ├─ Total Position: ${sig.total_size:,.0f}")
        print(f"   ├─ Avg Entry: {sig.avg_entry_price:.2f} → Current: {sig.current_price:.2f} ({edge_str})")
        print(f"   ├─ Recommended Size: {sig.recommended_size:.1%} of portfolio")
        print(f"   └─ Traders: {', '.join(sig.traders[:4])}")
        print()


if __name__ == "__main__":
    generator = SignalGenerator()
    signals = generator.run(top_traders=25, min_agreement=2)
    
    # Print actionable signals
    print_actionable_signals(signals)