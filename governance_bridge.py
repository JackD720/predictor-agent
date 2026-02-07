"""
AgentWallet Governance Bridge
Connects Predictor Agent signals → AgentWallet Rules Engine → Kalshi Execution

This is the missing link: every trade signal must pass through governance
before it can touch real money.

Architecture:
  [Predictor Agent] → generates Signal
  [Governance Bridge] → evaluates against rules
  [AgentWallet] → enforces spend limits, audit logs
  [Kalshi] → executes trade (if approved)
"""

import uuid
import json
import time
from datetime import datetime, timedelta
from dataclasses import dataclass, field, asdict
from typing import Optional, Dict, Any, List
from enum import Enum


# ─────────────────────────────────────────────────────────────────
# Signal Schema (mirrors predictor-agent output)
# ─────────────────────────────────────────────────────────────────

@dataclass
class PredictorSignal:
    """A trading signal from the Predictor Agent."""
    signal_id: str
    market_slug: str
    market_title: str
    direction: str          # "yes" or "no"
    conviction: float       # 0-1
    num_traders: int
    total_size: float       # USD
    avg_entry_price: float  # 0-1
    current_price: float    # 0-1
    expected_edge: float
    entry_quality: str      # "good", "fair", "late", "very_late"
    ars_score: float        # 0-1
    recommended_size: float # % of portfolio
    traders: List[str]
    generated_at: str = field(default_factory=lambda: datetime.utcnow().isoformat())


# ─────────────────────────────────────────────────────────────────
# Governance Decision
# ─────────────────────────────────────────────────────────────────

class GovernanceDecision(Enum):
    APPROVED = "approved"
    BLOCKED = "blocked"
    REQUIRES_APPROVAL = "requires_approval"
    KILL_SWITCHED = "kill_switched"


@dataclass
class RuleEvaluation:
    """Result of a single rule check."""
    rule_id: str
    rule_name: str
    rule_type: str
    passed: bool
    reason: str
    details: Dict[str, Any] = field(default_factory=dict)


@dataclass
class GovernanceResult:
    """Full governance evaluation result — this is the audit record."""
    evaluation_id: str
    signal: Dict[str, Any]
    decision: GovernanceDecision
    rules_evaluated: List[RuleEvaluation]
    order_request: Optional[Dict[str, Any]]
    execution_result: Optional[Dict[str, Any]]
    wallet_state: Dict[str, Any]
    timestamp: str
    latency_ms: float
    
    def to_audit_entry(self) -> Dict[str, Any]:
        """Convert to audit log format."""
        return {
            "evaluation_id": self.evaluation_id,
            "timestamp": self.timestamp,
            "signal_id": self.signal.get("signal_id"),
            "market": self.signal.get("market_title"),
            "direction": self.signal.get("direction"),
            "decision": self.decision.value,
            "rules_checked": len(self.rules_evaluated),
            "rules_failed": len([r for r in self.rules_evaluated if not r.passed]),
            "blocking_rules": [r.rule_name for r in self.rules_evaluated if not r.passed],
            "order_value_cents": self.order_request.get("total_cost_cents") if self.order_request else None,
            "latency_ms": self.latency_ms,
        }


# ─────────────────────────────────────────────────────────────────
# Spend & Position Tracker
# ─────────────────────────────────────────────────────────────────

class SpendTracker:
    """Tracks agent spending across time windows."""
    
    def __init__(self):
        self.transactions: List[Dict[str, Any]] = []
        self.peak_balance: float = 0
        self.current_balance: float = 0
        self.total_pnl: float = 0
        self.consecutive_losses: int = 0
    
    def record_trade(self, amount_cents: int, pnl: float = 0):
        self.transactions.append({
            "timestamp": datetime.utcnow(),
            "amount_cents": amount_cents,
            "pnl": pnl,
        })
        self.current_balance -= amount_cents / 100
        self.total_pnl += pnl
        if pnl < 0:
            self.consecutive_losses += 1
        else:
            self.consecutive_losses = 0
        if self.current_balance > self.peak_balance:
            self.peak_balance = self.current_balance
    
    def get_spend_since(self, since: datetime) -> int:
        return sum(
            t["amount_cents"] for t in self.transactions
            if t["timestamp"] >= since
        )
    
    def get_daily_spend(self) -> int:
        return self.get_spend_since(datetime.utcnow() - timedelta(days=1))
    
    def get_weekly_spend(self) -> int:
        return self.get_spend_since(datetime.utcnow() - timedelta(days=7))
    
    def get_drawdown(self) -> float:
        if self.peak_balance <= 0:
            return 0
        return (self.peak_balance - self.current_balance) / self.peak_balance
    
    def get_state(self) -> Dict[str, Any]:
        return {
            "current_balance": self.current_balance,
            "peak_balance": self.peak_balance,
            "total_pnl": self.total_pnl,
            "daily_spend_cents": self.get_daily_spend(),
            "weekly_spend_cents": self.get_weekly_spend(),
            "drawdown_pct": round(self.get_drawdown() * 100, 1),
            "consecutive_losses": self.consecutive_losses,
            "total_transactions": len(self.transactions),
        }


# ─────────────────────────────────────────────────────────────────
# Governance Engine (the core innovation)
# ─────────────────────────────────────────────────────────────────

class GovernanceEngine:
    """
    The bridge between AI agent signals and financial execution.
    
    Every signal must pass through this engine before any money moves.
    This is what AgentWallet is selling: the governance layer.
    """
    
    def __init__(self, config: Optional[Dict[str, Any]] = None):
        self.config = config or self._default_config()
        self.spend_tracker = SpendTracker()
        self.audit_log: List[Dict[str, Any]] = []
        self.kill_switch_active = False
        self.kill_switch_reason = ""
        self.total_signals_processed = 0
        self.total_blocked = 0
        self.total_approved = 0
        
        # Initialize balance
        self.spend_tracker.current_balance = self.config.get("initial_balance", 500)
        self.spend_tracker.peak_balance = self.spend_tracker.current_balance
    
    @staticmethod
    def _default_config() -> Dict[str, Any]:
        return {
            "initial_balance": 500,       # $500 starting balance
            "max_per_trade_cents": 2000,   # $20 max per trade
            "max_daily_spend_cents": 5000, # $50/day max
            "max_weekly_spend_cents": 15000,  # $150/week max
            "max_position_contracts": 50,
            "min_entry_quality": "fair",   # block "late" and "very_late"
            "min_ars_score": 0.3,          # minimum signal quality
            "min_conviction": 0.05,        # minimum trader consensus
            "allowed_signal_strengths": ["good", "fair"],
            "drawdown_kill_switch_pct": 0.20,  # kill switch at 20% drawdown
            "consecutive_loss_limit": 5,
            "trading_hours": {"start": 6, "end": 23},  # EST
            "blocked_categories": [],
        }
    
    # ─────────────────────────────────────────────────────────
    # Rule Evaluators
    # ─────────────────────────────────────────────────────────
    
    def _check_kill_switch(self) -> RuleEvaluation:
        return RuleEvaluation(
            rule_id="kill_switch",
            rule_name="Kill Switch",
            rule_type="KILL_SWITCH",
            passed=not self.kill_switch_active,
            reason=self.kill_switch_reason if self.kill_switch_active else "Kill switch not active",
            details={"active": self.kill_switch_active}
        )
    
    def _check_entry_quality(self, signal: PredictorSignal) -> RuleEvaluation:
        allowed = self.config["allowed_signal_strengths"]
        passed = signal.entry_quality in allowed
        return RuleEvaluation(
            rule_id="entry_quality_filter",
            rule_name="Entry Quality Filter",
            rule_type="SIGNAL_FILTER",
            passed=passed,
            reason=f"Entry quality '{signal.entry_quality}' {'is' if passed else 'not in'} allowed: {allowed}",
            details={"entry_quality": signal.entry_quality, "allowed": allowed}
        )
    
    def _check_ars_score(self, signal: PredictorSignal) -> RuleEvaluation:
        min_score = self.config["min_ars_score"]
        passed = signal.ars_score >= min_score
        return RuleEvaluation(
            rule_id="ars_score_minimum",
            rule_name="ARS Score Minimum",
            rule_type="SIGNAL_FILTER",
            passed=passed,
            reason=f"ARS score {signal.ars_score:.2f} {'≥' if passed else '<'} minimum {min_score}",
            details={"ars_score": signal.ars_score, "minimum": min_score}
        )
    
    def _check_conviction(self, signal: PredictorSignal) -> RuleEvaluation:
        min_conv = self.config["min_conviction"]
        passed = signal.conviction >= min_conv
        return RuleEvaluation(
            rule_id="conviction_minimum",
            rule_name="Trader Conviction Minimum",
            rule_type="SIGNAL_FILTER",
            passed=passed,
            reason=f"Conviction {signal.conviction:.0%} {'≥' if passed else '<'} minimum {min_conv:.0%}",
            details={"conviction": signal.conviction, "minimum": min_conv}
        )
    
    def _check_per_trade_limit(self, cost_cents: int) -> RuleEvaluation:
        limit = self.config["max_per_trade_cents"]
        passed = cost_cents <= limit
        return RuleEvaluation(
            rule_id="per_trade_limit",
            rule_name="Per-Trade Spend Limit",
            rule_type="PER_TRANSACTION_LIMIT",
            passed=passed,
            reason=f"Trade cost ${cost_cents/100:.2f} {'≤' if passed else '>'} limit ${limit/100:.2f}",
            details={"cost_cents": cost_cents, "limit_cents": limit}
        )
    
    def _check_daily_limit(self, cost_cents: int) -> RuleEvaluation:
        limit = self.config["max_daily_spend_cents"]
        current = self.spend_tracker.get_daily_spend()
        projected = current + cost_cents
        passed = projected <= limit
        return RuleEvaluation(
            rule_id="daily_spend_limit",
            rule_name="Daily Spend Limit",
            rule_type="DAILY_LIMIT",
            passed=passed,
            reason=f"Daily spend ${projected/100:.2f} {'≤' if passed else '>'} limit ${limit/100:.2f} (current: ${current/100:.2f})",
            details={"current_cents": current, "projected_cents": projected, "limit_cents": limit}
        )
    
    def _check_weekly_limit(self, cost_cents: int) -> RuleEvaluation:
        limit = self.config["max_weekly_spend_cents"]
        current = self.spend_tracker.get_weekly_spend()
        projected = current + cost_cents
        passed = projected <= limit
        return RuleEvaluation(
            rule_id="weekly_spend_limit",
            rule_name="Weekly Spend Limit",
            rule_type="WEEKLY_LIMIT",
            passed=passed,
            reason=f"Weekly spend ${projected/100:.2f} {'≤' if passed else '>'} limit ${limit/100:.2f}",
            details={"current_cents": current, "projected_cents": projected, "limit_cents": limit}
        )
    
    def _check_drawdown(self) -> RuleEvaluation:
        threshold = self.config["drawdown_kill_switch_pct"]
        current_dd = self.spend_tracker.get_drawdown()
        passed = current_dd < threshold
        
        if not passed and not self.kill_switch_active:
            self.kill_switch_active = True
            self.kill_switch_reason = f"Drawdown {current_dd:.1%} exceeded threshold {threshold:.0%}"
        
        return RuleEvaluation(
            rule_id="drawdown_monitor",
            rule_name="Drawdown Kill Switch",
            rule_type="KILL_SWITCH",
            passed=passed,
            reason=f"Drawdown {current_dd:.1%} {'<' if passed else '≥'} threshold {threshold:.0%}",
            details={"drawdown": current_dd, "threshold": threshold}
        )
    
    def _check_consecutive_losses(self) -> RuleEvaluation:
        limit = self.config["consecutive_loss_limit"]
        current = self.spend_tracker.consecutive_losses
        passed = current < limit
        return RuleEvaluation(
            rule_id="consecutive_losses",
            rule_name="Consecutive Loss Limit",
            rule_type="KILL_SWITCH",
            passed=passed,
            reason=f"{current} consecutive losses {'<' if passed else '≥'} limit of {limit}",
            details={"consecutive_losses": current, "limit": limit}
        )
    
    def _check_trading_hours(self) -> RuleEvaluation:
        hours = self.config["trading_hours"]
        current_hour = datetime.utcnow().hour
        passed = hours["start"] <= current_hour < hours["end"]
        return RuleEvaluation(
            rule_id="trading_hours",
            rule_name="Trading Hours Window",
            rule_type="TIME_WINDOW",
            passed=passed,
            reason=f"Current hour {current_hour} {'within' if passed else 'outside'} {hours['start']}:00-{hours['end']}:00",
            details={"current_hour": current_hour, **hours}
        )
    
    def _check_balance(self, cost_cents: int) -> RuleEvaluation:
        balance_cents = int(self.spend_tracker.current_balance * 100)
        passed = cost_cents <= balance_cents
        return RuleEvaluation(
            rule_id="sufficient_balance",
            rule_name="Sufficient Balance",
            rule_type="BALANCE_CHECK",
            passed=passed,
            reason=f"Balance ${balance_cents/100:.2f} {'≥' if passed else '<'} cost ${cost_cents/100:.2f}",
            details={"balance_cents": balance_cents, "cost_cents": cost_cents}
        )
    
    # ─────────────────────────────────────────────────────────
    # Main Evaluation Pipeline
    # ─────────────────────────────────────────────────────────
    
    def evaluate_signal(self, signal: PredictorSignal) -> GovernanceResult:
        """
        Evaluate a predictor signal through all governance rules.
        
        This is the core function — every signal passes through here
        before any money can move.
        """
        start_time = time.time()
        self.total_signals_processed += 1
        
        # Calculate order parameters from signal
        price_cents = int(signal.current_price * 100)
        contracts = max(1, min(
            int(signal.recommended_size * self.spend_tracker.current_balance / max(signal.current_price, 0.01)),
            self.config["max_position_contracts"]
        ))
        total_cost_cents = price_cents * contracts
        
        order_request = {
            "ticker": signal.market_slug,
            "side": signal.direction,
            "action": "buy",
            "count": contracts,
            "type": "limit",
            f"{signal.direction}_price": price_cents,
            "total_cost_cents": total_cost_cents,
            "signal_id": signal.signal_id,
        }
        
        # ── Run all rules ──
        evaluations: List[RuleEvaluation] = []
        
        # 1. Kill switch (highest priority)
        evaluations.append(self._check_kill_switch())
        
        # 2. Drawdown monitor
        evaluations.append(self._check_drawdown())
        
        # 3. Consecutive losses
        evaluations.append(self._check_consecutive_losses())
        
        # 4. Signal quality filters
        evaluations.append(self._check_entry_quality(signal))
        evaluations.append(self._check_ars_score(signal))
        evaluations.append(self._check_conviction(signal))
        
        # 5. Spend limits
        evaluations.append(self._check_per_trade_limit(total_cost_cents))
        evaluations.append(self._check_daily_limit(total_cost_cents))
        evaluations.append(self._check_weekly_limit(total_cost_cents))
        
        # 6. Balance check
        evaluations.append(self._check_balance(total_cost_cents))
        
        # 7. Trading hours
        evaluations.append(self._check_trading_hours())
        
        # ── Determine decision ──
        failed_rules = [e for e in evaluations if not e.passed]
        kill_switched = any(e.rule_type == "KILL_SWITCH" and not e.passed for e in evaluations)
        
        if kill_switched:
            decision = GovernanceDecision.KILL_SWITCHED
        elif failed_rules:
            decision = GovernanceDecision.BLOCKED
        else:
            decision = GovernanceDecision.APPROVED
        
        # Track stats
        if decision == GovernanceDecision.APPROVED:
            self.total_approved += 1
        else:
            self.total_blocked += 1
        
        latency_ms = (time.time() - start_time) * 1000
        
        result = GovernanceResult(
            evaluation_id=str(uuid.uuid4()),
            signal=asdict(signal),
            decision=decision,
            rules_evaluated=evaluations,
            order_request=order_request if decision == GovernanceDecision.APPROVED else None,
            execution_result=None,  # Filled after Kalshi execution
            wallet_state=self.spend_tracker.get_state(),
            timestamp=datetime.utcnow().isoformat(),
            latency_ms=round(latency_ms, 2),
        )
        
        # Append to audit log
        self.audit_log.append(result.to_audit_entry())
        
        return result
    
    def execute_approved_trade(self, result: GovernanceResult) -> GovernanceResult:
        """
        Execute an approved trade on Kalshi.
        In demo mode, simulates execution. In production, calls Kalshi API.
        """
        if result.decision != GovernanceDecision.APPROVED:
            return result
        
        # Record the spend
        cost = result.order_request["total_cost_cents"]
        self.spend_tracker.record_trade(cost)
        
        # In production: call AgentWallet.create_order() here
        result.execution_result = {
            "status": "executed",
            "order_id": str(uuid.uuid4()),
            "filled_at": datetime.utcnow().isoformat(),
            "cost_cents": cost,
        }
        
        return result
    
    # ─────────────────────────────────────────────────────────
    # Kill Switch Controls
    # ─────────────────────────────────────────────────────────
    
    def activate_kill_switch(self, reason: str):
        self.kill_switch_active = True
        self.kill_switch_reason = reason
        self.audit_log.append({
            "evaluation_id": str(uuid.uuid4()),
            "timestamp": datetime.utcnow().isoformat(),
            "event": "KILL_SWITCH_ACTIVATED",
            "reason": reason,
        })
    
    def reset_kill_switch(self, authorized_by: str):
        self.kill_switch_active = False
        self.kill_switch_reason = ""
        self.audit_log.append({
            "evaluation_id": str(uuid.uuid4()),
            "timestamp": datetime.utcnow().isoformat(),
            "event": "KILL_SWITCH_RESET",
            "authorized_by": authorized_by,
        })
    
    # ─────────────────────────────────────────────────────────
    # Stats & Reporting
    # ─────────────────────────────────────────────────────────
    
    def get_stats(self) -> Dict[str, Any]:
        return {
            "signals_processed": self.total_signals_processed,
            "approved": self.total_approved,
            "blocked": self.total_blocked,
            "approval_rate": self.total_approved / max(self.total_signals_processed, 1),
            "kill_switch_active": self.kill_switch_active,
            "wallet": self.spend_tracker.get_state(),
            "config": {
                "max_per_trade": f"${self.config['max_per_trade_cents']/100:.0f}",
                "max_daily": f"${self.config['max_daily_spend_cents']/100:.0f}",
                "drawdown_threshold": f"{self.config['drawdown_kill_switch_pct']:.0%}",
            }
        }


# ─────────────────────────────────────────────────────────────────
# Demo: Full Pipeline
# ─────────────────────────────────────────────────────────────────

def run_demo():
    """
    Demonstrates the full governance pipeline with sample signals.
    This is what you'd screen-record for the tweet.
    """
    print("=" * 70)
    print("🔐 AGENTWALLET GOVERNANCE BRIDGE — LIVE DEMO")
    print("=" * 70)
    print()
    
    # Initialize governance engine
    engine = GovernanceEngine({
        "initial_balance": 500,
        "max_per_trade_cents": 2000,      # $20
        "max_daily_spend_cents": 5000,    # $50
        "max_weekly_spend_cents": 15000,  # $150
        "max_position_contracts": 50,
        "min_entry_quality": "fair",
        "min_ars_score": 0.3,
        "min_conviction": 0.05,
        "allowed_signal_strengths": ["good", "fair"],
        "drawdown_kill_switch_pct": 0.20,
        "consecutive_loss_limit": 5,
        "trading_hours": {"start": 0, "end": 24},  # Allow all hours for demo
        "blocked_categories": [],
    })
    
    print(f"  Wallet Balance: ${engine.spend_tracker.current_balance:.2f}")
    print(f"  Max Per Trade:  ${engine.config['max_per_trade_cents']/100:.0f}")
    print(f"  Daily Limit:    ${engine.config['max_daily_spend_cents']/100:.0f}")
    print(f"  Kill Switch:    {engine.config['drawdown_kill_switch_pct']:.0%} drawdown")
    print()
    
    # Sample signals (what the predictor agent would generate)
    signals = [
        PredictorSignal(
            signal_id="sig_001",
            market_slug="KXBTC-26FEB-B100K",
            market_title="Bitcoin above $100k on Feb 28?",
            direction="yes",
            conviction=0.35,
            num_traders=7,
            total_size=45000,
            avg_entry_price=0.52,
            current_price=0.58,
            expected_edge=0.115,
            entry_quality="good",
            ars_score=0.72,
            recommended_size=0.04,
            traders=["whale_01", "shark_02", "prof_03"],
        ),
        PredictorSignal(
            signal_id="sig_002",
            market_slug="KXFED-26MAR-RATECUT",
            market_title="Fed rate cut in March 2026?",
            direction="no",
            conviction=0.20,
            num_traders=4,
            total_size=28000,
            avg_entry_price=0.71,
            current_price=0.73,
            expected_edge=0.028,
            entry_quality="fair",
            ars_score=0.55,
            recommended_size=0.03,
            traders=["macro_king", "fed_watcher"],
        ),
        PredictorSignal(
            signal_id="sig_003",
            market_slug="KXAI-26FEB-GPT5",
            market_title="GPT-5 released before March 2026?",
            direction="yes",
            conviction=0.10,
            num_traders=2,
            total_size=12000,
            avg_entry_price=0.15,
            current_price=0.82,
            expected_edge=4.47,
            entry_quality="very_late",  # ← This will be BLOCKED
            ars_score=0.18,
            recommended_size=0.01,
            traders=["tech_bet_01"],
        ),
        PredictorSignal(
            signal_id="sig_004",
            market_slug="KXECON-26Q1-RECESSION",
            market_title="US recession declared in Q1 2026?",
            direction="no",
            conviction=0.45,
            num_traders=9,
            total_size=67000,
            avg_entry_price=0.88,
            current_price=0.91,
            expected_edge=0.034,
            entry_quality="good",
            ars_score=0.81,
            recommended_size=0.06,
            traders=["econ_prof", "hedge_01", "macro_king"],
        ),
        PredictorSignal(
            signal_id="sig_005",
            market_slug="KXSPORT-SUPERBOWL",
            market_title="Super Bowl LX total over 49.5?",
            direction="yes",
            conviction=0.08,
            num_traders=2,
            total_size=5000,
            avg_entry_price=0.45,
            current_price=0.51,
            expected_edge=0.133,
            entry_quality="good",
            ars_score=0.22,  # ← Below ARS minimum, will be BLOCKED
            recommended_size=0.02,
            traders=["sports_degen"],
        ),
    ]
    
    # Process each signal through governance
    for i, signal in enumerate(signals):
        print(f"{'─' * 70}")
        print(f"📡 SIGNAL {i+1}/{len(signals)}: {signal.direction.upper()} on \"{signal.market_title}\"")
        print(f"   ARS: {signal.ars_score:.2f} | Entry: {signal.entry_quality} | Conviction: {signal.conviction:.0%} | Price: {signal.current_price:.2f}")
        print()
        
        # Evaluate through governance
        result = engine.evaluate_signal(signal)
        
        # Show rule results
        for rule in result.rules_evaluated:
            icon = "✅" if rule.passed else "❌"
            print(f"   {icon} {rule.rule_name}: {rule.reason}")
        
        print()
        
        # Show decision
        if result.decision == GovernanceDecision.APPROVED:
            print(f"   ✅ APPROVED — Order: {result.order_request['count']} contracts @ {result.order_request.get('yes_price') or result.order_request.get('no_price')}¢")
            result = engine.execute_approved_trade(result)
            print(f"   💰 Executed — Order ID: {result.execution_result['order_id'][:12]}...")
        elif result.decision == GovernanceDecision.BLOCKED:
            blocking = [r for r in result.rules_evaluated if not r.passed]
            print(f"   🚫 BLOCKED by {len(blocking)} rule(s): {', '.join(r.rule_name for r in blocking)}")
        elif result.decision == GovernanceDecision.KILL_SWITCHED:
            print(f"   🛑 KILL SWITCH ACTIVE — All trading halted")
        
        print(f"   📊 Wallet: ${engine.spend_tracker.current_balance:.2f} | Daily: ${engine.spend_tracker.get_daily_spend()/100:.2f}/$50")
        print()
    
    # Final stats
    print("=" * 70)
    print("📋 GOVERNANCE SUMMARY")
    print("=" * 70)
    stats = engine.get_stats()
    print(f"  Signals Processed:  {stats['signals_processed']}")
    print(f"  Approved:           {stats['approved']}")
    print(f"  Blocked:            {stats['blocked']}")
    print(f"  Approval Rate:      {stats['approval_rate']:.0%}")
    print(f"  Kill Switch:        {'🔴 ACTIVE' if stats['kill_switch_active'] else '🟢 Inactive'}")
    print(f"  Final Balance:      ${stats['wallet']['current_balance']:.2f}")
    print(f"  Drawdown:           {stats['wallet']['drawdown_pct']}%")
    print()
    
    # Audit log
    print("📜 AUDIT LOG:")
    for entry in engine.audit_log:
        if "decision" in entry:
            icon = {"approved": "✅", "blocked": "🚫", "kill_switched": "🛑"}.get(entry["decision"], "❓")
            print(f"  {icon} [{entry['timestamp'][:19]}] {entry['decision'].upper()} — {entry['market']} ({entry['direction']})")
            if entry.get("blocking_rules"):
                print(f"     Blocked by: {', '.join(entry['blocking_rules'])}")
    
    return engine


if __name__ == "__main__":
    engine = run_demo()
