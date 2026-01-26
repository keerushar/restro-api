from fastapi import FastAPI, Depends, HTTPException, status
from sqlalchemy.orm import Session
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from typing import List
from jose import jwt, JWTError
from datetime import datetime

from . import models, schemas, database, auth

# Create tables
models.Base.metadata.create_all(bind=database.engine)

app = FastAPI(title="Restaurant Management System")

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="token")

# --- Dependencies ---
def get_current_user(token: str = Depends(oauth2_scheme), db: Session = Depends(database.get_db)):
    try:
        payload = jwt.decode(token, auth.SECRET_KEY, algorithms=[auth.ALGORITHM])
        username: str = payload.get("sub")
        if username is None:
            raise HTTPException(status_code=401, detail="Invalid auth credentials")
    except JWTError:
        raise HTTPException(status_code=401, detail="Invalid auth credentials")
    
    user = db.query(models.User).filter(models.User.username == username).first()
    if user is None:
        raise HTTPException(status_code=401, detail="User not found")
    return user

def admin_only(user: models.User = Depends(get_current_user)):
    if user.role != "admin":
        raise HTTPException(status_code=403, detail="Admin privileges required")
    return user

def staff_only(user: models.User = Depends(get_current_user)):
    if user.role not in ["admin", "staff"]:
        raise HTTPException(status_code=403, detail="Staff privileges required")
    return user

# --- Auth Routes ---
@app.post("/register", response_model=schemas.UserResponse)
def register(user: schemas.UserCreate, db: Session = Depends(database.get_db)):
    # Check if user already exists
    existing_user = db.query(models.User).filter(models.User.username == user.username).first()
    if existing_user:
        raise HTTPException(status_code=400, detail="Username already registered")
    
    hashed_pw = auth.get_password_hash(user.password)
    new_user = models.User(username=user.username, hashed_password=hashed_pw, role=user.role)
    db.add(new_user)
    db.commit()
    db.refresh(new_user)
    return new_user

@app.post("/token", response_model=schemas.Token)
def login(form_data: OAuth2PasswordRequestForm = Depends(), db: Session = Depends(database.get_db)):
    user = db.query(models.User).filter(models.User.username == form_data.username).first()
    if not user or not auth.verify_password(form_data.password, user.hashed_password):
        raise HTTPException(status_code=401, detail="Incorrect username or password")
    
    access_token = auth.create_access_token(data={"sub": user.username, "role": user.role})
    return {"access_token": access_token, "token_type": "bearer"}

# --- Floor Management ---
@app.post("/floors", response_model=schemas.FloorResponse)
def create_floor(floor: schemas.FloorCreate, db: Session = Depends(database.get_db), current_user = Depends(admin_only)):
    # Check if floor name already exists
    existing = db.query(models.Floor).filter(models.Floor.name == floor.name).first()
    if existing:
        raise HTTPException(status_code=400, detail="Floor name already exists")
    
    new_floor = models.Floor(name=floor.name)
    db.add(new_floor)
    db.commit()
    db.refresh(new_floor)
    return new_floor

@app.get("/floors", response_model=List[schemas.FloorResponse])
def read_floors(db: Session = Depends(database.get_db)):
    return db.query(models.Floor).all()

@app.get("/floors/{floor_id}", response_model=schemas.FloorResponse)
def read_floor(floor_id: int, db: Session = Depends(database.get_db)):
    floor = db.query(models.Floor).filter(models.Floor.id == floor_id).first()
    if not floor:
        raise HTTPException(status_code=404, detail="Floor not found")
    return floor

@app.put("/floors/{floor_id}", response_model=schemas.FloorResponse)
def update_floor(floor_id: int, floor_update: schemas.FloorUpdate, db: Session = Depends(database.get_db), current_user = Depends(admin_only)):
    floor = db.query(models.Floor).filter(models.Floor.id == floor_id).first()
    if not floor:
        raise HTTPException(status_code=404, detail="Floor not found")
    
    if floor_update.name is not None:
        # Check if new name already exists
        existing = db.query(models.Floor).filter(models.Floor.name == floor_update.name, models.Floor.id != floor_id).first()
        if existing:
            raise HTTPException(status_code=400, detail="Floor name already exists")
        floor.name = floor_update.name
    
    db.commit()
    db.refresh(floor)
    return floor

@app.delete("/floors/{floor_id}")
def delete_floor(floor_id: int, db: Session = Depends(database.get_db), current_user = Depends(admin_only)):
    floor = db.query(models.Floor).filter(models.Floor.id == floor_id).first()
    if not floor:
        raise HTTPException(status_code=404, detail="Floor not found")
    
    db.delete(floor)
    db.commit()
    return {"msg": "Floor deleted successfully"}

# --- Table Management ---
@app.post("/tables", response_model=schemas.TableResponse)
def create_table(table: schemas.TableCreate, db: Session = Depends(database.get_db), current_user = Depends(admin_only)):
    # Check if floor exists
    floor = db.query(models.Floor).filter(models.Floor.id == table.floor_id).first()
    if not floor:
        raise HTTPException(status_code=404, detail="Floor not found")
    
    new_table = models.Table(**table.dict())
    db.add(new_table)
    db.commit()
    db.refresh(new_table)
    return new_table

@app.get("/tables", response_model=List[schemas.TableResponse])
def read_tables(db: Session = Depends(database.get_db)):
    return db.query(models.Table).all()

@app.get("/tables/{table_id}", response_model=schemas.TableResponse)
def read_table(table_id: int, db: Session = Depends(database.get_db)):
    table = db.query(models.Table).filter(models.Table.id == table_id).first()
    if not table:
        raise HTTPException(status_code=404, detail="Table not found")
    return table

@app.put("/tables/{table_id}", response_model=schemas.TableResponse)
def update_table(table_id: int, table_update: schemas.TableUpdate, db: Session = Depends(database.get_db), current_user = Depends(admin_only)):
    table = db.query(models.Table).filter(models.Table.id == table_id).first()
    if not table:
        raise HTTPException(status_code=404, detail="Table not found")
    
    if table_update.table_number is not None:
        table.table_number = table_update.table_number
    if table_update.capacity is not None:
        table.capacity = table_update.capacity
    if table_update.floor_id is not None:
        # Check if new floor exists
        floor = db.query(models.Floor).filter(models.Floor.id == table_update.floor_id).first()
        if not floor:
            raise HTTPException(status_code=404, detail="Floor not found")
        table.floor_id = table_update.floor_id
    
    db.commit()
    db.refresh(table)
    return table

@app.delete("/tables/{table_id}")
def delete_table(table_id: int, db: Session = Depends(database.get_db), current_user = Depends(admin_only)):
    table = db.query(models.Table).filter(models.Table.id == table_id).first()
    if not table:
        raise HTTPException(status_code=404, detail="Table not found")
    
    db.delete(table)
    db.commit()
    return {"msg": "Table deleted successfully"}

# --- Category Management ---
@app.post("/categories", response_model=schemas.CategoryResponse)
def create_category(cat: schemas.CategoryCreate, db: Session = Depends(database.get_db), current_user = Depends(admin_only)):
    # Check if category already exists
    existing = db.query(models.Category).filter(models.Category.name == cat.name).first()
    if existing:
        raise HTTPException(status_code=400, detail="Category already exists")
    
    new_cat = models.Category(name=cat.name)
    db.add(new_cat)
    db.commit()
    db.refresh(new_cat)
    return new_cat

@app.get("/categories", response_model=List[schemas.CategoryResponse])
def read_categories(db: Session = Depends(database.get_db)):
    return db.query(models.Category).all()

@app.put("/categories/{category_id}", response_model=schemas.CategoryResponse)
def update_category(category_id: int, cat_update: schemas.CategoryUpdate, db: Session = Depends(database.get_db), current_user = Depends(admin_only)):
    category = db.query(models.Category).filter(models.Category.id == category_id).first()
    if not category:
        raise HTTPException(status_code=404, detail="Category not found")
    
    if cat_update.name is not None:
        # Check if new name already exists
        existing = db.query(models.Category).filter(models.Category.name == cat_update.name, models.Category.id != category_id).first()
        if existing:
            raise HTTPException(status_code=400, detail="Category name already exists")
        category.name = cat_update.name
    
    db.commit()
    db.refresh(category)
    return category

@app.delete("/categories/{category_id}")
def delete_category(category_id: int, db: Session = Depends(database.get_db), current_user = Depends(admin_only)):
    category = db.query(models.Category).filter(models.Category.id == category_id).first()
    if not category:
        raise HTTPException(status_code=404, detail="Category not found")
    
    db.delete(category)
    db.commit()
    return {"msg": "Category deleted successfully"}

# --- Menu Item Management ---
@app.post("/menu-items", response_model=schemas.MenuItemResponse)
def create_menu_item(item: schemas.MenuItemCreate, db: Session = Depends(database.get_db), current_user = Depends(admin_only)):
    # Check if category exists
    category = db.query(models.Category).filter(models.Category.id == item.category_id).first()
    if not category:
        raise HTTPException(status_code=404, detail="Category not found")
    
    new_item = models.MenuItem(**item.dict())
    db.add(new_item)
    db.commit()
    db.refresh(new_item)
    return new_item

@app.get("/menu-items", response_model=List[schemas.MenuItemResponse])
def get_menu(available_only: bool = False, db: Session = Depends(database.get_db)):
    query = db.query(models.MenuItem)
    if available_only:
        query = query.filter(models.MenuItem.is_available == True)
    return query.all()

@app.get("/menu-items/{item_id}", response_model=schemas.MenuItemResponse)
def get_menu_item(item_id: int, db: Session = Depends(database.get_db)):
    item = db.query(models.MenuItem).filter(models.MenuItem.id == item_id).first()
    if not item:
        raise HTTPException(status_code=404, detail="Menu item not found")
    return item

@app.put("/menu-items/{item_id}", response_model=schemas.MenuItemResponse)
def update_menu_item(item_id: int, item_update: schemas.MenuItemUpdate, db: Session = Depends(database.get_db), current_user = Depends(admin_only)):
    item = db.query(models.MenuItem).filter(models.MenuItem.id == item_id).first()
    if not item:
        raise HTTPException(status_code=404, detail="Menu item not found")
    
    if item_update.name is not None:
        item.name = item_update.name
    if item_update.price is not None:
        item.price = item_update.price
    if item_update.category_id is not None:
        # Check if category exists
        category = db.query(models.Category).filter(models.Category.id == item_update.category_id).first()
        if not category:
            raise HTTPException(status_code=404, detail="Category not found")
        item.category_id = item_update.category_id
    if item_update.is_available is not None:
        item.is_available = item_update.is_available
    
    db.commit()
    db.refresh(item)
    return item

@app.patch("/menu-items/{item_id}/availability", response_model=schemas.MenuItemResponse)
def toggle_menu_item_availability(item_id: int, is_available: bool, db: Session = Depends(database.get_db), current_user = Depends(admin_only)):
    item = db.query(models.MenuItem).filter(models.MenuItem.id == item_id).first()
    if not item:
        raise HTTPException(status_code=404, detail="Menu item not found")
    
    item.is_available = is_available
    db.commit()
    db.refresh(item)
    return item

@app.delete("/menu-items/{item_id}")
def delete_menu_item(item_id: int, db: Session = Depends(database.get_db), current_user = Depends(admin_only)):
    item = db.query(models.MenuItem).filter(models.MenuItem.id == item_id).first()
    if not item:
        raise HTTPException(status_code=404, detail="Menu item not found")
    
    db.delete(item)
    db.commit()
    return {"msg": "Menu item deleted successfully"}

# --- Staff: Requested Items ---
@app.post("/staff/request-item")
def request_new_item(req: schemas.ItemRequestCreate, db: Session = Depends(database.get_db), current_user = Depends(staff_only)):
    # Check if item already requested, if so, increment count
    existing = db.query(models.ItemRequest).filter(models.ItemRequest.item_name == req.item_name).first()
    if existing:
        existing.request_count += 1
        db.commit()
    else:
        new_req = models.ItemRequest(**req.dict(), requested_by_id=current_user.id)
        db.add(new_req)
        db.commit()
    return {"msg": "Request logged"}

@app.get("/admin/item-requests", response_model=List[schemas.ItemRequestResponse])
def get_item_requests(db: Session = Depends(database.get_db), current_user = Depends(admin_only)):
    return db.query(models.ItemRequest).order_by(models.ItemRequest.request_count.desc()).all()

@app.delete("/admin/item-requests/{request_id}")
def delete_item_request(request_id: int, db: Session = Depends(database.get_db), current_user = Depends(admin_only)):
    item_request = db.query(models.ItemRequest).filter(models.ItemRequest.id == request_id).first()
    if not item_request:
        raise HTTPException(status_code=404, detail="Item request not found")
    
    db.delete(item_request)
    db.commit()
    return {"msg": "Item request deleted successfully"}

# --- Reservations ---
def check_table_availability(table_id: int, start_time: datetime, end_time: datetime, db: Session, exclude_reservation_id: int = None):
    """Check if a table is available for the given time slot"""
    query = db.query(models.Reservation).filter(
        models.Reservation.table_id == table_id,
        models.Reservation.start_time < end_time,
        models.Reservation.end_time > start_time
    )
    
    if exclude_reservation_id:
        query = query.filter(models.Reservation.id != exclude_reservation_id)
    
    conflicting_reservations = query.all()
    return len(conflicting_reservations) == 0

@app.post("/reservations", response_model=schemas.ReservationResponse)
def book_table(booking: schemas.ReservationCreate, db: Session = Depends(database.get_db)):
    # Check if table exists
    table = db.query(models.Table).filter(models.Table.id == booking.table_id).first()
    if not table:
        raise HTTPException(status_code=404, detail="Table not found")
    
    # Check if time is valid
    if booking.start_time >= booking.end_time:
        raise HTTPException(status_code=400, detail="End time must be after start time")
    
    # Check availability
    if not check_table_availability(booking.table_id, booking.start_time, booking.end_time, db):
        raise HTTPException(status_code=400, detail="Table is not available for the requested time slot")
    
    new_res = models.Reservation(**booking.dict())
    db.add(new_res)
    db.commit()
    db.refresh(new_res)
    return new_res

@app.get("/reservations", response_model=List[schemas.ReservationResponse])
def get_reservations(table_id: int = None, db: Session = Depends(database.get_db)):
    query = db.query(models.Reservation)
    if table_id:
        query = query.filter(models.Reservation.table_id == table_id)
    return query.all()

@app.get("/reservations/{reservation_id}", response_model=schemas.ReservationResponse)
def get_reservation(reservation_id: int, db: Session = Depends(database.get_db)):
    reservation = db.query(models.Reservation).filter(models.Reservation.id == reservation_id).first()
    if not reservation:
        raise HTTPException(status_code=404, detail="Reservation not found")
    return reservation

@app.delete("/reservations/{reservation_id}")
def cancel_reservation(reservation_id: int, db: Session = Depends(database.get_db)):
    reservation = db.query(models.Reservation).filter(models.Reservation.id == reservation_id).first()
    if not reservation:
        raise HTTPException(status_code=404, detail="Reservation not found")
    
    db.delete(reservation)
    db.commit()
    return {"msg": "Reservation cancelled successfully"}

# --- Orders ---
@app.post("/orders", response_model=schemas.OrderResponse)
def create_order(order_data: schemas.OrderCreate, db: Session = Depends(database.get_db), current_user = Depends(staff_only)):
    # Check if table exists
    table = db.query(models.Table).filter(models.Table.id == order_data.table_id).first()
    if not table:
        raise HTTPException(status_code=404, detail="Table not found")
    
    # Validate all menu items exist and are available
    for item in order_data.items:
        menu_item = db.query(models.MenuItem).filter(models.MenuItem.id == item.menu_item_id).first()
        if not menu_item:
            raise HTTPException(status_code=404, detail=f"Menu item {item.menu_item_id} not found")
        if not menu_item.is_available:
            raise HTTPException(status_code=400, detail=f"Menu item '{menu_item.name}' is not available")
    
    # Create Order
    new_order = models.Order(table_id=order_data.table_id, staff_id=current_user.id)
    db.add(new_order)
    db.commit()
    db.refresh(new_order)
    
    # Add items
    for item in order_data.items:
        order_item = models.OrderItem(order_id=new_order.id, menu_item_id=item.menu_item_id, quantity=item.quantity)
        db.add(order_item)
    
    db.commit()
    db.refresh(new_order)
    return new_order

@app.get("/orders", response_model=List[schemas.OrderResponse])
def get_orders(table_id: int = None, status: str = None, db: Session = Depends(database.get_db), current_user = Depends(staff_only)):
    query = db.query(models.Order)
    if table_id:
        query = query.filter(models.Order.table_id == table_id)
    if status:
        query = query.filter(models.Order.status == status)
    return query.all()

@app.get("/orders/{order_id}", response_model=schemas.OrderResponse)
def get_order(order_id: int, db: Session = Depends(database.get_db), current_user = Depends(staff_only)):
    order = db.query(models.Order).filter(models.Order.id == order_id).first()
    if not order:
        raise HTTPException(status_code=404, detail="Order not found")
    return order

@app.patch("/orders/{order_id}/status", response_model=schemas.OrderResponse)
def update_order_status(order_id: int, status_update: schemas.OrderStatusUpdate, db: Session = Depends(database.get_db), current_user = Depends(staff_only)):
    order = db.query(models.Order).filter(models.Order.id == order_id).first()
    if not order:
        raise HTTPException(status_code=404, detail="Order not found")
    
    if status_update.status not in ["pending", "completed", "cancelled"]:
        raise HTTPException(status_code=400, detail="Invalid status. Must be: pending, completed, or cancelled")
    
    order.status = status_update.status
    db.commit()
    db.refresh(order)
    return order

@app.delete("/orders/{order_id}")
def delete_order(order_id: int, db: Session = Depends(database.get_db), current_user = Depends(admin_only)):
    order = db.query(models.Order).filter(models.Order.id == order_id).first()
    if not order:
        raise HTTPException(status_code=404, detail="Order not found")
    
    db.delete(order)
    db.commit()
    return {"msg": "Order deleted successfully"}
