from sqlalchemy import Column, Integer, String
from database import Base

class ProductInventory(Base):
    __tablename__ = "product_inventory"

    id = Column(Integer, primary_key=True, index=True)
    product_name = Column(String, unique=True, index=True, nullable=False)
    quantity_in_stock = Column(Integer, nullable=False)