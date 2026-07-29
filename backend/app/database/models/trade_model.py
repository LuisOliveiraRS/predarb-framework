from sqlalchemy import Column
from sqlalchemy import Float
from sqlalchemy import Integer
from sqlalchemy import String

from app.database.session import Base


class TradeModel(Base):

    __tablename__ = "trades"

    id = Column(Integer, primary_key=True)

    platform = Column(String(50))

    pnl = Column(Float)

    roi = Column(Float)