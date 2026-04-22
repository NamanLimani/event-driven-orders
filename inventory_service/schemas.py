from pydantic import BaseModel

class InventoryCreate(BaseModel):
    product_name: str
    quantity_in_stock: int

class InventoryResponse(BaseModel):
    id: int
    product_name: str
    quantity_in_stock: int

    class Config:
        from_attributes = True