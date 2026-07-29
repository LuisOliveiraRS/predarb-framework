from sqlalchemy import Column
from sqlalchemy import Float
from sqlalchemy import Integer
from sqlalchemy import String

from app.database.session import Base


class MarketModel(Base):

    __tablename__ = "markets"

    id = Column(Integer, primary_key=True)

    platform = Column(String(50))

    question = Column(String(500))

    yes = Column(Float)

    no = Column(Float)