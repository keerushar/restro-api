from sqlalchemy import Column, Integer, String, Boolean, ForeignKey, DateTime, Float, Enum as SQLEnum
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
import enum
from .database import Base

class Role(str, enum.Enum):
    ADMIN = "admin"
    STAFF = "staff"
    CUSTOMER = "customer"

class User(Base):
    __tablename__ = "users"
    id = Column(Integer, primary_key=True, index=True)
    username = Column(String, unique=True, index=True)
    hashed_password = Column(String)
    role = Column(String)  # admin, staff, customer

class Floor(Base):
    __tablename__ = "floors"
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, unique=True)
    tables = relationship("Table", back_populates="floor", cascade="all, delete-orphan")

class Table(Base):
    __tablename__ = "tables"
    id = Column(Integer, primary_key=True, index=True)
    floor_id = Column(Integer, ForeignKey("floors.id"))
    table_number = Column(String)
    capacity = Column(Integer)
    
    floor = relationship("Floor", back_populates="tables")
    reservations = relationship("Reservation", back_populates="table", cascade="all, delete-orphan")
    orders = relationship("Order", back_populates="table", cascade="all, delete-orphan")

class Category(Base):
    __tablename__ = "categories"
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, unique=True)  # e.g., Breakfast, Veg
    items = relationship("MenuItem", back_populates="category", cascade="all, delete-orphan")

class MenuItem(Base):
    __tablename__ = "menu_items"
    id = Column(Integer, primary_key=True, index=True)
    category_id = Column(Integer, ForeignKey("categories.id"))
    name = Column(String, index=True)
    price = Column(Float)
    is_available = Column(Boolean, default=True)
    
    category = relationship("Category", back_populates="items")

# Feature: Staff can add frequently requested items (to be reviewed by admin)
class ItemRequest(Base):
    __tablename__ = "item_requests"
    id = Column(Integer, primary_key=True, index=True)
    requested_by_id = Column(Integer, ForeignKey("users.id"))
    item_name = Column(String)
    description = Column(String)
    request_count = Column(Integer, default=1)

class Reservation(Base):
    __tablename__ = "reservations"
    id = Column(Integer, primary_key=True, index=True)
    table_id = Column(Integer, ForeignKey("tables.id"))
    customer_name = Column(String)
    start_time = Column(DateTime)
    end_time = Column(DateTime)
    
    table = relationship("Table", back_populates="reservations")

class Order(Base):
    __tablename__ = "orders"
    id = Column(Integer, primary_key=True, index=True)
    table_id = Column(Integer, ForeignKey("tables.id"))
    staff_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    status = Column(String, default="pending")  # pending, completed, cancelled
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    
    table = relationship("Table", back_populates="orders")
    items = relationship("OrderItem", back_populates="order", cascade="all, delete-orphan")

class OrderItem(Base):
    __tablename__ = "order_items"
    id = Column(Integer, primary_key=True, index=True)
    order_id = Column(Integer, ForeignKey("orders.id"))
    menu_item_id = Column(Integer, ForeignKey("menu_items.id"))
    quantity = Column(Integer, default=1)
    
    order = relationship("Order", back_populates="items")
    menu_item = relationship("MenuItem")
