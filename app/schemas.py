from pydantic import BaseModel
from typing import List, Optional
from datetime import datetime

# --- Auth ---
class UserCreate(BaseModel):
    username: str
    password: str
    role: str

class Token(BaseModel):
    access_token: str
    token_type: str

class UserResponse(BaseModel):
    id: int
    username: str
    role: str
    
    class Config:
        from_attributes = True

# --- Floor & Table ---
class TableBase(BaseModel):
    table_number: str
    capacity: int

class TableCreate(TableBase):
    floor_id: int

class TableUpdate(BaseModel):
    table_number: Optional[str] = None
    capacity: Optional[int] = None
    floor_id: Optional[int] = None

class TableResponse(TableBase):
    id: int
    floor_id: int
    
    class Config:
        from_attributes = True

class FloorCreate(BaseModel):
    name: str

class FloorUpdate(BaseModel):
    name: Optional[str] = None

class FloorResponse(BaseModel):
    id: int
    name: str
    tables: List[TableResponse] = []
    
    class Config:
        from_attributes = True

# --- Menu ---
class CategoryCreate(BaseModel):
    name: str

class CategoryUpdate(BaseModel):
    name: Optional[str] = None

class CategoryResponse(BaseModel):
    id: int
    name: str
    
    class Config:
        from_attributes = True

class MenuItemBase(BaseModel):
    name: str
    price: float
    category_id: int
    is_available: bool = True

class MenuItemCreate(MenuItemBase):
    pass

class MenuItemUpdate(BaseModel):
    name: Optional[str] = None
    price: Optional[float] = None
    category_id: Optional[int] = None
    is_available: Optional[bool] = None

class MenuItemResponse(MenuItemBase):
    id: int
    
    class Config:
        from_attributes = True

class ItemRequestCreate(BaseModel):
    item_name: str
    description: str

class ItemRequestResponse(BaseModel):
    id: int
    requested_by_id: int
    item_name: str
    description: str
    request_count: int
    
    class Config:
        from_attributes = True

# --- Reservation ---
class ReservationCreate(BaseModel):
    table_id: int
    customer_name: str
    start_time: datetime
    end_time: datetime

class ReservationResponse(ReservationCreate):
    id: int
    
    class Config:
        from_attributes = True

# --- Order ---
class OrderItemCreate(BaseModel):
    menu_item_id: int
    quantity: int

class OrderItemResponse(BaseModel):
    id: int
    menu_item_id: int
    quantity: int
    
    class Config:
        from_attributes = True

class OrderCreate(BaseModel):
    table_id: int
    items: List[OrderItemCreate]

class OrderStatusUpdate(BaseModel):
    status: str  # pending, completed, cancelled

class OrderResponse(BaseModel):
    id: int
    table_id: int
    staff_id: Optional[int]
    status: str
    created_at: datetime
    items: List[OrderItemResponse] = []
    
    class Config:
        from_attributes = True
