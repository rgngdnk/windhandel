"""
Domain/service layer for windhandel.
"""

from __future__ import annotations

from datetime import date, datetime, timedelta
from typing import Any, Callable, Dict, List, Optional

from pydantic import BaseModel

from windhandel.db import (
    DB_HOST,
    DB_NAME,
    DB_PASSWORD,
    DB_PORT,
    DB_USER,
    PostgresWrapper,
)

class WindhandelError(Exception):
    """Base class for every domain error raised by this layer."""


class FutureSnapshotDate(WindhandelError):
    """A snapshot was requested for today or later."""

    def __init__(self, requested: date, latest_allowed: date) -> None:
        self.requested = requested
        self.latest_allowed = latest_allowed
        super().__init__(
            f"Snapshot date {requested.isoformat()} is greater than the latest allowed."
            f"Latest allowed date is {latest_allowed.isoformat()}."
        )


class DataSourceUnavailable(WindhandelError):
    """The database call failed — distinct from 'the query returned nothing'."""

    def __init__(self, operation: str) -> None:
        self.operation = operation
        super().__init__(f"Database call failed: {operation}")


# --------------------------------------------------------------------------
# Models
# --------------------------------------------------------------------------


class SnapshotRow(BaseModel):
    """One row of public.portfolio_snapshots"""

    id: int
    snapshot_date: date
    pocket: Optional[str] = None
    symbol: str
    price_date: date
    quantity: Optional[float] = None
    price: Optional[float] = None
    cash_value: Optional[float] = None
    mark_to_market: Optional[float] = None
    pnl: Optional[float] = None
    pct_portfolio: Optional[float] = None
    pct_pocket: Optional[float] = None
    created_at: Optional[datetime] = None


class PortfolioTotals(BaseModel):
    """Totals for one snapshot date, summed in Python over rows already fetched"""

    row_count: int = 0
    mark_to_market: float = 0.0
    pnl: float = 0.0
    cash_value: float = 0.0


class PortfolioView(BaseModel):
    """A portfolio as of one snapshot date.

    `exists=False` is a normal, expected state — it is the signal the TUI uses
    to offer the populate workflow. It is not an error.
    """

    snapshot_date: Optional[date] = None
    exists: bool = False
    totals: PortfolioTotals = PortfolioTotals()
    rows: List[SnapshotRow] = []

# --------------------------------------------------------------------------
# Service
# --------------------------------------------------------------------------


class PortfolioService:
    """Portfolio read operations.

    Takes its collaborators by injection so it can be exercised in tests with
    a stub wrapper and a frozen clock, with no Postgres anywhere in sight.
    """

    def __init__(
        self,
        db: PostgresWrapper,
        today: Callable[[], date] = date.today,
    ) -> None:
        self._db = db
        self._today = today

    # -- public API --------------------------------------------------------

    def ping(self) -> None:
        """Real round-trip to Postgres. Raises if the DB is unreachable."""
        result = self._db.gen_fetch("assets", select=["id"])
        if result is None:
            raise DataSourceUnavailable("ping")

    def portfolio_on(self, target: date) -> PortfolioView:
        """Portfolio for an exact snapshot date.

        Exact match, never nearest-preceding: a date with no snapshot must come
        back empty rather than silently serving stale data from another day.
        """
        self._reject_future(target)
        rows = self._snapshot_rows("get_snapshot_on", {"p_date": target})
        return self._build_view(target, rows)

    def latest_portfolio(self) -> PortfolioView:
        rows = self._snapshot_rows("get_latest_snapshot", None)
        snapshot_date = rows[0].snapshot_date if rows else None
        return self._build_view(snapshot_date, rows)

    # -- internals ---------------------------------------------------------

    def _reject_future(self, target: date) -> None:
        today = self._today()
        if target >= today:
            raise FutureSnapshotDate(target, today - timedelta(days=1))

    def _snapshot_rows(
        self,
        func_name: str,
        params: Optional[Dict[str, Any]],
    ) -> List[SnapshotRow]:
        raw = self._db.call_function(func_name, params=params)
        # db.py returns None on failure and [] on an empty result set. That
        # distinction is load-bearing here: None must not be read as "this date
        # has no snapshot, offer to populate it".
        if raw is None:
            raise DataSourceUnavailable(func_name)
        return [SnapshotRow.model_validate(row) for row in raw]

    @staticmethod
    def _build_view(
        snapshot_date: Optional[date],
        rows: List[SnapshotRow],
    ) -> PortfolioView:
        return PortfolioView(
            snapshot_date=snapshot_date,
            exists=bool(rows),
            totals=PortfolioTotals(
                row_count=len(rows),
                mark_to_market=sum(r.mark_to_market or 0.0 for r in rows),
                pnl=sum(r.pnl or 0.0 for r in rows),
                cash_value=sum(r.cash_value or 0.0 for r in rows),
            ),
            rows=rows,
        )


def build_default_service() -> PortfolioService:
    """Wire a service from environment config.

    Exists so api.py never has to import PostgresWrapper or the DB_* settings.
    """
    return PortfolioService(
        PostgresWrapper(
            host=DB_HOST,
            port=DB_PORT,
            dbname=DB_NAME,
            user=DB_USER,
            password=DB_PASSWORD,
        )
    )