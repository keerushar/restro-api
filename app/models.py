from sqlalchemy import Column, Integer, String, Float, Boolean, ForeignKey, DateTime, Text
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
import enum
from .database import Base


class Role(str, enum.Enum):
    SUPERADMIN = "superadmin"
    ADMIN = "admin"
    STAFF = "staff"


class User(Base):
    __tablename__ = "users"
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String)
    username = Column(String, unique=True, index=True)
    hashed_password = Column(String)
    role = Column(String, default=Role.STAFF)
    # null for superadmin and admin; points to admin's user.id for staff
    admin_id = Column(Integer, ForeignKey("users.id"), nullable=True)


class Floor(Base):
    __tablename__ = "floors"
    id = Column(Integer, primary_key=True, index=True)
    admin_id = Column(Integer, ForeignKey("users.id"))
    name = Column(String)


class Table(Base):
    __tablename__ = "tables"
    id = Column(Integer, primary_key=True, index=True)
    admin_id = Column(Integer, ForeignKey("users.id"))
    table_number = Column(Integer)
    table_name = Column(String)
    reservations = relationship("Reservation", back_populates="table", cascade="all, delete-orphan")
    orders = relationship("Order", back_populates="table", cascade="all, delete-orphan")


class MenuItem(Base):
    __tablename__ = "menu_items"
    id = Column(Integer, primary_key=True, index=True)
    admin_id = Column(Integer, ForeignKey("users.id"))
    name = Column(String, index=True)
    price = Column(Float)
    is_available = Column(Boolean, default=True)


class ItemRequest(Base):
    __tablename__ = "item_requests"
    id = Column(Integer, primary_key=True, index=True)
    requested_by_id = Column(Integer, ForeignKey("users.id"))
    admin_id = Column(Integer, ForeignKey("users.id"))  # the admin this request belongs to
    item_name = Column(String)
    description = Column(String)
    request_count = Column(Integer, default=1)


class Reservation(Base):
    __tablename__ = "reservations"
    id = Column(Integer, primary_key=True, index=True)
    admin_id = Column(Integer, ForeignKey("users.id"))
    table_id = Column(Integer, ForeignKey("tables.id"))
    customer_name = Column(String)
    start_time = Column(DateTime)
    end_time = Column(DateTime)
    table = relationship("Table", back_populates="reservations")


class Order(Base):
    __tablename__ = "orders"
    id = Column(Integer, primary_key=True, index=True)
    admin_id = Column(Integer, ForeignKey("users.id"))   # which admin's restaurant
    table_id = Column(Integer, ForeignKey("tables.id"))
    table_number = Column(Integer)
    table_name = Column(String)
    staff_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    status = Column(String, default="pending")  # pending | completed
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
    status = Column(String, default="ordered")  # ordered | placed
    order = relationship("Order", back_populates="items")
    menu_item = relationship("MenuItem")


class OrderHistory(Base):
    __tablename__ = "order_history"
    id = Column(Integer, primary_key=True, index=True)
    order_id = Column(Integer, ForeignKey("orders.id"))
    event_type = Column(String)
    description = Column(Text, nullable=True)
    actor_id = Column(Integer, ForeignKey("users.id"), nullable=True)
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
    pay_type = Column(String, nullable=True)  # cash | qr
    generated_at = Column(DateTime(timezone=True), server_default=func.now())
    paid_at = Column(DateTime(timezone=True), nullable=True)
    order = relationship("Order", back_populates="bill")
