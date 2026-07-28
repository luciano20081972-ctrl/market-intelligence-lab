from decimal import Decimal
from uuid import uuid4

from fastapi.testclient import TestClient
from sqlalchemy import Engine, select
from sqlalchemy.orm import Session

from packages.database.models import Asset, PaperOrder, PriceBar
from packages.paper_trading.engine import PaperTradingEngine
from packages.paper_trading.service import create_portfolio


def _create_portfolio(
    client: TestClient, *, name: str | None = None, starting_cash: str = "100000"
) -> dict[str, object]:
    response = client.post(
        "/api/v1/paper-portfolios",
        json={"name": name or f"Paper {uuid4().hex[:8]}", "starting_cash": starting_cash},
    )
    assert response.status_code == 201, response.text
    return response.json()


def _order(**overrides: object) -> dict[str, object]:
    payload: dict[str, object] = {
        "client_order_id": f"order-{uuid4().hex}",
        "symbol": "AAPL",
        "side": "buy",
        "order_type": "market",
        "quantity": "10",
    }
    payload.update(overrides)
    return payload


def _set_risk_rule(client: TestClient, portfolio_id: object, rule_type: str, value: str) -> None:
    rules = client.get(f"/api/v1/paper-portfolios/{portfolio_id}/risk-rules").json()
    rule = next(item for item in rules if item["rule_type"] == rule_type)
    response = client.patch(
        f"/api/v1/paper-portfolios/{portfolio_id}/risk-rules/{rule['id']}",
        json={"limit_value": value, "is_enabled": True},
    )
    assert response.status_code == 200, response.text


def test_portfolio_market_fill_positions_and_performance(client: TestClient) -> None:
    portfolio = _create_portfolio(client)
    portfolio_id = portfolio["id"]
    response = client.post(f"/api/v1/paper-portfolios/{portfolio_id}/orders", json=_order())
    assert response.status_code == 201, response.text
    assert response.json()["status"] == "filled"

    fills = client.get(f"/api/v1/paper-portfolios/{portfolio_id}/fills").json()
    positions = client.get(f"/api/v1/paper-portfolios/{portfolio_id}/positions").json()
    performance = client.get(f"/api/v1/paper-portfolios/{portfolio_id}/performance").json()
    assert len(fills) == 1
    assert fills[0]["source_price_bar_id"]
    assert len(positions) == 1
    assert positions[0]["symbol"] == "AAPL"
    assert Decimal(positions[0]["quantity"]) == Decimal("10")
    assert Decimal(positions[0]["average_cost"]) > 0
    assert performance["points"]
    assert "Hypothetical" in performance["warning"]


def test_duplicate_client_order_id_is_idempotent(client: TestClient) -> None:
    portfolio_id = _create_portfolio(client)["id"]
    payload = _order(client_order_id="stable-order-id")
    first = client.post(f"/api/v1/paper-portfolios/{portfolio_id}/orders", json=payload).json()
    replay = client.post(f"/api/v1/paper-portfolios/{portfolio_id}/orders", json=payload).json()
    fills = client.get(f"/api/v1/paper-portfolios/{portfolio_id}/fills").json()
    assert replay["id"] == first["id"]
    assert replay["idempotent_replay"] is True
    assert len(fills) == 1


def test_limit_order_pending_preview_and_cancel(client: TestClient) -> None:
    portfolio_id = _create_portfolio(client)["id"]
    payload = _order(order_type="limit", limit_price="1")
    preview = client.post(f"/api/v1/paper-portfolios/{portfolio_id}/orders/preview", json=payload)
    assert preview.status_code == 200
    assert preview.json()["outcome"] == "pending"
    order = client.post(f"/api/v1/paper-portfolios/{portfolio_id}/orders", json=payload).json()
    assert order["status"] == "pending"
    cancelled = client.delete(f"/api/v1/paper-portfolios/{portfolio_id}/orders/{order['id']}")
    assert cancelled.status_code == 200
    assert cancelled.json()["status"] == "cancelled"


def test_limit_stop_and_stop_limit_behaviors(client: TestClient) -> None:
    portfolio_id = _create_portfolio(client)["id"]
    limit_fill = client.post(
        f"/api/v1/paper-portfolios/{portfolio_id}/orders",
        json=_order(order_type="limit", limit_price="10000"),
    ).json()
    assert limit_fill["status"] == "filled"
    limit_fill_record = client.get(f"/api/v1/paper-portfolios/{portfolio_id}/fills").json()[0]
    assert Decimal(limit_fill_record["price"]) <= Decimal("10000")

    stop_fill = client.post(
        f"/api/v1/paper-portfolios/{portfolio_id}/orders",
        json=_order(order_type="stop", stop_price="1", quantity="1"),
    ).json()
    assert stop_fill["status"] == "filled"
    assert stop_fill["is_triggered"] is True

    stop_limit = client.post(
        f"/api/v1/paper-portfolios/{portfolio_id}/orders",
        json=_order(order_type="stop_limit", stop_price="1", limit_price="1", quantity="1"),
    ).json()
    assert stop_limit["status"] == "triggered"
    assert stop_limit["is_triggered"] is True


def test_sell_updates_realized_pnl_and_prevents_shorts(client: TestClient) -> None:
    portfolio_id = _create_portfolio(client)["id"]
    buy = client.post(f"/api/v1/paper-portfolios/{portfolio_id}/orders", json=_order(quantity="10"))
    assert buy.json()["status"] == "filled"
    sell = client.post(
        f"/api/v1/paper-portfolios/{portfolio_id}/orders",
        json=_order(side="sell", quantity="4"),
    )
    assert sell.json()["status"] == "filled"
    position = client.get(f"/api/v1/paper-portfolios/{portfolio_id}/positions").json()[0]
    assert Decimal(position["quantity"]) == Decimal("6")

    short = client.post(
        f"/api/v1/paper-portfolios/{portfolio_id}/orders",
        json=_order(side="sell", quantity="7"),
    ).json()
    assert short["status"] == "rejected"
    assert "short selling is disabled" in short["rejection_reason"]


def test_pause_resume_and_risk_rejections(client: TestClient) -> None:
    portfolio_id = _create_portfolio(client)["id"]
    paused = client.post(f"/api/v1/paper-portfolios/{portfolio_id}/pause")
    assert paused.json()["status"] == "paused"
    rejected = client.post(f"/api/v1/paper-portfolios/{portfolio_id}/orders", json=_order()).json()
    assert rejected["status"] == "rejected"
    assert "paused" in rejected["rejection_reason"]

    resumed = client.post(f"/api/v1/paper-portfolios/{portfolio_id}/resume")
    assert resumed.json()["status"] == "active"
    _set_risk_rule(client, portfolio_id, "maximum_order_value", "1")
    preview = client.post(
        f"/api/v1/paper-portfolios/{portfolio_id}/orders/preview", json=_order()
    ).json()
    assert preview["outcome"] == "rejected"
    assert any("maximum order value" in reason for reason in preview["rejection_reasons"])


def test_stale_price_rule_rejects_precisely(client: TestClient) -> None:
    portfolio_id = _create_portfolio(client)["id"]
    _set_risk_rule(client, portfolio_id, "stale_price_days", "0")
    preview = client.post(
        f"/api/v1/paper-portfolios/{portfolio_id}/orders/preview", json=_order()
    ).json()
    assert preview["outcome"] == "rejected"
    assert any("stale-price limit" in reason for reason in preview["rejection_reasons"])


def test_stop_limit_transitions_from_triggered_to_filled(engine: Engine) -> None:
    with Session(engine) as session:
        asset = session.scalar(select(Asset).where(Asset.symbol == "AAPL"))
        assert asset is not None
        bars = session.scalars(
            select(PriceBar).where(PriceBar.asset_id == asset.id).order_by(PriceBar.event_time)
        ).all()
        pair = next(
            (bars[first], bars[second])
            for first in range(len(bars) - 1)
            for second in range(first + 1, len(bars))
            if bars[second].low < bars[first].low
        )
        trigger_bar, fill_bar = pair
        limit_price = (trigger_bar.low + fill_bar.low) / Decimal("2")
        portfolio = create_portfolio(
            session, name=f"Transition {uuid4().hex[:8]}", starting_cash=Decimal("100000")
        )
        order = PaperOrder(
            portfolio_id=portfolio.id,
            asset_id=asset.id,
            client_order_id=f"transition-{uuid4().hex}",
            side="buy",
            order_type="stop_limit",
            quantity=Decimal("1"),
            limit_price=limit_price,
            stop_price=Decimal("1"),
            status="pending",
            is_triggered=False,
            assumptions={},
        )
        session.add(order)
        session.flush()
        trading = PaperTradingEngine()
        trading.process_order(session, order, trigger_bar)
        assert order.status == "triggered"
        assert order.is_triggered is True
        trading.process_order(session, order, fill_bar)
        assert order.status == "filled"
        assert order.fills[0].price <= limit_price


def test_order_validation_and_portfolio_lists(client: TestClient) -> None:
    portfolio = _create_portfolio(client)
    portfolio_id = portfolio["id"]
    invalid = client.post(
        f"/api/v1/paper-portfolios/{portfolio_id}/orders",
        json=_order(order_type="limit"),
    )
    assert invalid.status_code == 422
    listing = client.get("/api/v1/paper-portfolios?page=1&page_size=1")
    assert listing.status_code == 200
    assert listing.json()[0]["id"] == portfolio_id
    rules = client.get(f"/api/v1/paper-portfolios/{portfolio_id}/risk-rules").json()
    assert len(rules) == 9
