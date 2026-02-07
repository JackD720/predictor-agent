"""
Live Trader — AgentWallet Governance → Kalshi Execution

This is the real money pipeline:
  1. Fetch signals from Polymarket leaderboard (SignalGenerator)
  2. Match Polymarket signals to Kalshi markets
  3. Run each signal through GovernanceEngine
  4. Execute approved trades on Kalshi via authenticated API
  5. Log everything to audit trail

Requirements:
  pip install requests cryptography

Environment variables:
  KALSHI_API_KEY_ID     — Your Kalshi API key ID
  KALSHI_PRIVATE_KEY    — Your RSA private key (PEM string) OR
  KALSHI_PRIVATE_KEY_PATH — Path to private key file (default: ~/.kalshi/private_key.pem)

Usage:
  python live_trader.py                  # Run once
  python live_trader.py --loop 30        # Run every 30 minutes
  python live_trader.py --dry-run        # Signals + governance only, no real trades
"""

import os
import sys
import json
import time
import uuid
import argparse
import requests
import datetime
import base64
from typing import Optional, Dict, Any, List
from dataclasses import dataclass, asdict

# ─── Kalshi Authenticated Client (RSA-PSS) ─────────────────────

try:
    from cryptography.hazmat.primitives import serialization, hashes
    from cryptography.hazmat.backends import default_backend
    from cryptography.hazmat.primitives.asymmetric import padding
except ImportError:
    print("❌ Missing dependency: pip install cryptography")
    sys.exit(1)


class KalshiAuthClient:
    """Authenticated Kalshi client for real order placement."""

    BASE_URL = "https://trading-api.kalshi.com"

    def __init__(self, api_key_id: str, private_key_path: str = None, private_key_pem: str = None):
        self.api_key_id = api_key_id

        if private_key_pem:
            key_data = private_key_pem.encode() if isinstance(private_key_pem, str) else private_key_pem
        elif private_key_path:
            with open(os.path.expanduser(private_key_path), "rb") as f:
                key_data = f.read()
        else:
            raise ValueError("Provide private_key_path or private_key_pem")

        self.private_key = serialization.load_pem_private_key(key_data, password=None, backend=default_backend())

    def _sign(self, timestamp: str, method: str, path: str) -> str:
        path_clean = path.split("?")[0]
        message = f"{timestamp}{method}{path_clean}".encode("utf-8")
        signature = self.private_key.sign(
            message,
            padding.PSS(mgf=padding.MGF1(hashes.SHA256()), salt_length=padding.PSS.DIGEST_LENGTH),
            hashes.SHA256(),
        )
        return base64.b64encode(signature).decode("utf-8")

    def _headers(self, method: str, path: str) -> Dict[str, str]:
        ts = str(int(datetime.datetime.now().timestamp() * 1000))
        return {
            "KALSHI-ACCESS-KEY": self.api_key_id,
            "KALSHI-ACCESS-SIGNATURE": self._sign(ts, method, path),
            "KALSHI-ACCESS-TIMESTAMP": ts,
            "Content-Type": "application/json",
        }

    def _request(self, method: str, path: str, params=None, json_body=None) -> Dict:
        url = self.BASE_URL + path
        resp = requests.request(method, url, headers=self._headers(method, path), params=params, json=json_body)
        resp.raise_for_status()
        return resp.json()

    # ── Portfolio ──
    def get_balance(self) -> Dict:
        return self._request("GET", "/trade-api/v2/portfolio/balance")

    def get_positions(self, limit=100) -> Dict:
        return self._request("GET", "/trade-api/v2/portfolio/positions", params={"limit": limit})

    # ── Markets ──
    def search_markets(self, status="open", limit=200, cursor=None, series_ticker=None, event_ticker=None) -> Dict:
        """Fetch markets with filtering."""
        params = {"status": status, "limit": min(limit, 1000)}
        if cursor:
            params["cursor"] = cursor
        if series_ticker:
            params["series_ticker"] = series_ticker
        if event_ticker:
            params["event_ticker"] = event_ticker
        return self._request("GET", "/trade-api/v2/markets", params=params)

    def get_all_open_markets(self, max_markets=2000) -> List[Dict]:
        """Paginate through all open markets."""
        all_markets = []
        cursor = None
        while len(all_markets) < max_markets:
            data = self.search_markets(status="open", limit=1000, cursor=cursor)
            markets = data.get("markets", [])
            all_markets.extend(markets)
            cursor = data.get("cursor")
            if not cursor or not markets:
                break
        return all_markets

    def get_market(self, ticker: str) -> Dict:
        data = self._request("GET", f"/trade-api/v2/markets/{ticker}")
        return data.get("market", {})

    def get_events(self, status="open", limit=200, series_ticker=None) -> List[Dict]:
        """Fetch events (groups of markets)."""
        params = {"status": status, "limit": limit}
        if series_ticker:
            params["series_ticker"] = series_ticker
        data = self._request("GET", "/trade-api/v2/events", params=params)
        return data.get("events", [])

    def get_orderbook(self, ticker: str, depth: int = 5) -> Dict:
        """Get orderbook — useful when market-level prices are 0."""
        return self._request("GET", f"/trade-api/v2/markets/{ticker}/orderbook", params={"depth": depth})

    def get_event_markets(self, event_ticker: str) -> List[Dict]:
        """Get all markets for an event (e.g., all bets in a game)."""
        data = self.search_markets(status="open", limit=100, event_ticker=event_ticker)
        return data.get("markets", [])

    # ── Orders ──
    def create_order(
        self,
        ticker: str,
        side: str,      # "yes" or "no"
        action: str,     # "buy" or "sell"
        count: int,
        order_type: str = "limit",
        yes_price: int = None,
        no_price: int = None,
    ) -> Dict:
        """Place a real order on Kalshi. This spends real money."""
        order = {
            "ticker": ticker,
            "side": side,
            "action": action,
            "count": count,
            "type": order_type,
        }
        if yes_price is not None:
            order["yes_price"] = yes_price
        if no_price is not None:
            order["no_price"] = no_price

        return self._request("POST", "/trade-api/v2/portfolio/orders", json_body=order)

    def cancel_all_orders(self) -> Dict:
        return self._request("DELETE", "/trade-api/v2/portfolio/orders")


# ─── Import local modules ──────────────────────────────────────

from governance_bridge import GovernanceEngine, PredictorSignal, GovernanceDecision
from signals import SignalGenerator


# ─── Market Matcher ─────────────────────────────────────────────

# NBA team name aliases: Polymarket might say "Grizzlies" but Kalshi says "Memphis"
TEAM_ALIASES = {
    # NBA
    "hawks": ["atlanta", "hawks", "atl"], "celtics": ["boston", "celtics", "bos"],
    "nets": ["brooklyn", "nets", "bkn"], "hornets": ["charlotte", "hornets", "cha"],
    "bulls": ["chicago", "bulls", "chi"], "cavaliers": ["cleveland", "cavaliers", "cavs", "cle"],
    "mavericks": ["dallas", "mavericks", "mavs", "dal"], "nuggets": ["denver", "nuggets", "den"],
    "pistons": ["detroit", "pistons", "det"], "warriors": ["golden state", "warriors", "gsw"],
    "rockets": ["houston", "rockets", "hou"], "pacers": ["indiana", "pacers", "ind"],
    "clippers": ["los angeles c", "clippers", "lac", "la clippers"],
    "lakers": ["los angeles l", "lakers", "lal", "la lakers"],
    "grizzlies": ["memphis", "grizzlies", "mem"], "heat": ["miami", "heat", "mia"],
    "bucks": ["milwaukee", "bucks", "mil"], "timberwolves": ["minnesota", "timberwolves", "wolves", "min"],
    "pelicans": ["new orleans", "pelicans", "nop"], "knicks": ["new york", "knicks", "nyk"],
    "thunder": ["oklahoma city", "thunder", "okc"], "magic": ["orlando", "magic", "orl"],
    "76ers": ["philadelphia", "76ers", "sixers", "phi"], "suns": ["phoenix", "suns", "phx"],
    "trail blazers": ["portland", "trail blazers", "blazers", "por"],
    "kings": ["sacramento", "kings", "sac"], "spurs": ["san antonio", "spurs", "sas"],
    "raptors": ["toronto", "raptors", "tor"], "jazz": ["utah", "jazz", "uta"],
    "wizards": ["washington", "wizards", "was", "wiz"],
    # NFL
    "cardinals": ["arizona", "cardinals", "ari"], "falcons": ["atlanta", "falcons", "atl"],
    "ravens": ["baltimore", "ravens", "bal"], "bills": ["buffalo", "bills", "buf"],
    "panthers": ["carolina", "panthers", "car"], "bears": ["chicago", "bears", "chi"],
    "bengals": ["cincinnati", "bengals", "cin"], "browns": ["cleveland", "browns", "cle"],
    "cowboys": ["dallas", "cowboys", "dal"], "broncos": ["denver", "broncos", "den"],
    "lions": ["detroit", "lions", "det"], "packers": ["green bay", "packers", "gb"],
    "texans": ["houston", "texans", "hou"], "colts": ["indianapolis", "colts", "ind"],
    "jaguars": ["jacksonville", "jaguars", "jax"], "chiefs": ["kansas city", "chiefs", "kc"],
    "raiders": ["las vegas", "raiders", "lv"], "chargers": ["los angeles", "chargers", "lac"],
    "rams": ["los angeles", "rams", "lar"], "dolphins": ["miami", "dolphins", "mia"],
    "vikings": ["minnesota", "vikings", "min"], "patriots": ["new england", "patriots", "ne"],
    "saints": ["new orleans", "saints", "no"], "giants": ["new york", "giants", "nyg"],
    "jets": ["new york", "jets", "nyj"], "eagles": ["philadelphia", "eagles", "phi"],
    "steelers": ["pittsburgh", "steelers", "pit"], "49ers": ["san francisco", "49ers", "niners", "sf"],
    "seahawks": ["seattle", "seahawks", "sea"], "buccaneers": ["tampa bay", "buccaneers", "bucs", "tb"],
    "titans": ["tennessee", "titans", "ten"], "commanders": ["washington", "commanders", "was"],
    # NHL
    "bruins": ["boston", "bruins"], "sabres": ["buffalo", "sabres"],
    "flames": ["calgary", "flames"], "hurricanes": ["carolina", "hurricanes"],
    "blackhawks": ["chicago", "blackhawks"], "avalanche": ["colorado", "avalanche"],
    "blue jackets": ["columbus", "blue jackets"], "stars": ["dallas", "stars"],
    "red wings": ["detroit", "red wings"], "oilers": ["edmonton", "oilers"],
    "panthers_nhl": ["florida", "panthers"], "canadiens": ["montreal", "canadiens", "habs"],
    "predators": ["nashville", "predators", "preds"], "devils": ["new jersey", "devils"],
    "islanders": ["new york", "islanders", "nyi"], "rangers": ["new york", "rangers", "nyr"],
    "senators": ["ottawa", "senators", "sens"], "flyers": ["philadelphia", "flyers"],
    "penguins": ["pittsburgh", "penguins", "pens"], "sharks": ["san jose", "sharks"],
    "kraken": ["seattle", "kraken"], "blues": ["st. louis", "blues", "st louis"],
    "lightning": ["tampa bay", "lightning", "bolts"], "maple leafs": ["toronto", "maple leafs", "leafs"],
    "canucks": ["vancouver", "canucks"], "golden knights": ["vegas", "golden knights", "vgk"],
    "capitals": ["washington", "capitals", "caps"], "jets_nhl": ["winnipeg", "jets"],
}


class MarketMatcher:
    """
    Matches Polymarket signals to Kalshi market tickers.
    Handles sports (team name aliases), crypto, politics, and more.
    """

    def __init__(self, kalshi: KalshiAuthClient):
        self.kalshi = kalshi
        self.kalshi_markets: List[Dict] = []
        self.last_refresh = 0
        self.cache_ttl = 120  # refresh every 2 min (sports move fast)

    def refresh_markets(self):
        """Fetch ALL open Kalshi markets with pagination."""
        now = time.time()
        if now - self.last_refresh < self.cache_ttl and self.kalshi_markets:
            return

        print("  📡 Fetching all Kalshi markets...")
        self.kalshi_markets = self.kalshi.get_all_open_markets(max_markets=2000)
        self.last_refresh = now
        print(f"     Found {len(self.kalshi_markets)} open markets")

    def _expand_aliases(self, text: str) -> List[str]:
        """Given a text, find all team alias keywords it could match."""
        text_lower = text.lower()
        expanded = set()
        for team, aliases in TEAM_ALIASES.items():
            for alias in aliases:
                if alias in text_lower:
                    expanded.update(aliases)
                    break
        return list(expanded)

    def find_match(self, signal_title: str, signal_direction: str) -> Optional[Dict]:
        """
        Find the best Kalshi market match for a Polymarket signal.
        Uses team alias expansion for sports and keyword matching for everything else.
        """
        self.refresh_markets()

        # Get all possible aliases for teams mentioned in the signal
        signal_aliases = self._expand_aliases(signal_title)

        # Also extract regular keywords
        stop_words = {"will", "the", "a", "an", "in", "on", "by", "be", "to", "of", "and", "or",
                      "is", "it", "at", "for", "this", "that", "with", "from", "as", "are", "was",
                      "has", "have", "do", "does", "win", "winner", "vs", "vs.", "over", "under", "?"}
        keywords = [w.lower().strip("?.,!") for w in signal_title.split()
                    if w.lower().strip("?.,!") not in stop_words and len(w) > 2]

        if not keywords and not signal_aliases:
            return None

        best_match = None
        best_score = 0

        for market in self.kalshi_markets:
            title_lower = (market.get("title", "") + " " + market.get("subtitle", "")).lower()
            event_ticker = market.get("event_ticker", "").lower()
            category = market.get("category", "").lower()

            score = 0

            # Sports matching: check if team aliases overlap
            if signal_aliases:
                market_aliases = self._expand_aliases(title_lower)
                alias_overlap = len(set(signal_aliases) & set(market_aliases))
                if alias_overlap > 0:
                    # Both mention the same team(s) — strong match
                    # Need at least 2 teams matching for a game (home + away)
                    teams_in_signal = set()
                    teams_in_market = set()
                    for team, aliases in TEAM_ALIASES.items():
                        if any(a in signal_title.lower() for a in aliases):
                            teams_in_signal.add(team)
                        if any(a in title_lower for a in aliases):
                            teams_in_market.add(team)

                    common_teams = teams_in_signal & teams_in_market
                    if len(common_teams) >= 2:
                        score = 0.95  # Very high confidence — same game
                    elif len(common_teams) == 1:
                        score = 0.6   # One team matches — could be the same game

            # Regular keyword matching (for non-sports or as fallback)
            if score < 0.5 and keywords:
                matches = sum(1 for kw in keywords if kw in title_lower)
                kw_score = matches / len(keywords) if keywords else 0

                phrase = " ".join(keywords[:3])
                if phrase in title_lower:
                    kw_score += 0.3

                score = max(score, kw_score)

            # Must meet minimum threshold
            if score > best_score and score >= 0.4:
                best_score = score
                best_match = {
                    "ticker": market.get("ticker", ""),
                    "title": market.get("title", ""),
                    "yes_price": market.get("yes_price", 0),
                    "no_price": market.get("no_price", 0),
                    "volume": market.get("volume", 0),
                    "match_score": round(score, 2),
                    "status": market.get("status", ""),
                    "category": market.get("category", ""),
                    "event_ticker": market.get("event_ticker", ""),
                }

        return best_match


# ─── Signal Converter ───────────────────────────────────────────

def polymarket_signal_to_predictor(sig, signal_id: str = None) -> PredictorSignal:
    """Convert a SignalGenerator Signal to GovernanceEngine PredictorSignal."""
    return PredictorSignal(
        signal_id=signal_id or f"sig_{uuid.uuid4().hex[:8]}",
        market_slug=sig.market_slug,
        market_title=sig.market_title,
        direction=sig.direction.lower(),
        conviction=sig.conviction,
        num_traders=sig.num_traders,
        total_size=sig.total_size,
        avg_entry_price=sig.avg_entry_price,
        current_price=sig.current_price,
        expected_edge=sig.expected_edge,
        entry_quality=sig.entry_quality,
        ars_score=sig.ars_score,
        recommended_size=sig.recommended_size,
        traders=sig.traders,
    )


# ─── Audit File Logger ─────────────────────────────────────────

class AuditFile:
    """Append-only JSONL audit log."""

    def __init__(self, path: str = "live_audit.jsonl"):
        self.path = path

    def log(self, entry: Dict):
        entry["_logged_at"] = datetime.datetime.utcnow().isoformat()
        with open(self.path, "a") as f:
            f.write(json.dumps(entry, default=str) + "\n")
        print(f"  📝 Audit logged: {entry.get('decision', entry.get('event', 'unknown'))}")


# ─── Live Trader ────────────────────────────────────────────────

class LiveTrader:
    """
    The real deal. Signals → Governance → Kalshi.
    
    This is what makes AgentWallet real: every trade signal from an AI agent
    passes through a governance layer with spend controls, kill switches,
    and full audit trail before any money moves.
    """

    def __init__(self, dry_run: bool = False):
        self.dry_run = dry_run
        self.audit = AuditFile()

        # ── Kalshi Auth ──
        api_key = os.environ.get("KALSHI_API_KEY_ID")
        pk_path = os.environ.get("KALSHI_PRIVATE_KEY_PATH", "~/.kalshi/private_key.pem")
        pk_pem = os.environ.get("KALSHI_PRIVATE_KEY")
        pk_b64 = os.environ.get("KALSHI_PRIVATE_KEY_B64")

        # Decode base64 key if provided (for Cloud Run where multiline env vars are tricky)
        if pk_b64 and not pk_pem:
            import base64 as b64mod
            pk_pem = b64mod.b64decode(pk_b64).decode("utf-8")

        if not api_key:
            print("❌ Set KALSHI_API_KEY_ID environment variable")
            sys.exit(1)

        self.kalshi = KalshiAuthClient(
            api_key_id=api_key,
            private_key_path=pk_path if not pk_pem else None,
            private_key_pem=pk_pem,
        )

        # ── Get real balance ──
        balance_data = self.kalshi.get_balance()
        real_balance_cents = balance_data.get("balance", 0)
        real_balance = real_balance_cents / 100
        print(f"\n💰 Kalshi Balance: ${real_balance:.2f}")

        if real_balance < 1:
            print("❌ Balance too low to trade. Deposit funds first.")
            sys.exit(1)

        # ── Governance Engine (tuned for real balance) ──
        self.governance = GovernanceEngine({
            "initial_balance": real_balance,
            "max_per_trade_cents": min(500, int(real_balance_cents * 0.10)),    # 10% of balance per trade
            "max_daily_spend_cents": min(1000, int(real_balance_cents * 0.20)),  # 20% of balance per day
            "max_weekly_spend_cents": min(2500, int(real_balance_cents * 0.50)), # 50% of balance per week
            "max_position_contracts": 10,
            "min_entry_quality": "fair",
            "min_ars_score": 0.3,
            "min_conviction": 0.05,
            "allowed_signal_strengths": ["good", "fair"],
            "drawdown_kill_switch_pct": 0.20,   # kill at 20% loss
            "consecutive_loss_limit": 3,         # tight for small balance
            "trading_hours": {"start": 0, "end": 24},  # 24/7 — sports happen at night
            "blocked_categories": [],
        })

        # ── Market Matcher ──
        self.matcher = MarketMatcher(self.kalshi)

        # ── Signal Generator ──
        self.signal_gen = SignalGenerator()

        # ── Log startup ──
        self.audit.log({
            "event": "TRADER_STARTED",
            "balance": real_balance,
            "dry_run": dry_run,
            "config": {
                "max_per_trade": f"${self.governance.config['max_per_trade_cents']/100:.2f}",
                "max_daily": f"${self.governance.config['max_daily_spend_cents']/100:.2f}",
                "max_weekly": f"${self.governance.config['max_weekly_spend_cents']/100:.2f}",
                "drawdown_kill": f"{self.governance.config['drawdown_kill_switch_pct']:.0%}",
            }
        })

        print(f"\n🔐 Governance Config:")
        print(f"   Max per trade:  ${self.governance.config['max_per_trade_cents']/100:.2f}")
        print(f"   Max daily:      ${self.governance.config['max_daily_spend_cents']/100:.2f}")
        print(f"   Max weekly:     ${self.governance.config['max_weekly_spend_cents']/100:.2f}")
        print(f"   Kill switch:    {self.governance.config['drawdown_kill_switch_pct']:.0%} drawdown")
        print(f"   Mode:           {'🧪 DRY RUN' if dry_run else '🔴 LIVE TRADING'}")

    def fetch_signals(self) -> List:
        """Generate real signals from Polymarket leaderboard."""
        print("\n" + "=" * 60)
        print("📊 FETCHING SIGNALS FROM POLYMARKET")
        print("=" * 60)

        try:
            self.signal_gen.fetch_top_traders(limit=30)
            self.signal_gen.score_traders(min_pnl=5000)
            self.signal_gen.fetch_positions(top_n=15)
            raw_signals = self.signal_gen.aggregate_signals(min_traders=2, min_conviction=0.05)
            raw_signals = self.signal_gen.filter_resolved_markets(raw_signals)
            scored_signals = self.signal_gen.apply_ars_scoring(raw_signals)

            print(f"\n✅ Generated {len(scored_signals)} signals")
            return scored_signals

        except Exception as e:
            print(f"❌ Signal generation failed: {e}")
            self.audit.log({"event": "SIGNAL_ERROR", "error": str(e)})
            return []

    def run_pipeline(self, signals: List) -> Dict[str, Any]:
        """Run the full governance → execution pipeline."""
        print("\n" + "=" * 60)
        print("🔐 GOVERNANCE PIPELINE")
        print("=" * 60)

        results = {
            "total": len(signals),
            "matched": 0,
            "approved": 0,
            "blocked": 0,
            "executed": 0,
            "errors": 0,
            "trades": [],
        }

        for i, sig in enumerate(signals[:10]):  # Cap at 10 signals per run
            print(f"\n── Signal {i+1}/{min(len(signals), 10)} ──")
            print(f"   {sig.direction} on: {sig.market_title[:50]}")
            print(f"   ARS: {sig.ars_score:.2f} | Entry: {sig.entry_quality} | Conviction: {sig.conviction:.0%}")

            # Step 1: Match to Kalshi market
            kalshi_match = self.matcher.find_match(sig.market_title, sig.direction)

            if not kalshi_match:
                print(f"   ⚪ No Kalshi match found — skipping")
                continue

            results["matched"] += 1

            # Step 1b: If price is 0, this is likely a multi-game container.
            # Find the actual tradeable winner/moneyline market under this event.
            ticker = kalshi_match["ticker"]
            yes_price = kalshi_match["yes_price"]
            no_price = kalshi_match["no_price"]

            if yes_price == 0 and no_price == 0 and kalshi_match.get("event_ticker"):
                print(f"   🔍 Container market — searching event for tradeable market...")
                try:
                    event_markets = self.kalshi.get_event_markets(kalshi_match["event_ticker"])
                    # Find simple winner/moneyline markets (not O/U, not props)
                    for em in event_markets:
                        em_title = (em.get("title", "") + " " + em.get("subtitle", "")).lower()
                        em_yes = em.get("yes_price", 0)
                        em_no = em.get("no_price", 0)
                        # Skip markets with 0 prices or that look like props/O-U
                        if em_yes == 0 and em_no == 0:
                            continue
                        if "over" in em_title or "under" in em_title or "points" in em_title:
                            continue
                        # This is a tradeable market with real prices
                        ticker = em.get("ticker", ticker)
                        yes_price = em_yes
                        no_price = em_no
                        kalshi_match["title"] = em.get("title", kalshi_match["title"])
                        print(f"   ✅ Found tradeable: {ticker}")
                        print(f"      {em.get('title', '')}")
                        break

                    # If still no price, try fetching orderbook on original ticker
                    if yes_price == 0 and no_price == 0:
                        try:
                            ob = self.kalshi.get_orderbook(kalshi_match["ticker"])
                            orderbook = ob.get("orderbook", {})
                            yes_bids = orderbook.get("yes", [])
                            no_bids = orderbook.get("no", [])
                            if yes_bids:
                                yes_price = yes_bids[0][0] if isinstance(yes_bids[0], list) else yes_bids[0]
                            if no_bids:
                                no_price = no_bids[0][0] if isinstance(no_bids[0], list) else no_bids[0]
                        except Exception:
                            pass

                except Exception as e:
                    print(f"   ⚠️  Event lookup failed: {e}")

            # Skip if we still can't get a price
            if yes_price == 0 and no_price == 0:
                print(f"   ⚪ No valid price found — skipping")
                continue

            print(f"   🎯 Kalshi: {ticker} (match: {kalshi_match['match_score']})")
            print(f"      {kalshi_match['title']}")
            print(f"      Yes: {yes_price}¢ | No: {no_price}¢ | Vol: {kalshi_match['volume']}")

            # Step 2: Convert to PredictorSignal (with Kalshi price)
            kalshi_price = yes_price if sig.direction.lower() == "yes" else no_price
            if kalshi_price == 0:
                kalshi_price = yes_price or no_price  # Take whichever is nonzero
            pred_signal = polymarket_signal_to_predictor(sig)
            pred_signal.current_price = kalshi_price / 100 if kalshi_price > 0 else sig.current_price
            pred_signal.market_slug = ticker  # Use resolved Kalshi ticker

            # Step 3: Governance evaluation
            gov_result = self.governance.evaluate_signal(pred_signal)

            if gov_result.decision == GovernanceDecision.APPROVED:
                results["approved"] += 1
                print(f"   ✅ APPROVED — cost: ${gov_result.order_request['total_cost_cents']/100:.2f}")

                # Step 4: Execute trade (or dry run)
                if self.dry_run:
                    print(f"   🧪 DRY RUN — would place order on {ticker}")
                    self.audit.log({
                        "event": "DRY_RUN_APPROVED",
                        "signal": sig.market_title,
                        "ticker": ticker,
                        "direction": sig.direction,
                        "price_cents": kalshi_price,
                        "cost_cents": gov_result.order_request["total_cost_cents"],
                        "governance": gov_result.to_audit_entry(),
                    })
                else:
                    # REAL TRADE
                    try:
                        order = gov_result.order_request
                        trade_result = self.kalshi.create_order(
                            ticker=ticker,
                            side=sig.direction.lower(),
                            action="buy",
                            count=order["count"],
                            order_type="limit",
                            yes_price=kalshi_price if sig.direction.lower() == "yes" else None,
                            no_price=kalshi_price if sig.direction.lower() == "no" else None,
                        )

                        results["executed"] += 1
                        print(f"   🔴 EXECUTED — Order ID: {trade_result.get('order', {}).get('order_id', 'unknown')}")

                        # Record in governance spend tracker
                        self.governance.spend_tracker.record_trade(order["total_cost_cents"])

                        self.audit.log({
                            "event": "TRADE_EXECUTED",
                            "signal": sig.market_title,
                            "ticker": ticker,
                            "direction": sig.direction,
                            "count": order["count"],
                            "price_cents": kalshi_price,
                            "cost_cents": order["total_cost_cents"],
                            "order_response": trade_result,
                            "governance": gov_result.to_audit_entry(),
                        })

                        results["trades"].append({
                            "ticker": ticker,
                            "side": sig.direction,
                            "count": order["count"],
                            "price": kalshi_price,
                        })

                    except Exception as e:
                        results["errors"] += 1
                        print(f"   ❌ EXECUTION FAILED: {e}")
                        self.audit.log({
                            "event": "TRADE_FAILED",
                            "signal": sig.market_title,
                            "ticker": ticker,
                            "error": str(e),
                            "governance": gov_result.to_audit_entry(),
                        })

            else:
                results["blocked"] += 1
                blocking = [r.rule_name for r in gov_result.rules_evaluated if not r.passed]
                print(f"   🚫 {gov_result.decision.value.upper()} — blocked by: {', '.join(blocking)}")
                self.audit.log({
                    "event": "SIGNAL_BLOCKED",
                    "signal": sig.market_title,
                    "ticker": ticker,
                    "decision": gov_result.decision.value,
                    "blocking_rules": blocking,
                    "governance": gov_result.to_audit_entry(),
                })

        return results

    def run_once(self) -> Dict[str, Any]:
        """Single run of the full pipeline. Returns results dict."""
        print("\n" + "🟢" * 30)
        print(f"  LIVE TRADER RUN — {datetime.datetime.utcnow().isoformat()}")
        print("🟢" * 30)

        # Refresh balance
        try:
            bal = self.kalshi.get_balance()
            current = bal.get("balance", 0) / 100
            print(f"\n💰 Current balance: ${current:.2f}")
            self.governance.spend_tracker.current_balance = current
        except Exception as e:
            print(f"⚠️  Balance check failed: {e}")

        # Fetch signals
        signals = self.fetch_signals()
        if not signals:
            print("\n⚪ No signals generated. Waiting for next run.")
            return {"total": 0, "matched": 0, "approved": 0, "blocked": 0, "executed": 0, "errors": 0, "trades": []}

        # Run pipeline
        results = self.run_pipeline(signals)

        # Summary
        print("\n" + "=" * 60)
        print("📊 RUN SUMMARY")
        print("=" * 60)
        print(f"   Signals generated:  {results['total']}")
        print(f"   Kalshi matches:     {results['matched']}")
        print(f"   Governance approved: {results['approved']}")
        print(f"   Governance blocked:  {results['blocked']}")
        print(f"   Trades executed:     {results['executed']}")
        print(f"   Errors:             {results['errors']}")

        if results["trades"]:
            print(f"\n   💸 Trades placed:")
            for t in results["trades"]:
                print(f"      {t['side'].upper()} {t['count']}x {t['ticker']} @ {t['price']}¢")

        self.audit.log({"event": "RUN_COMPLETE", "summary": results})

        # Check governance stats
        stats = self.governance.get_stats()
        print(f"\n   🔐 Governance stats:")
        print(f"      Total processed: {stats['signals_processed']}")
        print(f"      Approval rate:   {stats['approval_rate']:.0%}")
        print(f"      Kill switch:     {'🔴 ACTIVE' if stats['kill_switch_active'] else '🟢 OFF'}")

        results["governance"] = stats
        return results

    def run_loop(self, interval_minutes: int = 30):
        """Run on a schedule."""
        print(f"\n🔄 Starting loop — running every {interval_minutes} minutes")
        print(f"   Press Ctrl+C to stop\n")

        while True:
            try:
                self.run_once()
            except KeyboardInterrupt:
                print("\n\n⏹️  Stopped by user.")
                self.audit.log({"event": "TRADER_STOPPED", "reason": "user_interrupt"})
                break
            except Exception as e:
                print(f"\n❌ Run failed: {e}")
                self.audit.log({"event": "RUN_ERROR", "error": str(e)})

            print(f"\n⏳ Next run in {interval_minutes} minutes...")
            try:
                time.sleep(interval_minutes * 60)
            except KeyboardInterrupt:
                print("\n\n⏹️  Stopped by user.")
                break


# ─── FastAPI Server (for Cloud Run + Cloud Scheduler) ──────────

def create_app() -> "FastAPI":
    """Create FastAPI app for Cloud Run deployment."""
    from fastapi import FastAPI, BackgroundTasks
    from fastapi.middleware.cors import CORSMiddleware

    app = FastAPI(title="AgentWallet Live Trader", version="1.0.0")
    app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])

    # Lazy-init trader (created on first request)
    _trader = {"instance": None}

    def get_trader(dry_run: bool = False) -> LiveTrader:
        if _trader["instance"] is None:
            mode = os.environ.get("TRADER_MODE", "live")
            _trader["instance"] = LiveTrader(dry_run=(mode == "dry-run" or dry_run))
        return _trader["instance"]

    @app.get("/health")
    def health():
        return {"status": "ok", "service": "agentwallet-live-trader", "timestamp": datetime.datetime.utcnow().isoformat()}

    @app.post("/run")
    def run_trade():
        """Trigger a single trading run. Called by Cloud Scheduler."""
        trader = get_trader()
        try:
            results = trader.run_once()
            return {"status": "ok", "results": results}
        except Exception as e:
            return {"status": "error", "error": str(e)}

    @app.get("/stats")
    def stats():
        """Get governance engine stats."""
        trader = get_trader()
        return {
            "governance": trader.governance.get_stats(),
            "dry_run": trader.dry_run,
            "audit_entries": len(trader.governance.audit_log),
        }

    @app.get("/balance")
    def balance():
        """Check real Kalshi balance."""
        trader = get_trader()
        try:
            bal = trader.kalshi.get_balance()
            return {"balance_cents": bal.get("balance", 0), "balance_usd": bal.get("balance", 0) / 100}
        except Exception as e:
            return {"error": str(e)}

    @app.post("/kill-switch")
    def kill_switch(activate: bool = True, reason: str = "manual"):
        """Activate or deactivate the kill switch."""
        trader = get_trader()
        if activate:
            trader.governance.activate_kill_switch(reason)
            return {"status": "kill_switch_activated", "reason": reason}
        else:
            trader.governance.reset_kill_switch("api_request")
            return {"status": "kill_switch_deactivated"}

    @app.get("/positions")
    def positions():
        """Get current Kalshi positions."""
        trader = get_trader()
        try:
            pos = trader.kalshi.get_positions()
            return pos
        except Exception as e:
            return {"error": str(e)}

    @app.get("/trades")
    def trades():
        """Get recent fills/trades from Kalshi."""
        trader = get_trader()
        try:
            data = trader.kalshi._request("GET", "/trade-api/v2/portfolio/fills", params={"limit": 20})
            return data
        except Exception as e:
            return {"error": str(e)}

    @app.get("/audit")
    def audit():
        """Get recent audit entries."""
        trader = get_trader()
        entries = []
        try:
            with open("live_audit.jsonl", "r") as f:
                for line in f:
                    if line.strip():
                        entries.append(json.loads(line.strip()))
        except FileNotFoundError:
            pass
        # Return last 50 entries, newest first
        return {"entries": entries[-50:][::-1], "total": len(entries)}

    @app.get("/dashboard")
    def dashboard():
        """All-in-one dashboard data endpoint."""
        trader = get_trader()
        result = {
            "timestamp": datetime.datetime.utcnow().isoformat(),
            "dry_run": trader.dry_run,
        }

        # Balance
        try:
            bal = trader.kalshi.get_balance()
            result["balance"] = {"cents": bal.get("balance", 0), "usd": bal.get("balance", 0) / 100}
        except Exception as e:
            result["balance"] = {"error": str(e)}

        # Positions
        try:
            pos = trader.kalshi.get_positions()
            result["positions"] = pos
        except Exception as e:
            result["positions"] = {"error": str(e)}

        # Governance stats
        try:
            stats = trader.governance.get_stats()
            result["governance"] = stats
        except Exception as e:
            result["governance"] = {"error": str(e)}

        # Recent fills
        try:
            fills = trader.kalshi._request("GET", "/trade-api/v2/portfolio/fills", params={"limit": 10})
            result["recent_fills"] = fills
        except Exception as e:
            result["recent_fills"] = {"error": str(e)}

        # Audit summary
        try:
            entries = []
            with open("live_audit.jsonl", "r") as f:
                for line in f:
                    if line.strip():
                        entries.append(json.loads(line.strip()))
            result["audit_count"] = len(entries)
            result["last_run"] = entries[-1] if entries else None
        except Exception:
            result["audit_count"] = 0
            result["last_run"] = None

        return result

    # ── Public Activity Feed (for social media / marketing) ──────

    @app.get("/public/feed")
    def public_feed(limit: int = 10):
        """
        Public activity feed — formatted for social sharing.
        Shows approved trades, blocked signals, and governance stats
        WITHOUT exposing sensitive data (no balances, no exact amounts).
        """
        trader = get_trader()
        entries = []

        try:
            with open("live_audit.jsonl", "r") as f:
                for line in f:
                    if line.strip():
                        entries.append(json.loads(line.strip()))
        except FileNotFoundError:
            pass

        feed = []
        for entry in entries[-100:][::-1]:  # Last 100, newest first
            event = entry.get("event", "")

            if event == "TRADE_EXECUTED":
                gov = entry.get("governance", {})
                feed.append({
                    "type": "trade_executed",
                    "icon": "✅",
                    "headline": "Agent placed a trade",
                    "market": entry.get("signal", "")[:80],
                    "direction": entry.get("direction", "").upper(),
                    "ticker": entry.get("ticker", ""),
                    "rules_checked": gov.get("rules_checked", 0),
                    "rules_failed": gov.get("rules_failed", 0),
                    "decision": "APPROVED",
                    "timestamp": entry.get("_logged_at", ""),
                })

            elif event == "SIGNAL_BLOCKED":
                gov = entry.get("governance", {})
                blocking = entry.get("blocking_rules", [])
                feed.append({
                    "type": "signal_blocked",
                    "icon": "🚫",
                    "headline": "Guardrails blocked a trade",
                    "market": entry.get("signal", "")[:80],
                    "direction": entry.get("direction", "").upper(),
                    "decision": entry.get("decision", "blocked").upper(),
                    "blocked_by": blocking,
                    "blocked_by_summary": ", ".join(blocking[:3]),
                    "rules_checked": gov.get("rules_checked", 0),
                    "timestamp": entry.get("_logged_at", ""),
                })

            elif event == "KILL_SWITCH_ACTIVATED":
                feed.append({
                    "type": "kill_switch",
                    "icon": "🛑",
                    "headline": "KILL SWITCH ACTIVATED",
                    "reason": entry.get("reason", ""),
                    "timestamp": entry.get("_logged_at", ""),
                })

            elif event == "RUN_COMPLETE":
                summary = entry.get("summary", {})
                if summary.get("matched", 0) > 0:
                    feed.append({
                        "type": "run_summary",
                        "icon": "📊",
                        "headline": "Trade cycle completed",
                        "signals_found": summary.get("total", 0),
                        "matched": summary.get("matched", 0),
                        "approved": summary.get("approved", 0),
                        "blocked": summary.get("blocked", 0),
                        "executed": summary.get("executed", 0),
                        "timestamp": entry.get("_logged_at", ""),
                    })

        # Stats summary
        stats = trader.governance.get_stats()

        return {
            "feed": feed[:limit],
            "summary": {
                "total_signals_processed": stats["signals_processed"],
                "total_approved": stats["approved"],
                "total_blocked": stats["blocked"],
                "approval_rate": f"{stats['approval_rate']:.0%}",
                "kill_switch": "ACTIVE" if stats["kill_switch_active"] else "OFF",
            },
            "generated_at": datetime.datetime.utcnow().isoformat(),
        }

    @app.get("/public/tweet")
    def generate_tweet():
        """
        Auto-generate a tweet from the latest trading activity.
        Hit this endpoint -> copy -> paste to Twitter.
        """
        trader = get_trader()
        entries = []

        try:
            with open("live_audit.jsonl", "r") as f:
                for line in f:
                    if line.strip():
                        entries.append(json.loads(line.strip()))
        except FileNotFoundError:
            return {"tweets": [], "stats": {}, "note": "No activity yet."}

        stats = trader.governance.get_stats()

        # Count recent events
        recent_trades = []
        recent_blocks = []
        for entry in entries[-20:][::-1]:
            event = entry.get("event", "")
            if event == "TRADE_EXECUTED":
                recent_trades.append(entry)
            elif event == "SIGNAL_BLOCKED":
                recent_blocks.append(entry)

        tweets = []

        # Generate "daily recap" tweet
        if recent_trades or recent_blocks:
            lines = ["\U0001f510 AgentWallet Predictor \u2014 Daily Update\n"]

            if recent_trades:
                lines.append(f"\u2705 {len(recent_trades)} trade(s) approved and executed")
                for t in recent_trades[:2]:
                    direction = t.get("direction", "").upper()
                    market = t.get("signal", "")[:50]
                    lines.append(f'  \u2192 {direction} on "{market}"')

            if recent_blocks:
                lines.append(f"\n\U0001f6ab {len(recent_blocks)} signal(s) blocked by guardrails")
                for b in recent_blocks[:2]:
                    market = b.get("signal", "")[:50]
                    rules = b.get("blocking_rules", [])
                    rule_text = rules[0] if rules else "governance rules"
                    lines.append(f'  \u2192 "{market}" blocked by {rule_text}')

            lines.append(f"\n\U0001f4ca Lifetime: {stats['approved']} approved / {stats['blocked']} blocked")
            lines.append(f"Approval rate: {stats['approval_rate']:.0%}")
            lines.append("\nEvery trade goes through 11 governance rules before money moves.")
            lines.append("\ngithub.com/JackD720/agentwallet")

            tweet_text = "\n".join(lines)
            tweets.append({
                "type": "daily_recap",
                "tweet": tweet_text,
                "char_count": len(tweet_text),
            })

        # Generate "blocked trade spotlight" tweet
        if recent_blocks:
            block = recent_blocks[0]
            market = block.get("signal", "")[:60]
            rules = block.get("blocking_rules", [])

            lines = [
                f'Our AI agent wanted to trade on "{market}"\n',
                "Our guardrails said no.\n",
            ]
            for rule in rules[:3]:
                lines.append(f"\U0001f6ab Blocked by: {rule}")

            lines.append("\nThis is why AI agents need governance \u2014 not just a credit card.")
            lines.append("\nBuilding financial infrastructure for AI agents: github.com/JackD720/agentwallet")

            tweet_text = "\n".join(lines)
            tweets.append({
                "type": "blocked_spotlight",
                "tweet": tweet_text,
                "char_count": len(tweet_text),
            })

        return {
            "tweets": tweets,
            "stats": {
                "recent_trades": len(recent_trades),
                "recent_blocks": len(recent_blocks),
                "lifetime_approved": stats["approved"],
                "lifetime_blocked": stats["blocked"],
            }
        }

    return app


# ─── CLI ────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="AgentWallet Live Trader")
    parser.add_argument("--dry-run", action="store_true", help="Run without placing real orders")
    parser.add_argument("--loop", type=int, default=0, help="Run every N minutes (0 = run once)")
    parser.add_argument("--serve", action="store_true", help="Run as HTTP server (for Cloud Run)")
    parser.add_argument("--port", type=int, default=8080, help="Server port (default: 8080)")
    args = parser.parse_args()

    print("=" * 60)
    print("🔐 AGENTWALLET LIVE TRADER")
    print("   Signals → Governance → Kalshi Execution")
    print("=" * 60)

    if args.serve:
        # Cloud Run mode: HTTP server
        import uvicorn
        app = create_app()
        print(f"\n🌐 Starting server on port {args.port}...")
        uvicorn.run(app, host="0.0.0.0", port=args.port)
    elif args.loop > 0:
        trader = LiveTrader(dry_run=args.dry_run)
        trader.run_loop(interval_minutes=args.loop)
    else:
        trader = LiveTrader(dry_run=args.dry_run)
        trader.run_once()


if __name__ == "__main__":
    main()