"""
Tests for restock / restocking API endpoints and demand forecast unit cost.
"""
import pytest


class TestDemandUnitCost:
    """Demand forecasts must expose a unit_cost for restock cost calculations."""

    def test_demand_includes_unit_cost(self, client):
        """Every demand forecast has a numeric, non-negative unit_cost."""
        response = client.get("/api/demand")
        assert response.status_code == 200

        data = response.json()
        assert isinstance(data, list)
        assert len(data) > 0

        for forecast in data:
            assert "unit_cost" in forecast
            assert isinstance(forecast["unit_cost"], (int, float))
            assert forecast["unit_cost"] >= 0


class TestRestockOrderEndpoint:
    """Test suite for POST /api/restock/orders."""

    def _payload(self):
        return {
            "items": [
                {"sku": "WDG-001", "name": "Industrial Widget Type A",
                 "quantity": 450, "unit_price": 85.0},
                {"sku": "GSK-203", "name": "High-Temperature Gasket",
                 "quantity": 600, "unit_price": 9.5}
            ],
            "total_value": 450 * 85.0 + 600 * 9.5,
            "budget": 50000
        }

    def test_create_restock_order(self, client):
        """Submitting a restock order returns a Submitted order with lead time."""
        payload = self._payload()
        response = client.post("/api/restock/orders", json=payload)
        assert response.status_code == 200

        order = response.json()
        assert order["status"] == "Submitted"
        assert order["order_number"].startswith("RST-")
        assert order["customer"] == "Internal Restock"
        assert order["lead_time_days"] == 14
        assert abs(order["total_value"] - payload["total_value"]) < 0.01
        assert len(order["items"]) == 2

        # order item structure preserved
        for item in order["items"]:
            assert set(["sku", "name", "quantity", "unit_price"]).issubset(item.keys())

    def test_expected_delivery_matches_lead_time(self, client):
        """expected_delivery is order_date + lead_time_days."""
        from datetime import datetime

        response = client.post("/api/restock/orders", json=self._payload())
        assert response.status_code == 200
        order = response.json()

        order_date = datetime.fromisoformat(order["order_date"])
        expected = datetime.fromisoformat(order["expected_delivery"])
        delta_days = (expected - order_date).days
        assert delta_days == order["lead_time_days"] == 14

    def test_submitted_order_appears_in_orders(self, client):
        """A submitted restock order shows up in GET /api/orders."""
        response = client.post("/api/restock/orders", json=self._payload())
        assert response.status_code == 200
        created = response.json()

        orders_response = client.get("/api/orders")
        assert orders_response.status_code == 200
        all_orders = orders_response.json()

        match = next((o for o in all_orders if o["order_number"] == created["order_number"]), None)
        assert match is not None
        assert match["status"] == "Submitted"
        assert match["lead_time_days"] == 14

    def test_empty_items_rejected(self, client):
        """An order with no items is rejected with 400."""
        response = client.post("/api/restock/orders",
                               json={"items": [], "total_value": 0})
        assert response.status_code == 400
        assert "detail" in response.json()

    def test_missing_required_fields_returns_422(self, client):
        """Malformed payload fails Pydantic validation."""
        response = client.post("/api/restock/orders", json={"budget": 1000})
        assert response.status_code == 422
