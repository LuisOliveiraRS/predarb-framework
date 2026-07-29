from fastapi import APIRouter

from app.repositories.market_repository import market_repository


router = APIRouter(
    prefix="/markets",
    tags=["Markets"]
)


@router.get("/")
async def list_markets():

    return market_repository.all()