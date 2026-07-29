from fastapi import APIRouter

from app.engine.arbitrage_engine import arbitrage_engine


router = APIRouter(

    prefix="/arbitrage",

    tags=["Arbitrage"]

)


@router.get("/")

async def opportunities():

    return arbitrage_engine.scan()