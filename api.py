"""
Predictor Agent API

FastAPI backend that serves real trading signals from Polymarket.
"""

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Optional
from datetime import datetime
import json
import os

# Import signal generator
from signals import SignalGenerator, Signal

# ============================================
# PYDANTIC MODELS
# ============================================

class SignalResponse(BaseModel):
    id: str
    market_slug: str
    market_title: str
    direction: str
    conviction: float
    num_traders: int
    total_size: float
    avg_entry_price: float
    current_price: float
    expected_edge: float
    traders: list[str]
    ars_score: float
    recommended_size: float
    entry_quality: str
    category: str = "Prediction"
    end_date: Optional[str] = None
    volume_24h: float = 0

class TraderResponse(BaseModel):
    rank: int
    username: str
    wallet: str
    pnl: float
    volume: float
    efficiency: float
    score: float
    positions: int
    verified: bool = False

class StatsResponse(BaseModel):
    total_signals: int
    actionable_signals: int
    avg_ars_score: float
    total_position_size: float
    traders_analyzed: int
    last_updated: str

class SignalsDataResponse(BaseModel):
    signals: list[SignalResponse]
    traders: list[TraderResponse]
    stats: StatsResponse


# ============================================
# FASTAPI APP
# ============================================

app = FastAPI(
    title="Predictor Agent API",
    description="Real-time trading signals from Polymarket top traders",
    version="1.0.0"
)

# CORS - allow dashboard to call API
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # In production, set specific origins
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Cache for signals (avoid hitting Polymarket too often)
signal_cache = {
    "signals": [],
    "traders": [],
    "last_updated": None,
    "cache_duration_minutes": 5
}


def categorize_market(title: str) -> str:
    """Categorize market based on title keywords"""
    title_lower = title.lower()
    
    if any(word in title_lower for word in ['bitcoin', 'btc', 'ethereum', 'eth', 'crypto', 'solana', 'token']):
        return "Crypto"
    elif any(word in title_lower for word in ['trump', 'biden', 'election', 'president', 'congress', 'senate', 'democrat', 'republican', 'vote']):
        return "Politics"
    elif any(word in title_lower for word in ['fed', 'rate', 'inflation', 'gdp', 'economy', 'recession', 'jobs']):
        return "Economics"
    elif any(word in title_lower for word in ['ai', 'openai', 'gpt', 'google', 'apple', 'microsoft', 'tech', 'startup']):
        return "Tech"
    elif any(word in title_lower for word in ['stock', 'shares', 'market', 'nasdaq', 'sp500', 's&p']):
        return "Stocks"
    elif any(word in title_lower for word in ['nfl', 'nba', 'mlb', 'soccer', 'game', 'championship', 'super bowl']):
        return "Sports"
    else:
        return "Other"


def signal_to_response(sig: Signal, index: int) -> SignalResponse:
    """Convert Signal dataclass to API response"""
    return SignalResponse(
        id=f"sig_{index}_{sig.market_slug[:20]}",
        market_slug=sig.market_slug,
        market_title=sig.market_title,
        direction=sig.direction,
        conviction=sig.conviction,
        num_traders=sig.num_traders,
        total_size=sig.total_size,
        avg_entry_price=sig.avg_entry_price,
        current_price=sig.current_price,
        expected_edge=sig.expected_edge,
        traders=sig.traders[:10],  # Limit to 10 traders
        ars_score=sig.ars_score,
        recommended_size=sig.recommended_size,
        entry_quality=sig.entry_quality,
        category=categorize_market(sig.market_title),
        volume_24h=sig.total_size * 0.1  # Estimate
    )


def fetch_fresh_signals() -> tuple[list[SignalResponse], list[TraderResponse]]:
    """Fetch fresh signals from Polymarket"""
    print("🔄 Fetching fresh signals from Polymarket...")
    
    generator = SignalGenerator()
    
    # Run the signal generation pipeline
    raw_signals = generator.run(top_traders=25, min_agreement=2)
    
    # Convert to response format
    signals = [signal_to_response(sig, i) for i, sig in enumerate(raw_signals)]
    
    # Get trader data
    traders = []
    for i, trader in enumerate(generator.trader_scores[:20]):
        position_count = len(generator.positions.get(trader.wallet, []))
        traders.append(TraderResponse(
            rank=i + 1,
            username=trader.username,
            wallet=f"{trader.wallet[:6]}...{trader.wallet[-4:]}",
            pnl=trader.pnl,
            volume=trader.volume,
            efficiency=trader.consistency,
            score=trader.final_score,
            positions=position_count,
            verified=trader.pnl > 100000  # "Verified" if PnL > 100k
        ))
    
    return signals, traders


def get_cached_or_fresh():
    """Get cached signals or fetch fresh if cache expired"""
    now = datetime.now()
    
    # Check if cache is valid
    if signal_cache["last_updated"]:
        age_minutes = (now - signal_cache["last_updated"]).total_seconds() / 60
        if age_minutes < signal_cache["cache_duration_minutes"]:
            print(f"📦 Using cached signals (age: {age_minutes:.1f} min)")
            return signal_cache["signals"], signal_cache["traders"]
    
    # Fetch fresh
    try:
        signals, traders = fetch_fresh_signals()
        signal_cache["signals"] = signals
        signal_cache["traders"] = traders
        signal_cache["last_updated"] = now
        return signals, traders
    except Exception as e:
        print(f"❌ Error fetching signals: {e}")
        # Return cached data if available, even if stale
        if signal_cache["signals"]:
            print("⚠️ Returning stale cache")
            return signal_cache["signals"], signal_cache["traders"]
        raise


# ============================================
# ROUTES
# ============================================

@app.get("/")
def root():
    return {
        "name": "Predictor Agent API",
        "version": "1.0.0",
        "status": "running",
        "endpoints": {
            "signals": "/api/signals",
            "stats": "/api/stats",
            "health": "/health"
        }
    }


@app.get("/health")
def health():
    return {
        "status": "healthy",
        "timestamp": datetime.now().isoformat(),
        "cache_age_minutes": (
            (datetime.now() - signal_cache["last_updated"]).total_seconds() / 60
            if signal_cache["last_updated"] else None
        )
    }


@app.get("/api/signals", response_model=SignalsDataResponse)
def get_signals(refresh: bool = False):
    """
    Get trading signals from top Polymarket traders.
    
    - **refresh**: Force refresh from Polymarket (ignores cache)
    """
    if refresh:
        signal_cache["last_updated"] = None
    
    signals, traders = get_cached_or_fresh()
    
    # Calculate stats
    actionable = [s for s in signals if s.entry_quality in ['good', 'fair']]
    avg_ars = sum(s.ars_score for s in signals) / len(signals) if signals else 0
    total_size = sum(s.total_size for s in signals)
    
    stats = StatsResponse(
        total_signals=len(signals),
        actionable_signals=len(actionable),
        avg_ars_score=avg_ars,
        total_position_size=total_size,
        traders_analyzed=len(traders),
        last_updated=signal_cache["last_updated"].isoformat() if signal_cache["last_updated"] else None
    )
    
    return SignalsDataResponse(
        signals=signals,
        traders=traders,
        stats=stats
    )


@app.get("/api/signals/{signal_id}")
def get_signal(signal_id: str):
    """Get a specific signal by ID"""
    signals, _ = get_cached_or_fresh()
    
    for sig in signals:
        if sig.id == signal_id:
            return sig
    
    raise HTTPException(status_code=404, detail="Signal not found")


@app.get("/api/traders", response_model=list[TraderResponse])
def get_traders():
    """Get top traders being tracked"""
    _, traders = get_cached_or_fresh()
    return traders


@app.get("/api/stats", response_model=StatsResponse)
def get_stats():
    """Get current statistics"""
    signals, traders = get_cached_or_fresh()
    
    actionable = [s for s in signals if s.entry_quality in ['good', 'fair']]
    avg_ars = sum(s.ars_score for s in signals) / len(signals) if signals else 0
    total_size = sum(s.total_size for s in signals)
    
    return StatsResponse(
        total_signals=len(signals),
        actionable_signals=len(actionable),
        avg_ars_score=avg_ars,
        total_position_size=total_size,
        traders_analyzed=len(traders),
        last_updated=signal_cache["last_updated"].isoformat() if signal_cache["last_updated"] else None
    )


@app.post("/api/refresh")
def refresh_signals():
    """Force refresh signals from Polymarket"""
    signal_cache["last_updated"] = None
    signals, traders = get_cached_or_fresh()
    
    return {
        "status": "refreshed",
        "signals_count": len(signals),
        "traders_count": len(traders),
        "timestamp": datetime.now().isoformat()
    }


# ============================================
# RUN
# ============================================

if __name__ == "__main__":
    import uvicorn
    port = int(os.environ.get("PORT", 8000))
    uvicorn.run(app, host="0.0.0.0", port=port)
