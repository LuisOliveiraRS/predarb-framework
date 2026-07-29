from fastapi import APIRouter

from app.market.statistics import statistics

from app.repositories.market_repository import market_repository

router = APIRouter(
    prefix="/statistics",
    tags=["Statistics"]
)


@router.get("/")
async def summary():

    return statistics.summary(

        market_repository.all()

    )