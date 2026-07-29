from sqlalchemy import Column
from sqlalchemy import Float
from sqlalchemy import Integer
from sqlalchemy import String

from app.database.session import Base


class OrderModel(Base):

    __tablename__ = "orders"

    id = Column(Integer, primary_key=True)

    platform = Column(String(50))

    side = Column(String(10))

    price = Column(Float)

    quantity = Column(Float)

    status = Column(String(30))