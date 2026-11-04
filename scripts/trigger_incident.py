#!/usr/bin/env python3
"""
Simulate an APM / Sentry / Datadog alert webhook.
Sends a payload to a running SwitchOps web instance or invokes local engine.
Usage: python scripts/trigger_incident.py
"""

import sys
import requests


def trigger(target_url="http://localhost:5000/api/incident/trigger"):
    payload = {
        "alert": {
            "id": "INC-7842",
            "title": "Uncaught KeyError: 'eur' in payments_service.convert_currency",
            "service": "payments-service",
            "severity": "CRITICAL",
            "error_type": "KeyError",
            "error_message": "KeyError: 'eur' in convert_currency",
            "stack_trace": """Traceback (most recent call last):
  File "switchops/sample_apps/payments_service/app.py", line 78, in process_checkout
    final_amount = self.convert_currency(subtotal_usd, "USD", raw_currency)
  File "switchops/sample_apps/payments_service/app.py", line 37, in convert_currency
    to_rate = EXCHANGE_RATES[to_currency]
KeyError: 'eur'""",
            "metadata": {
                "datacenter": "us-east-1",
                "impacted_traffic_percent": 18.5,
                "environment": "production"
            }
        }
    }

    try:
        resp = requests.post(target_url, json=payload, timeout=5)
        print(f"Status Code: {resp.status_code}")
        print("Response:", resp.json())
    except Exception as e:
        print(f"Failed to post to {target_url}: {e}")
        print("Ensure SwitchOps web server is running (python -m switchops.web.app).")


if __name__ == "__main__":
    trigger()
