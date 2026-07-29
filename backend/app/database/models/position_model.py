from sqlalchemy import Column
from sqlalchemy import Float
from sqlalchemy import Integer
from sqlalchemy import String

from app.database.session import Base


class PositionModel(Base):

    __tablename__ = "positions"

    id = Column(Integer, primary_key=True)

    platform = Column(String(50))

    quantity = Column(Float)

    average_price = Column(Float)