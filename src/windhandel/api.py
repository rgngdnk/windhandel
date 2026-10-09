from datetime import date

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from windhandel.config import configure_logging
from windhandel.service import (
    DataSourceUnavailable,
    FutureSnapshotDate,
    PortfolioView,
    build_default_service,
)


configure_logging("api")

app = FastAPI(title="windhandel")
service = build_default_service()


# --------------------------------------------------------------------------
# This is the only place in the codebase that knows a future date is a 422.
# service.py raises meaning; api.py assigns it a status code.
# --------------------------------------------------------------------------


@app.exception_handler(FutureSnapshotDate)
async def handle_future_date(request: Request, exc: FutureSnapshotDate) -> JSONResponse:
    return JSONResponse(
        status_code=422,
        content={
            "detail": str(exc),
            "requested": exc.requested.isoformat(),
            "latest_allowed": exc.latest_allowed.isoformat(),
        },
    )


@app.exception_handler(DataSourceUnavailable)
async def handle_unavailable(request: Request, exc: DataSourceUnavailable) -> JSONResponse:
    return JSONResponse(status_code=503, content={"detail": str(exc)})


# --------------------------------------------------------------------------
# Routes
# --------------------------------------------------------------------------


@app.get("/health")
def health() -> dict:
    service.ping()
    return {"status": "ok"}

# NOTE: this must stay declared ABOVE /snapshots/{snapshot_date}. FastAPI
@app.get("/snapshots/latest", response_model=PortfolioView)
def latest_snapshot() -> PortfolioView:
    return service.latest_portfolio()

@app.get("/snapshots/{snapshot_date}", response_model=PortfolioView)
def snapshot_on(snapshot_date: date) -> PortfolioView:
    return service.portfolio_on(snapshot_date)