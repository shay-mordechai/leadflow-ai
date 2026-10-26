# src/scripts/simulate_incoming_lead.py
# Professional English Comment:
# E2E Simulation Script for LeadFlow AI.
# Sends a POST request to the local marketing webhook simulating an incoming bridal lead from a campaign.

import argparse

import requests


def simulate_lead(
    webhook_url: str = "http://localhost:8000/webhooks/marketing/incoming-lead",
    marketing_api_key: str = "mk_live_bridal_test_key_abc123",
):
    """
    Sends a test payload simulating an incoming bridal lead to the local FastAPI webhook.
    """
    payload = {
        "name": "מיכל",
        "phone_number": "+972544444444",
        "campaign_name": "Bridal Makeup Campaign",
        "custom_fields": {
            "wedding_date": "2026-10-15",
            "location": "Tel Aviv",
        },
    }

    headers = {
        "Content-Type": "application/json",
        "X-Marketing-Api-Key": marketing_api_key,
    }

    print(f"🚀 Sending simulation request to webhook: {webhook_url}")
    print(f"📦 Payload: {payload}")

    try:
        response = requests.post(webhook_url, json=payload, headers=headers, timeout=10)
        print(f"\n📡 Response Status Code: {response.status_code}")
        print(f"📄 Response Body:\n{response.json()}")

        if response.status_code == 201:
            print("\n✅ Success! Lead successfully ingested and routed.")
        else:
            print("\n⚠️ Webhook returned non-201 status.")
    except requests.exceptions.ConnectionError:
        print(
            "\n❌ Error: Could not connect to the local server. Is FastAPI running on http://localhost:8000?"
        )
    except Exception as e:
        print(f"\n❌ Error during simulation: {e}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Simulate Incoming Bridal Lead")
    parser.add_argument(
        "--webhook-url", default="http://localhost:8000/webhooks/marketing/incoming-lead"
    )
    parser.add_argument("--api-key", default="mk_live_bridal_test_key_abc123")
    args = parser.parse_args()

    simulate_lead(webhook_url=args.webhook_url, marketing_api_key=args.api_key)
