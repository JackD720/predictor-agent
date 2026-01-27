"""
Adaptive Risk Stabilizer (ARS)

The core algorithm that filters noise, prevents overfitting,
and stabilizes trading signals for consistent performance.

Key Features:
1. Noise Filtering - Removes outliers and anomalous signals
2. Consistency Scoring - Weights traders by long-term consistency, not recent luck
3. Market Regime Detection - Adjusts risk based on market conditions
4. Position Sizing - Dynamic sizing based on conviction and volatility
5. Drawdown Protection - Reduces exposure during losing streaks
"""

import numpy as np
from dataclasses import dataclass
from typing import Optional
from datetime import datetime, timedelta
from enum import Enum


class MarketRegime(Enum):
    """Market regime classification"""
    CALM = "calm"           # Low volatility, normal conditions
    VOLATILE = "volatile"   # High volatility, uncertain
    TRENDING = "trending"   # Strong directional movement
    CHOPPY = "choppy"       # Frequent reversals, no clear direction


@dataclass
class TraderProfile:
    """Profile of a trader for consistency scoring"""
    wallet: str
    total_trades: int
    win_rate: float
    pnl: float
    avg_trade_size: float
    max_drawdown: float
    consistency_score: float  # 0-1, how consistent are returns
    days_active: int
    markets_diversification: float  # 0-1, how diversified


@dataclass
class Signal:
    """A trading signal with ARS-adjusted parameters"""
    market_id: str
    market_title: str
    direction: str  # "yes" or "no"
    raw_conviction: float  # Original conviction from aggregation
    ars_conviction: float  # ARS-adjusted conviction
    recommended_size: float  # As fraction of portfolio
    source_traders: list[str]
    avg_trader_consistency: float
    regime_adjustment: float
    expires_at: datetime
    metadata: dict


@dataclass
class ARSConfig:
    """Configuration for the Adaptive Risk Stabilizer"""
    # Noise filtering
    outlier_std_threshold: float = 2.0  # Z-score threshold for outliers
    min_sample_size: int = 5  # Minimum data points for statistical validity
    
    # Consistency scoring
    consistency_lookback_days: int = 90
    min_trades_for_consistency: int = 20
    consistency_decay_rate: float = 0.95  # Recent trades weighted more
    
    # Position sizing
    base_position_size: float = 0.05  # 5% of portfolio base
    max_position_size: float = 0.15  # 15% max
    min_position_size: float = 0.01  # 1% min
    conviction_scaling: float = 2.0  # How much conviction affects size
    
    # Risk management
    max_daily_drawdown: float = 0.10  # 10% max daily loss
    max_total_drawdown: float = 0.25  # 25% max total loss
    drawdown_reduction_rate: float = 0.5  # Reduce size by 50% when in drawdown
    
    # Market regime
    volatility_lookback_periods: int = 20
    high_volatility_threshold: float = 0.3
    regime_position_adjustments: dict = None
    
    def __post_init__(self):
        if self.regime_position_adjustments is None:
            self.regime_position_adjustments = {
                MarketRegime.CALM: 1.0,
                MarketRegime.VOLATILE: 0.5,
                MarketRegime.TRENDING: 1.2,
                MarketRegime.CHOPPY: 0.3
            }


class AdaptiveRiskStabilizer:
    """
    The Adaptive Risk Stabilizer filters trading signals and adjusts
    position sizing based on market conditions and trader consistency.
    """
    
    def __init__(self, config: Optional[ARSConfig] = None):
        self.config = config or ARSConfig()
        self.price_history: dict[str, list[float]] = {}
        self.trader_profiles: dict[str, TraderProfile] = {}
        self.current_drawdown: float = 0.0
        self.daily_pnl: float = 0.0
        self.last_reset: datetime = datetime.now()
    
    def calculate_consistency_score(
        self,
        trade_results: list[float],  # List of PnL from each trade
        timestamps: list[datetime]
    ) -> float:
        """
        Calculate how consistent a trader's returns are.
        
        High consistency = steady small wins
        Low consistency = volatile, big wins/losses
        
        Returns:
            Score from 0 (very inconsistent) to 1 (very consistent)
        """
        if len(trade_results) < self.config.min_trades_for_consistency:
            return 0.5  # Default for insufficient data
        
        results = np.array(trade_results)
        
        # 1. Win rate stability (rolling window)
        window_size = min(10, len(results) // 3)
        if window_size < 3:
            return 0.5
        
        rolling_win_rates = []
        for i in range(len(results) - window_size + 1):
            window = results[i:i + window_size]
            win_rate = np.sum(window > 0) / len(window)
            rolling_win_rates.append(win_rate)
        
        win_rate_stability = 1 - np.std(rolling_win_rates)
        
        # 2. Return stability (coefficient of variation)
        positive_returns = results[results > 0]
        if len(positive_returns) > 3:
            return_cv = np.std(positive_returns) / (np.mean(positive_returns) + 1e-6)
            return_stability = max(0, 1 - return_cv)
        else:
            return_stability = 0.5
        
        # 3. Drawdown recovery speed
        cumulative = np.cumsum(results)
        running_max = np.maximum.accumulate(cumulative)
        drawdowns = running_max - cumulative
        
        if np.max(drawdowns) > 0:
            # How quickly do they recover from drawdowns?
            recovery_score = 1 - (np.mean(drawdowns) / (np.max(drawdowns) + 1e-6))
        else:
            recovery_score = 1.0
        
        # 4. Time-weighted recency (more recent = slightly more weight)
        if timestamps:
            now = datetime.now()
            days_ago = [(now - t).days for t in timestamps]
            recency_weights = [self.config.consistency_decay_rate ** d for d in days_ago]
            weighted_results = results * np.array(recency_weights[:len(results)])
            recency_factor = np.sum(weighted_results > 0) / (np.sum(recency_weights[:len(results)]) + 1e-6)
        else:
            recency_factor = 0.5
        
        # Combine factors
        consistency = (
            0.3 * win_rate_stability +
            0.3 * return_stability +
            0.2 * recovery_score +
            0.2 * recency_factor
        )
        
        return np.clip(consistency, 0, 1)
    
    def detect_market_regime(
        self,
        prices: list[float],
        volumes: list[float] = None
    ) -> MarketRegime:
        """
        Detect current market regime based on price action.
        
        Args:
            prices: Recent price history
            volumes: Recent volume history (optional)
        
        Returns:
            Detected MarketRegime
        """
        if len(prices) < self.config.volatility_lookback_periods:
            return MarketRegime.CALM
        
        prices = np.array(prices[-self.config.volatility_lookback_periods:])
        returns = np.diff(prices) / prices[:-1]
        
        # Calculate volatility
        volatility = np.std(returns)
        
        # Calculate trend strength
        trend = (prices[-1] - prices[0]) / prices[0]
        trend_strength = abs(trend)
        
        # Calculate choppiness (reversals)
        direction_changes = np.sum(np.diff(np.sign(returns)) != 0)
        choppiness = direction_changes / len(returns)
        
        # Classify regime
        if volatility > self.config.high_volatility_threshold:
            return MarketRegime.VOLATILE
        elif trend_strength > 0.1 and choppiness < 0.3:
            return MarketRegime.TRENDING
        elif choppiness > 0.6:
            return MarketRegime.CHOPPY
        else:
            return MarketRegime.CALM
    
    def filter_outliers(
        self,
        values: list[float],
        labels: list[str] = None
    ) -> tuple[list[float], list[str]]:
        """
        Remove statistical outliers from a dataset.
        
        Args:
            values: Data values
            labels: Corresponding labels (e.g., trader IDs)
        
        Returns:
            Filtered values and labels
        """
        if len(values) < self.config.min_sample_size:
            return values, labels or []
        
        arr = np.array(values)
        mean = np.mean(arr)
        std = np.std(arr)
        
        if std == 0:
            return values, labels or []
        
        z_scores = np.abs((arr - mean) / std)
        mask = z_scores < self.config.outlier_std_threshold
        
        filtered_values = arr[mask].tolist()
        filtered_labels = [labels[i] for i, m in enumerate(mask) if m] if labels else []
        
        return filtered_values, filtered_labels
    
    def calculate_position_size(
        self,
        conviction: float,
        regime: MarketRegime,
        current_exposure: float = 0.0
    ) -> float:
        """
        Calculate recommended position size based on conviction and conditions.
        
        Args:
            conviction: Signal conviction (0-1)
            regime: Current market regime
            current_exposure: Current portfolio exposure (0-1)
        
        Returns:
            Recommended position size as fraction of portfolio
        """
        # Base size scaled by conviction
        base = self.config.base_position_size
        conviction_adjusted = base * (1 + (conviction - 0.5) * self.config.conviction_scaling)
        
        # Regime adjustment
        regime_factor = self.config.regime_position_adjustments.get(regime, 1.0)
        regime_adjusted = conviction_adjusted * regime_factor
        
        # Drawdown adjustment
        if self.current_drawdown > self.config.max_daily_drawdown / 2:
            drawdown_factor = 1 - (self.current_drawdown / self.config.max_total_drawdown)
            drawdown_factor = max(drawdown_factor, self.config.drawdown_reduction_rate)
        else:
            drawdown_factor = 1.0
        
        # Exposure limit
        remaining_capacity = 1.0 - current_exposure
        
        # Final size
        final_size = regime_adjusted * drawdown_factor
        final_size = min(final_size, remaining_capacity, self.config.max_position_size)
        final_size = max(final_size, self.config.min_position_size)
        
        return final_size
    
    def process_signal(
        self,
        market_id: str,
        market_title: str,
        direction: str,
        supporting_traders: list[dict],  # Each has wallet, position_size, pnl, win_rate
        market_prices: list[float] = None,
        current_exposure: float = 0.0
    ) -> Signal:
        """
        Process a raw trading signal through ARS filters.
        
        Args:
            market_id: Market identifier
            market_title: Human-readable title
            direction: "yes" or "no"
            supporting_traders: List of traders supporting this signal
            market_prices: Recent price history for regime detection
            current_exposure: Current portfolio exposure
        
        Returns:
            ARS-processed Signal
        """
        # 1. Calculate raw conviction from trader agreement
        num_traders = len(supporting_traders)
        raw_conviction = min(num_traders / 10, 1.0)  # 10 traders = 100%
        
        # 2. Filter outlier traders (by position size)
        position_sizes = [t.get("position_size", 0) for t in supporting_traders]
        wallets = [t.get("wallet", "") for t in supporting_traders]
        filtered_sizes, filtered_wallets = self.filter_outliers(position_sizes, wallets)
        
        # 3. Calculate consistency-weighted conviction
        consistency_scores = []
        for trader in supporting_traders:
            if trader.get("wallet") in filtered_wallets:
                # Use stored profile or estimate from available data
                win_rate = trader.get("win_rate", 0.5)
                pnl = trader.get("pnl", 0)
                
                # Simple consistency estimate from win rate and PnL sign agreement
                consistency = win_rate * 0.6 + (0.4 if pnl > 0 else 0.0)
                consistency_scores.append(consistency)
        
        avg_consistency = np.mean(consistency_scores) if consistency_scores else 0.5
        
        # 4. Detect market regime
        regime = MarketRegime.CALM
        if market_prices and len(market_prices) >= 10:
            regime = self.detect_market_regime(market_prices)
        
        # 5. Calculate ARS-adjusted conviction
        ars_conviction = raw_conviction * avg_consistency
        regime_factor = self.config.regime_position_adjustments.get(regime, 1.0)
        ars_conviction = ars_conviction * (0.5 + 0.5 * regime_factor)  # Dampen regime impact
        ars_conviction = np.clip(ars_conviction, 0, 1)
        
        # 6. Calculate recommended position size
        recommended_size = self.calculate_position_size(
            ars_conviction, 
            regime, 
            current_exposure
        )
        
        # 7. Create signal
        return Signal(
            market_id=market_id,
            market_title=market_title,
            direction=direction,
            raw_conviction=raw_conviction,
            ars_conviction=ars_conviction,
            recommended_size=recommended_size,
            source_traders=filtered_wallets,
            avg_trader_consistency=avg_consistency,
            regime_adjustment=regime_factor,
            expires_at=datetime.now() + timedelta(hours=24),
            metadata={
                "regime": regime.value,
                "num_traders_original": num_traders,
                "num_traders_filtered": len(filtered_wallets),
                "outliers_removed": num_traders - len(filtered_wallets)
            }
        )
    
    def update_drawdown(self, pnl: float):
        """Update drawdown tracking with new PnL."""
        self.daily_pnl += pnl
        
        # Reset daily at midnight
        if datetime.now().date() > self.last_reset.date():
            self.daily_pnl = pnl
            self.last_reset = datetime.now()
        
        # Update drawdown
        if self.daily_pnl < 0:
            self.current_drawdown = abs(self.daily_pnl)
        else:
            self.current_drawdown = max(0, self.current_drawdown - pnl)
    
    def should_stop_trading(self) -> tuple[bool, str]:
        """
        Check if trading should stop due to risk limits.
        
        Returns:
            Tuple of (should_stop, reason)
        """
        if self.current_drawdown >= self.config.max_daily_drawdown:
            return True, f"Daily drawdown limit reached ({self.current_drawdown:.1%})"
        
        if self.current_drawdown >= self.config.max_total_drawdown:
            return True, f"Total drawdown limit reached ({self.current_drawdown:.1%})"
        
        return False, ""


# Factory function for easy instantiation
def create_ars(
    conservative: bool = False,
    aggressive: bool = False
) -> AdaptiveRiskStabilizer:
    """
    Create an ARS instance with preset configurations.
    
    Args:
        conservative: Use conservative risk settings
        aggressive: Use aggressive risk settings
    
    Returns:
        Configured AdaptiveRiskStabilizer
    """
    if conservative:
        config = ARSConfig(
            base_position_size=0.03,
            max_position_size=0.10,
            max_daily_drawdown=0.05,
            max_total_drawdown=0.15,
            conviction_scaling=1.5
        )
    elif aggressive:
        config = ARSConfig(
            base_position_size=0.08,
            max_position_size=0.20,
            max_daily_drawdown=0.15,
            max_total_drawdown=0.35,
            conviction_scaling=2.5
        )
    else:
        config = ARSConfig()
    
    return AdaptiveRiskStabilizer(config)


if __name__ == "__main__":
    # Demo the ARS
    from rich import print as rprint
    
    print("\n" + "=" * 60)
    print("🔒 Adaptive Risk Stabilizer Demo")
    print("=" * 60 + "\n")
    
    ars = create_ars()
    
    # Simulate some trader data
    traders = [
        {"wallet": "0x1...", "position_size": 1000, "pnl": 5000, "win_rate": 0.62},
        {"wallet": "0x2...", "position_size": 800, "pnl": 3000, "win_rate": 0.58},
        {"wallet": "0x3...", "position_size": 1200, "pnl": 8000, "win_rate": 0.65},
        {"wallet": "0x4...", "position_size": 500, "pnl": 1500, "win_rate": 0.55},
        {"wallet": "0x5...", "position_size": 50000, "pnl": 100, "win_rate": 0.51},  # Outlier
    ]
    
    # Simulate price history
    prices = [0.45, 0.47, 0.46, 0.48, 0.50, 0.49, 0.52, 0.55, 0.54, 0.56]
    
    signal = ars.process_signal(
        market_id="test-market",
        market_title="Will it rain tomorrow?",
        direction="yes",
        supporting_traders=traders,
        market_prices=prices,
        current_exposure=0.2
    )
    
    rprint("\n📊 Processed Signal:")
    rprint(f"  Market: {signal.market_title}")
    rprint(f"  Direction: {signal.direction.upper()}")
    rprint(f"  Raw Conviction: {signal.raw_conviction:.1%}")
    rprint(f"  ARS Conviction: {signal.ars_conviction:.1%}")
    rprint(f"  Recommended Size: {signal.recommended_size:.1%} of portfolio")
    rprint(f"  Traders: {len(signal.source_traders)} (filtered from {signal.metadata['num_traders_original']})")
    rprint(f"  Avg Consistency: {signal.avg_trader_consistency:.1%}")
    rprint(f"  Market Regime: {signal.metadata['regime']}")
    rprint(f"  Outliers Removed: {signal.metadata['outliers_removed']}")
