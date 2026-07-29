from fastapi import APIRouter

from app.engine.arbitrage_engine import arbitrage_engine


router = APIRouter(
    prefix="/signals",
    tags=["Signals"]
)


@router.get("/")
async def list_signals():

    return arbitrage_engine.scan()