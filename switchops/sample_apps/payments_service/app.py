"""
Payments Service Microservice
Demonstration service with realistic checkout operations, currency conversion, and discount engine.
"""

import logging
from typing import Dict, Any, Optional

logger = logging.getLogger("payments_service")

# Static exchange rates against USD
EXCHANGE_RATES = {
    "USD": 1.0,
    "EUR": 0.92,
    "GBP": 0.79,
    "CAD": 1.36,
    "JPY": 154.5,
    "INR": 83.2,
}

SUPPORTED_PAYMENT_METHODS = ["credit_card", "debit_card", "paypal", "apple_pay", "crypto"]


class PaymentProcessingError(Exception):
    """Raised when payment fails."""
    pass


class PaymentsService:
    def __init__(self, default_currency: str = "USD"):
        self.default_currency = default_currency
        self.transactions = []

    def convert_currency(self, amount: float, from_currency: str, to_currency: str) -> float:
        """
        Converts an amount from one currency to another using exchange rates.
        
        NOTE: Bug here in v1.0.0! If a currency key is lowercase or not found,
        it does a raw dict lookup without normalization or fallback, triggering KeyError.
        """
        # Normalized lookup with uppercase safety fallback in v1.0.1 (Auto-remediated by SwitchOps)
        clean_from = str(from_currency).upper().strip()
        clean_to = str(to_currency).upper().strip()

        if clean_from not in EXCHANGE_RATES:
            raise PaymentProcessingError(f"Unsupported source currency: {from_currency}")
        if clean_to not in EXCHANGE_RATES:
            raise PaymentProcessingError(f"Unsupported target currency: {to_currency}")

        from_rate = EXCHANGE_RATES[clean_from]
        to_rate = EXCHANGE_RATES[clean_to]
        
        # Convert to USD base first, then to target
        amount_in_usd = amount / from_rate
        return round(amount_in_usd * to_rate, 2)

    def calculate_total(self, items: list, discount_code: Optional[str] = None, tax_rate: float = 0.08) -> float:
        """Calculates subtotal, discounts, and taxes."""
        subtotal = sum(item.get("price", 0.0) * item.get("quantity", 1) for item in items)
        
        discount = 0.0
        if discount_code == "SWITCH2026":
            discount = subtotal * 0.20  # 20% discount
        elif discount_code == "WELCOME10":
            discount = subtotal * 0.10

        taxable = max(0.0, subtotal - discount)
        total = taxable * (1.0 + tax_rate)
        return round(total, 2)

    def process_checkout(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """
        Processes a full customer checkout transaction.
        Expects payload with:
          - order_id: str
          - items: list[dict]
          - currency: str (e.g. 'USD', 'EUR', 'eur', 'GBP')
          - payment_method: str
          - discount_code: optional str
        """
        order_id = payload.get("order_id")
        if not order_id:
            raise PaymentProcessingError("Missing mandatory 'order_id'")

        items = payload.get("items", [])
        if not items:
            raise PaymentProcessingError("Cannot process checkout with empty cart")

        raw_currency = payload.get("currency", self.default_currency)
        payment_method = payload.get("payment_method")

        if payment_method not in SUPPORTED_PAYMENT_METHODS:
            raise PaymentProcessingError(f"Unsupported payment method: {payment_method}")

        subtotal_usd = self.calculate_total(items, payload.get("discount_code"))

        # In production v1.0.0, passing lowercase 'eur' or 'gbp' causes KeyError: 'eur'
        final_amount = self.convert_currency(subtotal_usd, "USD", raw_currency)

        txn = {
            "transaction_id": f"txn_{len(self.transactions) + 1000}",
            "order_id": order_id,
            "amount": final_amount,
            "currency": raw_currency,
            "status": "SETTLED",
            "items_count": len(items),
        }
        self.transactions.append(txn)
        return txn
