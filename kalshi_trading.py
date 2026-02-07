"""
Kalshi Authenticated Trading Client

Extends the base KalshiClient with authenticated endpoints for:
- Placing orders
- Canceling orders  
- Checking balance
- Managing positions

Integrates with AgentWallet for spend controls and audit logging.

Setup:
1. Generate API key at https://kalshi.com/account/api
2. Save private key as .pem file
3. Set environment variables:
   - KALSHI_API_KEY_ID=your-key-id
   - KALSHI_PRIVATE_KEY_PATH=path/to/private_key.pem
   - KALSHI_ENV=demo|prod (default: demo)
"""

import os
import time
import base64
import requests
from typing import Optional, Literal
from dataclasses import dataclass, asdict
from datetime import datetime
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import padding
from cryptography.hazmat.backends import default_backend


# API URLs
PROD_URL = "https://trading-api.kalshi.com/trade-api/v2"
DEMO_URL = "https://demo-api.kalshi.co/trade-api/v2"


@dataclass
class KalshiBalance:
    """Account balance info"""
    balance: float  # in dollars
    available_balance: float  # in dollars (excluding pending orders)
    
    
@dataclass
class KalshiPosition:
    """A position in a market"""
    ticker: str
    market_title: str
    side: str  # "yes" or "no"
    quantity: int
    average_price: float  # in cents
    market_value: float  # current value in cents
    pnl: float  # profit/loss in cents
    

@dataclass
class KalshiOrder:
    """An order on Kalshi"""
    order_id: str
    ticker: str
    side: str  # "yes" or "no"
    type: str  # "limit" or "market"
    price: Optional[int]  # in cents, None for market orders
    quantity: int
    filled_quantity: int
    status: str  # "open", "filled", "cancelled", "expired"
    created_at: datetime
    

@dataclass
class OrderResult:
    """Result of placing an order"""
    success: bool
    order_id: Optional[str]
    filled_quantity: int
    average_price: Optional[float]
    error: Optional[str] = None
    

class KalshiTradingClient:
    """
    Authenticated Kalshi client for trading.
    
    Usage:
        client = KalshiTradingClient(
            api_key_id="your-key-id",
            private_key_path="path/to/key.pem",
            environment="demo"  # Use demo for testing!
        )
        
        # Check balance
        balance = client.get_balance()
        print(f"Available: ${balance.available_balance:.2f}")
        
        # Place order
        result = client.place_order(
            ticker="KXBTC-25FEB01-B100000",
            side="yes",
            quantity=10,
            price=45  # 45 cents
        )
    """
    
    def __init__(
        self,
        api_key_id: Optional[str] = None,
        private_key_path: Optional[str] = None,
        private_key_pem: Optional[str] = None,
        environment: Literal["demo", "prod"] = "demo",
        rate_limit_delay: float = 0.2
    ):
        """
        Initialize the trading client.
        
        Args:
            api_key_id: Kalshi API key ID (or set KALSHI_API_KEY_ID env var)
            private_key_path: Path to private key .pem file (or set KALSHI_PRIVATE_KEY_PATH)
            private_key_pem: Private key PEM string (alternative to path)
            environment: "demo" for paper trading, "prod" for real money
            rate_limit_delay: Seconds between requests
        """
        self.api_key_id = api_key_id or os.getenv("KALSHI_API_KEY_ID")
        self.environment = environment or os.getenv("KALSHI_ENV", "demo")
        self.base_url = PROD_URL if self.environment == "prod" else DEMO_URL
        self.rate_limit_delay = rate_limit_delay
        self._last_request = 0
        
        # Load private key
        if private_key_pem:
            self.private_key = serialization.load_pem_private_key(
                private_key_pem.encode(),
                password=None,
                backend=default_backend()
            )
        else:
            key_path = private_key_path or os.getenv("KALSHI_PRIVATE_KEY_PATH")
            if key_path:
                with open(key_path, "rb") as f:
                    self.private_key = serialization.load_pem_private_key(
                        f.read(),
                        password=None,
                        backend=default_backend()
                    )
            else:
                self.private_key = None
                
        self.session = requests.Session()
        
        if not self.api_key_id or not self.private_key:
            print("⚠️  Warning: No API credentials provided. Only public endpoints will work.")
            print("   Set KALSHI_API_KEY_ID and KALSHI_PRIVATE_KEY_PATH environment variables.")
    
    def _sign_request(self, method: str, path: str) -> dict:
        """
        Generate authentication headers for a request.
        
        Returns dict with required headers.
        """
        timestamp = str(int(time.time() * 1000))
        
        # Sign: timestamp + method + path (without query params)
        path_without_query = path.split("?")[0]
        message = f"{timestamp}{method}/trade-api/v2{path_without_query}"
        
        signature = self.private_key.sign(
            message.encode(),
            padding.PKCS1v15(),
            hashes.SHA256()
        )
        
        return {
            "KALSHI-ACCESS-KEY": self.api_key_id,
            "KALSHI-ACCESS-TIMESTAMP": timestamp,
            "KALSHI-ACCESS-SIGNATURE": base64.b64encode(signature).decode(),
            "Content-Type": "application/json"
        }
    
    def _request(
        self,
        method: str,
        endpoint: str,
        params: dict = None,
        json_body: dict = None,
        authenticated: bool = True
    ) -> dict:
        """Make a rate-limited request to the API."""
        # Rate limiting
        elapsed = time.time() - self._last_request
        if elapsed < self.rate_limit_delay:
            time.sleep(self.rate_limit_delay - elapsed)
        
        url = f"{self.base_url}{endpoint}"
        
        headers = {}
        if authenticated:
            if not self.api_key_id or not self.private_key:
                raise ValueError("Authentication required but no credentials provided")
            headers = self._sign_request(method, endpoint)
        
        response = self.session.request(
            method=method,
            url=url,
            params=params,
            json=json_body,
            headers=headers
        )
        
        self._last_request = time.time()
        
        if not response.ok:
            error_msg = f"API error {response.status_code}: {response.text}"
            raise Exception(error_msg)
            
        return response.json() if response.text else {}
    
    # ============ BALANCE & PORTFOLIO ============
    
    def get_balance(self) -> KalshiBalance:
        """
        Get account balance.
        
        Returns:
            KalshiBalance with balance and available_balance in dollars
        """
        data = self._request("GET", "/portfolio/balance")
        
        return KalshiBalance(
            balance=data.get("balance", 0) / 100,  # Convert cents to dollars
            available_balance=data.get("available_balance", 0) / 100
        )
    
    def get_positions(self, ticker: Optional[str] = None) -> list[KalshiPosition]:
        """
        Get current positions.
        
        Args:
            ticker: Optional filter by market ticker
            
        Returns:
            List of positions
        """
        params = {}
        if ticker:
            params["ticker"] = ticker
            
        data = self._request("GET", "/portfolio/positions", params=params)
        
        positions = []
        for item in data.get("market_positions", []):
            # Calculate totals from yes/no positions
            yes_qty = item.get("position", 0)
            market_exposure = item.get("market_exposure", 0)
            
            if yes_qty != 0:
                positions.append(KalshiPosition(
                    ticker=item.get("ticker", ""),
                    market_title=item.get("market_title", ""),
                    side="yes" if yes_qty > 0 else "no",
                    quantity=abs(yes_qty),
                    average_price=0,  # Would need to calculate from fills
                    market_value=market_exposure,
                    pnl=item.get("realized_pnl", 0)
                ))
        
        return positions
    
    def get_orders(
        self,
        ticker: Optional[str] = None,
        status: str = "open"
    ) -> list[KalshiOrder]:
        """
        Get orders.
        
        Args:
            ticker: Optional filter by market
            status: "open", "filled", "cancelled", etc.
            
        Returns:
            List of orders
        """
        params = {"status": status}
        if ticker:
            params["ticker"] = ticker
            
        data = self._request("GET", "/portfolio/orders", params=params)
        
        orders = []
        for item in data.get("orders", []):
            orders.append(KalshiOrder(
                order_id=item.get("order_id", ""),
                ticker=item.get("ticker", ""),
                side=item.get("side", ""),
                type=item.get("type", "limit"),
                price=item.get("yes_price") or item.get("no_price"),
                quantity=item.get("count", 0),
                filled_quantity=item.get("filled_count", 0),
                status=item.get("status", ""),
                created_at=datetime.fromisoformat(
                    item.get("created_time", "").replace("Z", "+00:00")
                ) if item.get("created_time") else datetime.now()
            ))
        
        return orders
    
    # ============ TRADING ============
    
    def place_order(
        self,
        ticker: str,
        side: Literal["yes", "no"],
        quantity: int,
        price: Optional[int] = None,
        order_type: Literal["limit", "market"] = "limit",
        expiration_ts: Optional[int] = None
    ) -> OrderResult:
        """
        Place an order on Kalshi.
        
        Args:
            ticker: Market ticker (e.g., "KXBTC-25FEB01-B100000")
            side: "yes" or "no"
            quantity: Number of contracts
            price: Price in cents (1-99). Required for limit orders.
            order_type: "limit" or "market"
            expiration_ts: Unix timestamp when order expires (optional)
            
        Returns:
            OrderResult with success status and order details
        """
        if order_type == "limit" and price is None:
            return OrderResult(
                success=False,
                order_id=None,
                filled_quantity=0,
                average_price=None,
                error="Price required for limit orders"
            )
        
        body = {
            "ticker": ticker,
            "action": "buy",
            "side": side,
            "count": quantity,
            "type": order_type
        }
        
        if price is not None:
            body["yes_price" if side == "yes" else "no_price"] = price
            
        if expiration_ts:
            body["expiration_ts"] = expiration_ts
        
        try:
            data = self._request("POST", "/portfolio/orders", json_body=body)
            order = data.get("order", {})
            
            return OrderResult(
                success=True,
                order_id=order.get("order_id"),
                filled_quantity=order.get("filled_count", 0),
                average_price=order.get("average_fill_price")
            )
        except Exception as e:
            return OrderResult(
                success=False,
                order_id=None,
                filled_quantity=0,
                average_price=None,
                error=str(e)
            )
    
    def cancel_order(self, order_id: str) -> bool:
        """
        Cancel an open order.
        
        Args:
            order_id: The order ID to cancel
            
        Returns:
            True if cancelled successfully
        """
        try:
            self._request("DELETE", f"/portfolio/orders/{order_id}")
            return True
        except Exception as e:
            print(f"Failed to cancel order {order_id}: {e}")
            return False
    
    def cancel_all_orders(self, ticker: Optional[str] = None) -> int:
        """
        Cancel all open orders, optionally for a specific market.
        
        Args:
            ticker: Optional market ticker to filter
            
        Returns:
            Number of orders cancelled
        """
        orders = self.get_orders(ticker=ticker, status="open")
        cancelled = 0
        
        for order in orders:
            if self.cancel_order(order.order_id):
                cancelled += 1
                
        return cancelled
    
    def sell_position(
        self,
        ticker: str,
        side: Literal["yes", "no"],
        quantity: int,
        price: Optional[int] = None
    ) -> OrderResult:
        """
        Sell (close) a position.
        
        Args:
            ticker: Market ticker
            side: Side of position to sell ("yes" or "no")
            quantity: Number of contracts to sell
            price: Limit price in cents, or None for market order
            
        Returns:
            OrderResult
        """
        body = {
            "ticker": ticker,
            "action": "sell",
            "side": side,
            "count": quantity,
            "type": "limit" if price else "market"
        }
        
        if price:
            body["yes_price" if side == "yes" else "no_price"] = price
        
        try:
            data = self._request("POST", "/portfolio/orders", json_body=body)
            order = data.get("order", {})
            
            return OrderResult(
                success=True,
                order_id=order.get("order_id"),
                filled_quantity=order.get("filled_count", 0),
                average_price=order.get("average_fill_price")
            )
        except Exception as e:
            return OrderResult(
                success=False,
                order_id=None,
                filled_quantity=0,
                average_price=None,
                error=str(e)
            )


# ============ AGENTWALLET INTEGRATION ============

@dataclass
class TradeProposal:
    """A proposed trade that needs approval"""
    proposal_id: str
    ticker: str
    market_title: str
    side: str
    quantity: int
    price: int
    estimated_cost: float  # in dollars
    signal_strength: str  # "STRONG", "MODERATE", "WEAK"
    reasoning: str
    created_at: datetime
    status: str = "pending"  # "pending", "approved", "rejected", "executed"


class AgentWalletKalshiTrader:
    """
    Integrates Kalshi trading with AgentWallet guardrails.
    
    This is the main class for the Predictor Agent to use.
    It enforces spend limits, requires approvals, and logs everything.
    
    Usage:
        trader = AgentWalletKalshiTrader(
            kalshi_client=KalshiTradingClient(...),
            agentwallet_url="https://your-agentwallet-api.com",
            wallet_id="your-wallet-id",
            agent_api_key="your-agent-key"
        )
        
        # Propose a trade (goes through rules engine)
        result = trader.propose_trade(
            ticker="KXBTC-25FEB01-B100000",
            side="yes",
            quantity=10,
            price=45,
            signal_strength="STRONG",
            reasoning="BTC momentum indicator positive"
        )
        
        # If auto-approved, it executes. If not, awaits human approval.
    """
    
    def __init__(
        self,
        kalshi_client: KalshiTradingClient,
        agentwallet_url: str,
        wallet_id: str,
        agent_api_key: str
    ):
        self.kalshi = kalshi_client
        self.aw_url = agentwallet_url.rstrip("/")
        self.wallet_id = wallet_id
        self.agent_api_key = agent_api_key
        self.session = requests.Session()
        self.session.headers["Authorization"] = f"Bearer {agent_api_key}"
        
    def _aw_request(self, method: str, endpoint: str, json_body: dict = None) -> dict:
        """Make request to AgentWallet API."""
        url = f"{self.aw_url}{endpoint}"
        response = self.session.request(method, url, json=json_body)
        
        if not response.ok:
            raise Exception(f"AgentWallet API error: {response.status_code} {response.text}")
            
        return response.json()
    
    def check_balance(self) -> dict:
        """Get both Kalshi and AgentWallet balances."""
        kalshi_balance = self.kalshi.get_balance()
        
        # Get AgentWallet balance
        aw_data = self._aw_request("GET", f"/api/wallets/{self.wallet_id}")
        aw_balance = float(aw_data.get("wallet", {}).get("balance", 0))
        
        return {
            "kalshi": asdict(kalshi_balance),
            "agentwallet": {
                "balance": aw_balance,
                "wallet_id": self.wallet_id
            },
            "effective_limit": min(kalshi_balance.available_balance, aw_balance)
        }
    
    def propose_trade(
        self,
        ticker: str,
        side: Literal["yes", "no"],
        quantity: int,
        price: int,
        signal_strength: str = "MODERATE",
        reasoning: str = ""
    ) -> dict:
        """
        Propose a trade through AgentWallet's rules engine.
        
        The trade will be:
        1. Evaluated against spend rules
        2. If approved → executed immediately on Kalshi
        3. If requires approval → held for human review
        4. If rejected → returned with explanation
        
        Returns:
            Dict with status and details
        """
        # Calculate cost (price is in cents, quantity is contracts)
        # Max loss on a YES position at price P is: quantity * price (if settles NO)
        # Max loss on a NO position at price P is: quantity * (100 - price) (if settles YES)
        if side == "yes":
            estimated_cost = (quantity * price) / 100  # Convert to dollars
        else:
            estimated_cost = (quantity * (100 - price)) / 100
        
        # Submit to AgentWallet as a transaction request
        tx_request = {
            "walletId": self.wallet_id,
            "amount": estimated_cost,
            "category": "trading",
            "recipientId": f"kalshi:{ticker}",
            "description": f"Trade: {side.upper()} {quantity}x {ticker} @ {price}¢",
            "metadata": {
                "platform": "kalshi",
                "ticker": ticker,
                "side": side,
                "quantity": quantity,
                "price": price,
                "signal_strength": signal_strength,
                "reasoning": reasoning
            }
        }
        
        try:
            result = self._aw_request("POST", "/api/transactions", json_body=tx_request)
            
            tx = result.get("transaction", {})
            status = tx.get("status")
            rule_eval = result.get("ruleEvaluation", {})
            
            if status == "COMPLETED" or status == "APPROVED":
                # Rules passed - execute on Kalshi
                order_result = self.kalshi.place_order(
                    ticker=ticker,
                    side=side,
                    quantity=quantity,
                    price=price
                )
                
                return {
                    "status": "executed",
                    "agentwallet_tx_id": tx.get("id"),
                    "kalshi_order": asdict(order_result),
                    "rules_passed": True,
                    "rule_evaluation": rule_eval
                }
                
            elif status == "AWAITING_APPROVAL":
                # Needs human approval
                return {
                    "status": "pending_approval",
                    "agentwallet_tx_id": tx.get("id"),
                    "message": "Trade requires human approval",
                    "rules_passed": True,
                    "requires_approval_reason": [
                        r for r in rule_eval.get("results", [])
                        if r.get("requiresApproval")
                    ],
                    "approve_url": f"{self.aw_url}/dashboard/transactions/{tx.get('id')}"
                }
                
            else:
                # Rejected by rules
                failed_rules = [
                    r for r in rule_eval.get("results", [])
                    if not r.get("passed")
                ]
                
                return {
                    "status": "rejected",
                    "agentwallet_tx_id": tx.get("id"),
                    "message": "Trade blocked by spend rules",
                    "rules_passed": False,
                    "failed_rules": failed_rules,
                    "rule_evaluation": rule_eval
                }
                
        except Exception as e:
            return {
                "status": "error",
                "message": str(e),
                "rules_passed": None
            }
    
    def execute_approved_trade(self, tx_id: str) -> dict:
        """
        Execute a trade that was previously approved.
        Called after human approves via dashboard.
        
        Args:
            tx_id: AgentWallet transaction ID
            
        Returns:
            Execution result
        """
        # Get transaction details
        tx_data = self._aw_request("GET", f"/api/transactions/{tx_id}")
        tx = tx_data.get("transaction", {})
        
        if tx.get("status") != "APPROVED":
            return {
                "status": "error",
                "message": f"Transaction not approved, status: {tx.get('status')}"
            }
        
        metadata = tx.get("metadata", {})
        
        # Execute on Kalshi
        order_result = self.kalshi.place_order(
            ticker=metadata.get("ticker"),
            side=metadata.get("side"),
            quantity=metadata.get("quantity"),
            price=metadata.get("price")
        )
        
        return {
            "status": "executed" if order_result.success else "failed",
            "agentwallet_tx_id": tx_id,
            "kalshi_order": asdict(order_result)
        }
    
    def emergency_stop(self) -> dict:
        """
        Emergency stop - cancel all Kalshi orders and freeze AgentWallet.
        
        Returns:
            Summary of actions taken
        """
        results = {
            "kalshi_orders_cancelled": 0,
            "wallet_frozen": False,
            "errors": []
        }
        
        # Cancel all Kalshi orders
        try:
            results["kalshi_orders_cancelled"] = self.kalshi.cancel_all_orders()
        except Exception as e:
            results["errors"].append(f"Failed to cancel Kalshi orders: {e}")
        
        # Freeze AgentWallet (would need endpoint added)
        # For now, just log
        print("🛑 EMERGENCY STOP TRIGGERED")
        print(f"   Cancelled {results['kalshi_orders_cancelled']} Kalshi orders")
        
        return results


# ============ CLI FOR TESTING ============

if __name__ == "__main__":
    import argparse
    from rich import print as rprint
    from rich.table import Table
    from rich.console import Console
    
    console = Console()
    
    parser = argparse.ArgumentParser(description="Kalshi Trading CLI")
    parser.add_argument("--env", choices=["demo", "prod"], default="demo",
                       help="Environment (default: demo)")
    parser.add_argument("command", choices=["balance", "positions", "orders", "markets"],
                       help="Command to run")
    
    args = parser.parse_args()
    
    # Initialize client
    client = KalshiTradingClient(environment=args.env)
    
    if args.command == "balance":
        try:
            balance = client.get_balance()
            console.print(f"\n💰 [bold green]Kalshi Balance ({args.env.upper()})[/]")
            console.print(f"   Total:     ${balance.balance:.2f}")
            console.print(f"   Available: ${balance.available_balance:.2f}\n")
        except Exception as e:
            console.print(f"[red]Error: {e}[/]")
            console.print("Make sure KALSHI_API_KEY_ID and KALSHI_PRIVATE_KEY_PATH are set")
            
    elif args.command == "positions":
        try:
            positions = client.get_positions()
            if not positions:
                console.print("\n📊 No open positions\n")
            else:
                table = Table(title="Open Positions")
                table.add_column("Ticker", style="cyan")
                table.add_column("Side", style="green")
                table.add_column("Qty", style="yellow")
                table.add_column("P&L", style="magenta")
                
                for p in positions:
                    table.add_row(
                        p.ticker[:30],
                        p.side.upper(),
                        str(p.quantity),
                        f"${p.pnl/100:.2f}"
                    )
                rprint(table)
        except Exception as e:
            console.print(f"[red]Error: {e}[/]")
            
    elif args.command == "orders":
        try:
            orders = client.get_orders(status="open")
            if not orders:
                console.print("\n📋 No open orders\n")
            else:
                table = Table(title="Open Orders")
                table.add_column("Order ID", style="cyan")
                table.add_column("Ticker", style="green")
                table.add_column("Side", style="yellow")
                table.add_column("Price", style="magenta")
                table.add_column("Qty", style="blue")
                
                for o in orders:
                    table.add_row(
                        o.order_id[:12],
                        o.ticker[:25],
                        o.side.upper(),
                        f"{o.price}¢" if o.price else "MKT",
                        f"{o.filled_quantity}/{o.quantity}"
                    )
                rprint(table)
        except Exception as e:
            console.print(f"[red]Error: {e}[/]")
            
    elif args.command == "markets":
        # Use public endpoint - no auth needed
        from kalshi import KalshiClient
        
        public_client = KalshiClient()
        markets, _ = public_client.get_markets(status="open", limit=10)
        
        table = Table(title="Top 10 Open Markets")
        table.add_column("Ticker", style="cyan")
        table.add_column("Title", style="green")
        table.add_column("Yes", style="yellow")
        table.add_column("Volume", style="blue")
        
        for m in sorted(markets, key=lambda x: x.volume, reverse=True)[:10]:
            table.add_row(
                m.ticker[:25],
                m.title[:35],
                f"{m.yes_price}¢",
                f"{m.volume:,}"
            )
        rprint(table)
