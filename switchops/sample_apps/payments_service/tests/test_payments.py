"""
Tests for payments_service.
Validates standard checkout, error handling, and currency conversion.
"""

import unittest
from switchops.sample_apps.payments_service.app import PaymentsService, PaymentProcessingError

class TestPaymentsService(unittest.TestCase):
    def setUp(self):
        self.service = PaymentsService()

    def test_standard_checkout_usd(self):
        payload = {
            "order_id": "ORD-101",
            "items": [{"name": "Laptop Stand", "price": 50.0, "quantity": 1}],
            "currency": "USD",
            "payment_method": "credit_card"
        }
        result = self.service.process_checkout(payload)
        self.assertEqual(result["status"], "SETTLED")
        self.assertEqual(result["amount"], 54.0)  # 50 + 8% tax

    def test_discount_code(self):
        payload = {
            "order_id": "ORD-102",
            "items": [{"name": "Mechanical Keyboard", "price": 100.0, "quantity": 1}],
            "currency": "USD",
            "payment_method": "apple_pay",
            "discount_code": "SWITCH2026"
        }
        result = self.service.process_checkout(payload)
        # 100 - 20% = 80; 80 * 1.08 = 86.4
        self.assertEqual(result["amount"], 86.4)

    def test_missing_order_id_raises_error(self):
        payload = {
            "items": [{"name": "Mouse", "price": 20.0, "quantity": 1}],
            "currency": "USD",
            "payment_method": "paypal"
        }
        with self.assertRaises(PaymentProcessingError):
            self.service.process_checkout(payload)

    def test_currency_conversion_eur(self):
        payload = {
            "order_id": "ORD-103",
            "items": [{"name": "Monitor", "price": 200.0, "quantity": 1}],
            "currency": "EUR",
            "payment_method": "credit_card"
        }
        result = self.service.process_checkout(payload)
        self.assertEqual(result["status"], "SETTLED")
        self.assertGreater(result["amount"], 0)

if __name__ == "__main__":
    unittest.main()
