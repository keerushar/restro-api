from pydantic import BaseModel
from typing import List, Optional
from datetime import datetime
from enum import Enum


# --- Enums ---

class OrderStatus(str, Enum):
    pending = "pending"
    completed = "completed"


class ItemStatus(str, Enum):
    ordered = "ordered"
    placed = "placed"
    cancelled = "cancelled"


class PayType(str, Enum):
    cash = "cash"
    qr = "qr"


# --- Cafe ---

class CafeAdminCreate(BaseModel):
    """Admin account to create alongside the cafe."""
    name: str
    username: str
    password: str


class CafeCreate(BaseModel):
    """Create a cafe and its admin in one request."""
    cafe_name: str
    cafe_username: str
    admin: CafeAdminCreate


class CafeResponse(BaseModel):
    id: str
    name: str
    username: str
    is_active: bool
    created_at: datetime

    class Config:
        from_attributes = True


class CafeStatusUpdate(BaseModel):
    is_active: bool


class CafeWithAdminResponse(BaseModel):
    cafe: CafeResponse
    admin: "UserResponse"


# --- Staff ---

class StaffCreate(BaseModel):
    """Create a staff account directly under the calling cafe_admin's cafe."""
    name: str
    username: str
    password: str
    is_active: bool = True


# --- Auth ---

class UserCreate(BaseModel):
    name: str
    username: str
    password: Optional[str] = None
    role: str
    is_active: bool = True
    cafe_id: Optional[str] = None


class Token(BaseModel):
    access_token: str
    token_type: str


class UserResponse(BaseModel):
    id: str
    name: str
    username: str
    role: str
    is_active: bool
    cafe_id: Optional[str] = None
    created_at: Optional[datetime] = None

    class Config:
        from_attributes = True


CafeWithAdminResponse.model_rebuild()


# --- Floor & Table ---

class TableCreate(BaseModel):
    table_number: int
    table_name: str


class TableUpdate(BaseModel):
    table_number: Optional[int] = None
    table_name: Optional[str] = None


class TableResponse(BaseModel):
    id: int
    table_number: int
    table_name: str

    class Config:
        from_attributes = True


class FloorCreate(BaseModel):
    name: str


class FloorUpdate(BaseModel):
    name: Optional[str] = None


class FloorResponse(BaseModel):
    id: int
    name: str

    class Config:
        from_attributes = True


# --- Menu ---

class MenuItemCreate(BaseModel):
    name: str
    price: float
    is_available: bool = True


class MenuItemUpdate(BaseModel):
    name: Optional[str] = None
    price: Optional[float] = None
    is_available: Optional[bool] = None


class MenuItemResponse(BaseModel):
    id: int
    name: str
    price: float
    is_available: bool

    class Config:
        from_attributes = True


# --- Item Requests ---

class ItemRequestCreate(BaseModel):
    item_name: str
    description: str


class ItemRequestResponse(BaseModel):
    id: int
    requested_by_id: str
    item_name: str
    description: str
    request_count: int

    class Config:
        from_attributes = True


# --- Reservations ---

class ReservationCreate(BaseModel):
    table_id: int
    customer_name: str
    start_time: datetime
    end_time: datetime


class ReservationResponse(ReservationCreate):
    id: int

    class Config:
        from_attributes = True


# --- Orders ---

class OrderItemCreate(BaseModel):
    menu_item_id: int
    quantity: int = 1


class OrderItemStatusUpdate(BaseModel):
    status: ItemStatus


class OrderItemResponse(BaseModel):
    id: int
    menu_item_id: Optional[int] = None
    name: str
    price: float
    quantity: int
    status: ItemStatus

    class Config:
        from_attributes = True


class OrderCreate(BaseModel):
    table_id: int
    items: List[OrderItemCreate]


class AddItemsToOrder(BaseModel):
    items: List[OrderItemCreate]


class OrderStatusUpdate(BaseModel):
    status: OrderStatus


class OrderResponse(BaseModel):
    id: int
    table_id: int
    table_number: int
    table_name: str
    staff_id: Optional[str] = None
    status: OrderStatus
    total_amount: float
    ordered_items: List[OrderItemResponse] = []
    placed_items: List[OrderItemResponse] = []
    cancelled_items: List[OrderItemResponse] = []
    created_at: Optional[datetime] = None

    class Config:
        from_attributes = True


# --- Table Transfer ---

class TableTransferRequest(BaseModel):
    target_table_id: int


# --- History ---

class OrderHistoryResponse(BaseModel):
    id: int
    order_id: int
    event_type: str
    description: Optional[str] = None
    actor_id: Optional[str] = None
    created_at: datetime

    class Config:
        from_attributes = True


# --- Bill ---

class PayRequest(BaseModel):
    pay_type: PayType


class BillItemResponse(BaseModel):
    name: str
    quantity: int
    unit_price: float
    amount: float  # quantity * unit_price


class BillResponse(BaseModel):
    id: int
    order_id: int
    table_number: int
    table_name: str
    items: List[BillItemResponse]
    total_amount: float
    is_paid: bool
    pay_type: Optional[PayType] = None
    generated_at: datetime
    paid_at: Optional[datetime] = None


class StaffTransactionResponse(BaseModel):
    bill_id: int
    order_id: int
    table_number: int
    table_name: str
    items: List[BillItemResponse]
    total_amount: float
    is_paid: bool
    pay_type: Optional[PayType] = None
    paid_at: Optional[datetime] = None
    generated_at: datetime


class DailySalesResponse(BaseModel):
    date: str
    total_sales: float
    total_orders: int
    cash_total: float
    qr_total: float
    bills: List[BillResponse]


# --- Revenue Analytics ---

class RevenueDataPoint(BaseModel):
    label: str        # "14:00", "Mon", "15" etc.
    total_sales: float
    total_orders: int
    cash_total: float
    qr_total: float


class RevenuePeriod(BaseModel):
    total_sales: float
    total_orders: int
    cash_total: float
    qr_total: float
    breakdown: List[RevenueDataPoint]


class RevenueAnalyticsResponse(BaseModel):
    day: RevenuePeriod    # today, hourly breakdown
    week: RevenuePeriod   # last 7 days, daily breakdown
    month: RevenuePeriod  # current month, daily breakdown
    year: RevenuePeriod   # current year, monthly breakdown
