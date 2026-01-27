<p align="center">
  <img src="https://img.shields.io/badge/python-3.11+-blue.svg" alt="Python 3.11+">
  <img src="https://img.shields.io/badge/status-alpha-orange" alt="Status: Alpha">
  <img src="https://img.shields.io/badge/license-MIT-green.svg" alt="License: MIT">
</p>

<h1 align="center">📈 Predictor Agent</h1>

<p align="center">
  <strong>AI-powered trading signals from prediction market whales</strong><br>
  Copy-trade the smartest traders on Polymarket with built-in risk controls.
</p>

<p align="center">
  <a href="#how-it-works">How It Works</a> •
  <a href="#quick-start">Quick Start</a> •
  <a href="#ars-technology">ARS Technology</a> •
  <a href="#signals">Signals</a> •
  <a href="#configuration">Config</a>
</p>

---

## The Idea

The best prediction market traders consistently outperform. What if you could:

1. **Identify** the top traders by consistency (not just raw PnL)
2. **Track** their current positions in real-time
3. **Find consensus** — markets where multiple top traders agree
4. **Filter** signals through risk controls to avoid bad entries
5. **Size** positions dynamically based on conviction

That's what Predictor Agent does.

---

## How It Works

```
┌─────────────────┐     ┌─────────────────┐     ┌─────────────────┐
│   Polymarket    │────▶│  Signal Engine  │────▶│   ARS Filter    │
│   Leaderboard   │     │                 │     │                 │
└─────────────────┘     └─────────────────┘     └─────────────────┘
                                                        │
                              ┌──────────────────────────┘
                              ▼
                    ┌─────────────────┐
                    │ Actionable      │
                    │ Trading Signals │
                    └─────────────────┘
```

**Pipeline:**

1. **Fetch Leaderboard** — Get top 50 traders from Polymarket
2. **Score Traders** — Rank by consistency, not just total PnL
3. **Get Positions** — Fetch current holdings for top 25 traders
4. **Find Consensus** — Markets where 2+ top traders agree
5. **Apply ARS** — Filter noise, detect regime, size positions
6. **Output Signals** — Actionable trades with entry quality ratings

---

## Quick Start

### Installation

```bash
# Clone the repo
git clone https://github.com/JackD720/predictor-agent.git
cd predictor-agent

# Install dependencies
pip install -r requirements.txt

# Run the signal generator
python signals.py
```

### Requirements

```
requests>=2.28.0
numpy>=1.24.0
rich>=13.0.0  # For pretty output
```

### Example Output

```
============================================================
🚀 SIGNAL GENERATOR (with ARS filtering)
============================================================

📊 Fetching top 50 traders...
   Found 50 traders

🎯 Scoring traders (min PnL: $10,000)...
   Qualified traders: 28
   1. BITCOINTO500K: $892,450 PnL, 12.3% efficiency, 0.87 score
   2. Fredi9999: $654,200 PnL, 9.8% efficiency, 0.82 score
   ...

📈 Fetching positions for top 25 traders...

🔍 Aggregating signals (min 2 traders, 5% conviction)...
   Raw signals found: 47
   After filtering resolved: 31

🔒 Applying ARS filtering to 31 signals...

============================================================
📋 ACTIONABLE SIGNALS (Good Entry Opportunities)
============================================================

1. YES on 'Will JD Vance win the 2028 US Presidential Election?'
   ┌─ ARS Score: 0.37 | Entry Quality: GOOD
   ├─ Traders: 2 (8% of top traders)
   ├─ Total Position: $266,270
   ├─ Avg Entry: 0.50 → Current: 0.27 (-47%)
   ├─ Recommended Size: 1.2% of portfolio
   └─ Traders: BITCOINTO500K, 0xa0f21e6d351baa...

2. YES on 'Will Trump nominate Kevin Hassett as the next Fed chair?'
   ┌─ ARS Score: 0.37 | Entry Quality: GOOD
   ├─ Traders: 2 (8% of top traders)
   ├─ Total Position: $4,351
   ├─ Avg Entry: 0.40 → Current: 0.06 (-84%)
   ├─ Recommended Size: 1.2% of portfolio
   └─ Traders: botbot, Brunoruno
```

---

## ARS Technology

The **Adaptive Risk Stabilizer (ARS)** is the core innovation — a risk management layer that prevents common copy-trading mistakes.

### The Problem with Naive Copy-Trading

| Issue | What Happens |
|-------|--------------|
| **Chasing** | Enter after traders already 3x'd |
| **Outliers** | One whale skews the signal |
| **Volatility** | Same size in calm vs choppy markets |
| **Drawdowns** | Keep betting during losing streaks |

### How ARS Solves This

```python
from stabilizer import create_ars, ARSConfig

# Create ARS with custom config
ars = create_ars(conservative=True)

# Process a raw signal
signal = ars.process_signal(
    market_id="will-x-happen",
    market_title="Will X happen?",
    direction="yes",
    supporting_traders=[
        {"wallet": "0x1...", "position_size": 1000, "pnl": 5000, "win_rate": 0.62},
        {"wallet": "0x2...", "position_size": 800, "pnl": 3000, "win_rate": 0.58},
    ],
    market_prices=[0.45, 0.47, 0.50, 0.52, 0.55],  # For regime detection
    current_exposure=0.2
)

print(f"Raw Conviction: {signal.raw_conviction:.1%}")
print(f"ARS Conviction: {signal.ars_conviction:.1%}")  # Adjusted
print(f"Recommended Size: {signal.recommended_size:.1%}")
print(f"Market Regime: {signal.metadata['regime']}")
```

### ARS Features

#### 1. Noise Filtering
Removes statistical outliers (traders with abnormally large positions that skew consensus).

```python
# Z-score based outlier detection
outlier_threshold = 2.0  # Remove positions > 2 std devs
```

#### 2. Consistency Scoring
Weights traders by long-term consistency, not recent luck.

```python
# Factors:
# - Win rate stability (rolling window)
# - Return stability (coefficient of variation)
# - Drawdown recovery speed
# - Recency weighting
```

#### 3. Market Regime Detection
Adjusts risk based on current market conditions.

| Regime | Description | Position Adjustment |
|--------|-------------|---------------------|
| `CALM` | Low volatility, normal | 100% |
| `VOLATILE` | High volatility | 50% |
| `TRENDING` | Strong direction | 120% |
| `CHOPPY` | Frequent reversals | 30% |

#### 4. Entry Quality Assessment
Evaluates if it's still a good time to enter.

| Quality | Price Move Since Entry | Action |
|---------|------------------------|--------|
| `GOOD` | < 15% | ✅ Enter |
| `FAIR` | 15-50% | ⚠️ Smaller size |
| `LATE` | 50-100% | ⚠️ Caution |
| `VERY_LATE` | > 100% | ❌ Skip |

#### 5. Dynamic Position Sizing
Calculates optimal size based on:

```python
size = base_size * conviction_factor * regime_factor * drawdown_factor
size = clamp(size, min_size, max_size)
size = min(size, remaining_capacity)
```

#### 6. Drawdown Protection
Automatically reduces exposure during losing streaks.

```python
max_daily_drawdown = 0.10   # 10% max daily loss
max_total_drawdown = 0.25   # 25% max total loss
reduction_rate = 0.5        # Cut size by 50% when in drawdown
```

---

## Signals

### Signal Object

```python
@dataclass
class Signal:
    market_slug: str
    market_title: str
    direction: str           # "Yes" or "No"
    conviction: float        # 0-1 based on trader agreement
    num_traders: int         # How many top traders hold this
    total_size: float        # Combined position size in dollars
    avg_entry_price: float
    current_price: float
    expected_edge: float     # Current price vs avg entry
    traders: list[str]       # Usernames of traders holding this
    
    # ARS fields
    ars_score: float         # 0-1, higher = better opportunity
    recommended_size: float  # Recommended position size as % of portfolio
    entry_quality: str       # "good", "fair", "late", "very_late"
```

### Filtering Signals

```python
from signals import SignalGenerator, print_actionable_signals

generator = SignalGenerator()
signals = generator.run(
    top_traders=25,      # Analyze top 25 traders
    min_agreement=2      # Require 2+ traders to agree
)

# Only show good entry opportunities
print_actionable_signals(signals)
```

---

## Configuration

### ARS Config

```python
from stabilizer import ARSConfig, AdaptiveRiskStabilizer

config = ARSConfig(
    # Noise filtering
    outlier_std_threshold=2.0,
    min_sample_size=5,
    
    # Consistency scoring
    consistency_lookback_days=90,
    min_trades_for_consistency=20,
    consistency_decay_rate=0.95,
    
    # Position sizing
    base_position_size=0.05,    # 5% base
    max_position_size=0.15,     # 15% max
    min_position_size=0.01,     # 1% min
    conviction_scaling=2.0,
    
    # Risk management
    max_daily_drawdown=0.10,    # 10% daily max loss
    max_total_drawdown=0.25,    # 25% total max loss
    drawdown_reduction_rate=0.5,
    
    # Market regime
    volatility_lookback_periods=20,
    high_volatility_threshold=0.3
)

ars = AdaptiveRiskStabilizer(config)
```

### Presets

```python
from stabilizer import create_ars

# Conservative (smaller positions, tighter stops)
ars = create_ars(conservative=True)

# Aggressive (larger positions, wider stops)
ars = create_ars(aggressive=True)

# Default (balanced)
ars = create_ars()
```

---

## Project Structure

```
predictor-agent/
├── signals.py          # Main signal generator
├── stabilizer.py       # ARS implementation
├── polymarket.py       # Polymarket API client
├── kalshi.py           # Kalshi API client (WIP)
├── collector.py        # Data collection utilities
├── index.html          # Web dashboard (WIP)
└── requirements.txt
```

---

## Roadmap

- [x] Polymarket leaderboard scraping
- [x] Trader consistency scoring
- [x] Position aggregation & consensus
- [x] ARS risk filtering
- [x] Entry quality assessment
- [x] Dynamic position sizing
- [ ] Kalshi integration
- [ ] Web dashboard with live signals
- [ ] Telegram/Discord alerts
- [ ] Backtesting framework
- [ ] Auto-execution with AgentWallet
- [ ] Multi-platform consensus (Poly + Kalshi + Metaculus)

---

## Disclaimer

⚠️ **This is experimental software for research purposes.**

- Not financial advice
- Prediction markets involve risk of loss
- Past performance doesn't guarantee future results
- Do your own research before trading

---

## License

MIT License

---

<p align="center">
  <strong>Trade smarter, not harder.</strong><br>
  <sub>Built by <a href="https://twitter.com/jackdavis720">@jackdavis720</a></sub>
</p>