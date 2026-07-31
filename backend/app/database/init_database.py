from app.database.database import engine
from app.database.session import Base

# Importa todos os modelos para que sejam registrados no metadata
from app.database.models import (
    MarketModel,
    OrderModel,
    TradeModel,
    PositionModel,
    RealMarketObservationModel,
)


def initialize_database():
    """
    Cria todas as tabelas do banco caso ainda não existam.
    """
    Base.metadata.create_all(bind=engine)
