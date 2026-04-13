import uuid
import enum
from sqlalchemy import Column, Integer, String, Float, Boolean, ForeignKey, DateTime, Text
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from .database import Base


def gen_uuid():
    return str(uuid.uuid4())


class Role(str, enum.Enum):
    SUPER_ADMIN = "super_admin"
    CAFE_ADMIN = "cafe_admin"
    STAFF = "staff"


class Cafe(Base):
    __tablename__ = "cafes"
    id = Column(String(36), primary_key=True, default=gen_uuid)
    name = Column(String, nullable=False)
    username = Column(String, unique=True, index=True, nullable=False)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    users = relationship("User", back_populates="cafe", foreign_keys="User.cafe_id")


class User(Base):
    __tablename__ = "users"
    id = Column(String(36), primary_key=True, default=gen_uuid)
    name = Column(String, nullable=False)
    username = Column(String, unique=True, index=True, nullable=False)
    hashed_password = Column(String, nullable=False)
    role = Column(String, nullable=False)  # super_admin | cafe_admin | staff
    is_active = Column(Boolean, default=True)
    # null for super_admin; cafe's id for cafe_admin and staff
    cafe_id = Column(String(36), ForeignKey("cafes.id"), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    cafe = relationship("Cafe", back_populates="users", foreign_keys=[cafe_id])


class Floor(Base):
    __tablename__ = "floors"
    id = Column(Integer, primary_key=True, index=True)
    cafe_id = Column(String(36), ForeignKey("cafes.id"), nullable=False)
    name = Column(String)


class Table(Base):
    __tablename__ = "tables"
    id = Column(Integer, primary_key=True, index=True)
    cafe_id = Column(String(36), ForeignKey("cafes.id"), nullable=False)
    table_number = Column(Integer)
    table_name = Column(String)
    reservations = relationship("Reservation", back_populates="table", cascade="all, delete-orphan")
    orders = relationship("Order", back_populates="table", cascade="all, delete-orphan")


class MenuItem(Base):
    __tablename__ = "menu_items"
    id = Column(Integer, primary_key=True, index=True)
    cafe_id = Column(String(36), ForeignKey("cafes.id"), nullable=False)
    name = Column(String, index=True)
    price = Column(Float)
    is_available = Column(Boolean, default=True)


class ItemRequest(Base):
    __tablename__ = "item_requests"
    id = Column(Integer, primary_key=True, index=True)
    cafe_id = Column(String(36), ForeignKey("cafes.id"), nullable=False)
    requested_by_id = Column(String(36), ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    item_name = Column(String)
    description = Column(String)
    request_count = Column(Integer, default=1)


class Reservation(Base):
    __tablename__ = "reservations"
    id = Column(Integer, primary_key=True, index=True)
    cafe_id = Column(String(36), ForeignKey("cafes.id"), nullable=False)
    table_id = Column(Integer, ForeignKey("tables.id"))
    customer_name = Column(String)
    start_time = Column(DateTime)
    end_time = Column(DateTime)
    table = relationship("Table", back_populates="reservations")


class Order(Base):
    __tablename__ = "orders"
    id = Column(Integer, primary_key=True, index=True)
    cafe_id = Column(String(36), ForeignKey("cafes.id"), nullable=False)
    table_id = Column(Integer, ForeignKey("tables.id"))
    table_number = Column(Integer)
    table_name = Column(String)
    staff_id = Column(String(36), ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    status = Column(String, default="pending")
    total_amount = Column(Float, default=0.0)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    table = relationship("Table", back_populates="orders")
    items = relationship("OrderItem", back_populates="order", cascade="all, delete-orphan")
    history_events = relationship(
        "OrderHistory", back_populates="order",
        cascade="all, delete-orphan", order_by="OrderHistory.created_at"
    )
    bill = relationship("Bill", back_populates="order", uselist=False)

    @property
    def ordered_items(self):
        return [i for i in self.items if i.status == "ordered"]

    @property
    def placed_items(self):
        return [i for i in self.items if i.status == "placed"]

    @property
    def cancelled_items(self):
        return [i for i in self.items if i.status == "cancelled"]


class OrderItem(Base):
    __tablename__ = "order_items"
    id = Column(Integer, primary_key=True, index=True)
    order_id = Column(Integer, ForeignKey("orders.id"))
    menu_item_id = Column(Integer, ForeignKey("menu_items.id"), nullable=True)
    name = Column(String)
    price = Column(Float)
    quantity = Column(Integer, default=1)
    status = Column(String, default="ordered")
    order = relationship("Order", back_populates="items")
    menu_item = relationship("MenuItem")


class OrderHistory(Base):
    __tablename__ = "order_history"
    id = Column(Integer, primary_key=True, index=True)
    order_id = Column(Integer, ForeignKey("orders.id"))
    event_type = Column(String)
    description = Column(Text, nullable=True)
    actor_id = Column(String(36), ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    order = relationship("Order", back_populates="history_events")


class TokenBlocklist(Base):
    __tablename__ = "token_blocklist"
    id = Column(Integer, primary_key=True, index=True)
    token = Column(String, unique=True, index=True)
    expires_at = Column(DateTime(timezone=True))


class Bill(Base):
    __tablename__ = "bills"
    id = Column(Integer, primary_key=True, index=True)
    order_id = Column(Integer, ForeignKey("orders.id"), unique=True)
    table_number = Column(Integer)
    table_name = Column(String)
    total_amount = Column(Float)
    is_paid = Column(Boolean, default=False)
    pay_type = Column(String, nullable=True)
    generated_at = Column(DateTime(timezone=True), server_default=func.now())
    paid_at = Column(DateTime(timezone=True), nullable=True)
    order = relationship("Order", back_populates="bill")
