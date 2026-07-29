from fastapi import FastAPI
from windhandel.db import PostgresWrapper, DB_HOST, DB_PORT, DB_NAME, DB_USER, DB_PASSWORD

app = FastAPI()
db = PostgresWrapper(host=DB_HOST, port=DB_PORT, dbname=DB_NAME, user=DB_USER, password=DB_PASSWORD)

@app.get("/health")
def health():
    db.gen_fetch("assets", select=["id"])
    return {"status": "ok"}

@app.get("/snapshots/latest")
def latest_snapshot():
    return db.call_function("get_latest_snapshot")

@app.get("/stats/overview")
def stats_overview():
    result = db.call_function("get_portfolio_stats")
    return result[0] if result else {}