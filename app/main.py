from fastapi import FastAPI, Depends, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from typing import List, Optional
from jose import jwt, JWTError
from datetime import datetime, timezone, timedelta, date as date_type
import calendar

from . import models, schemas, database, auth

models.Base.metadata.create_all(bind=database.engine)

# Auto-create super_admin on first startup if it doesn't exist
def seed_superadmin():
    db = next(database.get_db())
    try:
        exists = db.query(models.User).filter(models.User.role == models.Role.SUPER_ADMIN).first()
        if not exists:
            db.add(models.User(
                name="Super Admin",
                username="superadmin",
                hashed_password=auth.get_password_hash("super123"),
                role=models.Role.SUPER_ADMIN,
                cafe_id=None,
            ))
            db.commit()
    finally:
        db.close()

seed_superadmin()

app = FastAPI(title="Restaurant Management System")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="login")

ACTIVE_ORDER_STATUSES = {"pending"}


# ============================================================
# Helpers
# ============================================================

def log_history(db, order_id, event_type, description=None, actor_id=None):
    """Add a history event — caller must commit."""
    db.add(models.OrderHistory(
        order_id=order_id,
        event_type=event_type,
        description=description,
        actor_id=actor_id,
    ))


def recalculate_total(order: models.Order) -> float:
    total = sum(
        item.price * item.quantity
        for item in order.items
        if item.status != "cancelled"
    )
    order.total_amount = total
    return total


def build_bill_response(bill: models.Bill, db: Session) -> schemas.BillResponse:
    # reload with eager loading to avoid lazy-load 500s
    bill = (
        db.query(models.Bill)
        .filter(models.Bill.id == bill.id)
        .first()
    )
    order = (
        db.query(models.Order)
        .filter(models.Order.id == bill.order_id)
        .first()
    )
    # only include non-cancelled items in the bill summary
    active_items = [i for i in order.items if i.status != "cancelled"]
    bill_items = [
        schemas.BillItemResponse(
            name=item.name,
            quantity=item.quantity,
            unit_price=item.price,
            amount=round(item.price * item.quantity, 2),
        )
        for item in active_items
    ]
    return schemas.BillResponse(
        id=bill.id,
        order_id=bill.order_id,
        table_number=bill.table_number,
        table_name=bill.table_name,
        items=bill_items,
        total_amount=bill.total_amount,
        is_paid=bill.is_paid,
        pay_type=bill.pay_type,
        generated_at=bill.generated_at,
        paid_at=bill.paid_at,
    )


# ============================================================
# Auth dependencies
# ============================================================

def get_current_user(
    token: str = Depends(oauth2_scheme),
    db: Session = Depends(database.get_db),
):
    try:
        payload = jwt.decode(token, auth.SECRET_KEY, algorithms=[auth.ALGORITHM])
        user_id: str = payload.get("sub")
        if user_id is None:
            raise HTTPException(status_code=401, detail="Invalid auth credentials")
    except JWTError:
        raise HTTPException(status_code=401, detail="Invalid auth credentials")

    blocked = db.query(models.TokenBlocklist).filter(models.TokenBlocklist.token == token).first()
    if blocked:
        raise HTTPException(status_code=401, detail="Token has been revoked. Please log in again.")

    user = db.query(models.User).filter(models.User.id == user_id).first()
    if user is None:
        raise HTTPException(status_code=401, detail="User not found")
    if not user.is_active:
        raise HTTPException(status_code=403, detail="Account is inactive")
    return user


def super_admin_only(user: models.User = Depends(get_current_user)):
    if user.role != models.Role.SUPER_ADMIN:
        raise HTTPException(status_code=403, detail="Super admin privileges required")
    return user


def cafe_admin_only(user: models.User = Depends(get_current_user)):
    if user.role not in [models.Role.SUPER_ADMIN, models.Role.CAFE_ADMIN]:
        raise HTTPException(status_code=403, detail="Cafe admin privileges required")
    return user


def staff_only(user: models.User = Depends(get_current_user)):
    # all roles have staff-level access
    return user


# keep old names as aliases so other endpoints don't break
admin_only = cafe_admin_only
superadmin_only = super_admin_only


# ============================================================
# Scoping — the core of multi-tenancy
# ============================================================

def get_scope(current_user: models.User) -> Optional[str]:
    """
    Returns the cafe_id to filter all queries with.
    - super_admin → None  (no filter, sees everything)
    - cafe_admin  → user.cafe_id
    - staff       → user.cafe_id
    """
    if current_user.role == models.Role.SUPER_ADMIN:
        return None
    return current_user.cafe_id


def apply_scope(query, model, current_user: models.User):
    """Apply cafe_id filter to a query if the user is not super_admin."""
    scope = get_scope(current_user)
    if scope is not None:
        query = query.filter(model.cafe_id == scope)
    return query


def assert_ownership(resource_cafe_id: str, current_user: models.User):
    """Raise 403 if the resource doesn't belong to the current user's cafe."""
    scope = get_scope(current_user)
    if scope is not None and resource_cafe_id != scope:
        raise HTTPException(status_code=403, detail="Access denied")


# ============================================================
# Auth
# ============================================================

@app.get("/profile", response_model=schemas.UserResponse)
def get_profile(current_user: models.User = Depends(get_current_user)):
    return current_user


@app.post("/auth/logout")
def logout(
    token: str = Depends(oauth2_scheme),
    db: Session = Depends(database.get_db),
):
    payload = jwt.decode(token, auth.SECRET_KEY, algorithms=[auth.ALGORITHM])
    expires_at = datetime.fromtimestamp(payload["exp"], tz=timezone.utc)
    db.add(models.TokenBlocklist(token=token, expires_at=expires_at))
    db.commit()
    return {"msg": "Logged out successfully"}


@app.post("/auth/register", response_model=schemas.UserResponse)
def register(
    user: schemas.UserCreate,
    db: Session = Depends(database.get_db),
    current_user: models.User = Depends(get_current_user),
):
    if user.role == models.Role.SUPER_ADMIN:
        raise HTTPException(status_code=400, detail="Cannot create super_admin via API")

    if user.role == models.Role.CAFE_ADMIN:
        if current_user.role != models.Role.SUPER_ADMIN:
            raise HTTPException(status_code=403, detail="Only super_admin can create cafe_admin accounts")
        if not user.cafe_id:
            raise HTTPException(status_code=400, detail="cafe_id is required when creating a cafe_admin")
        cafe = db.query(models.Cafe).filter(models.Cafe.id == user.cafe_id).first()
        if not cafe:
            raise HTTPException(status_code=404, detail="Cafe not found")
        if not user.password:
            user.password = "changeme123"
        cafe_id = user.cafe_id

    elif user.role == models.Role.STAFF:
        if not user.password:
            raise HTTPException(status_code=400, detail="Password is required when creating a staff account")
        if current_user.role == models.Role.CAFE_ADMIN:
            cafe_id = current_user.cafe_id
        elif current_user.role == models.Role.SUPER_ADMIN:
            if not user.cafe_id:
                raise HTTPException(status_code=400, detail="cafe_id is required when super_admin creates staff")
            cafe = db.query(models.Cafe).filter(models.Cafe.id == user.cafe_id).first()
            if not cafe:
                raise HTTPException(status_code=404, detail="Cafe not found")
            cafe_id = user.cafe_id
        else:
            raise HTTPException(status_code=403, detail="Only cafe_admin can create staff accounts")
    else:
        raise HTTPException(status_code=400, detail="Invalid role. Must be cafe_admin or staff")

    if db.query(models.User).filter(models.User.username == user.username).first():
        raise HTTPException(status_code=400, detail="Username already taken")

    new_user = models.User(
        name=user.name,
        username=user.username,
        hashed_password=auth.get_password_hash(user.password),
        role=user.role,
        is_active=user.is_active,
        cafe_id=cafe_id,
    )
    db.add(new_user)
    db.commit()
    db.refresh(new_user)
    return new_user


@app.post("/auth/login", response_model=schemas.Token)
def login(
    form_data: OAuth2PasswordRequestForm = Depends(),
    db: Session = Depends(database.get_db),
):
    user = db.query(models.User).filter(models.User.username == form_data.username).first()
    if not user or not auth.verify_password(form_data.password, user.hashed_password):
        raise HTTPException(status_code=401, detail="Incorrect username or password")
    if not user.is_active:
        raise HTTPException(status_code=403, detail="Account is inactive")
    if user.cafe_id:
        cafe = db.query(models.Cafe).filter(models.Cafe.id == user.cafe_id).first()
        if cafe and not cafe.is_active:
            raise HTTPException(status_code=403, detail="Cafe is inactive")
    access_token = auth.create_access_token(
        user_id=user.id,
        role=user.role,
        cafe_id=user.cafe_id,
    )
    return {"access_token": access_token, "token_type": "bearer"}


# keep /login as alias for Swagger compatibility
@app.post("/login", response_model=schemas.Token, include_in_schema=False)
def login_alias(
    form_data: OAuth2PasswordRequestForm = Depends(),
    db: Session = Depends(database.get_db),
):
    return login(form_data=form_data, db=db)


# ============================================================
# Staff management (admin sees their own staff)
# ============================================================

# ============================================================
# Cafes (super_admin only)
# ============================================================

@app.post("/cafes", response_model=schemas.CafeWithAdminResponse)
def create_cafe(
    data: schemas.CafeCreate,
    db: Session = Depends(database.get_db),
    _: models.User = Depends(super_admin_only),
):
    if db.query(models.Cafe).filter(models.Cafe.username == data.cafe_username).first():
        raise HTTPException(status_code=400, detail="Cafe username already taken")
    if db.query(models.User).filter(models.User.username == data.admin.username).first():
        raise HTTPException(status_code=400, detail="Admin username already taken")

    new_cafe = models.Cafe(name=data.cafe_name, username=data.cafe_username)
    db.add(new_cafe)
    db.flush()  # get new_cafe.id before committing

    new_admin = models.User(
        name=data.admin.name,
        username=data.admin.username,
        hashed_password=auth.get_password_hash(data.admin.password),
        role=models.Role.CAFE_ADMIN,
        is_active=True,
        cafe_id=new_cafe.id,
    )
    db.add(new_admin)
    db.commit()
    db.refresh(new_cafe)
    db.refresh(new_admin)
    return {"cafe": new_cafe, "admin": new_admin}


@app.get("/cafes", response_model=List[schemas.CafeResponse])
def list_cafes(
    db: Session = Depends(database.get_db),
    _: models.User = Depends(super_admin_only),
):
    return db.query(models.Cafe).all()


@app.patch("/cafes/{cafe_id}/status", response_model=schemas.CafeResponse)
def toggle_cafe_status(
    cafe_id: str,
    body: schemas.CafeStatusUpdate,
    db: Session = Depends(database.get_db),
    _: models.User = Depends(super_admin_only),
):
    cafe = db.query(models.Cafe).filter(models.Cafe.id == cafe_id).first()
    if not cafe:
        raise HTTPException(status_code=404, detail="Cafe not found")
    cafe.is_active = body.is_active
    db.commit()
    db.refresh(cafe)
    return cafe


# ============================================================
# Staff management
# ============================================================

@app.post("/staff", response_model=schemas.UserResponse)
def create_staff(
    data: schemas.StaffCreate,
    db: Session = Depends(database.get_db),
    current_user: models.User = Depends(cafe_admin_only),
):
    if db.query(models.User).filter(models.User.username == data.username).first():
        raise HTTPException(status_code=400, detail="Username already taken")

    new_staff = models.User(
        name=data.name,
        username=data.username,
        hashed_password=auth.get_password_hash(data.password),
        role=models.Role.STAFF,
        is_active=data.is_active,
        cafe_id=current_user.cafe_id,
    )
    db.add(new_staff)
    db.commit()
    db.refresh(new_staff)
    return new_staff


@app.get("/staff", response_model=List[schemas.UserResponse])
def list_staff(
    db: Session = Depends(database.get_db),
    current_user: models.User = Depends(cafe_admin_only),
):
    scope = get_scope(current_user)
    query = db.query(models.User).filter(models.User.role == models.Role.STAFF)
    if scope is not None:
        query = query.filter(models.User.cafe_id == scope)
    return query.all()


@app.patch("/staff/{staff_id}/status", response_model=schemas.UserResponse)
def toggle_staff_status(
    staff_id: str,
    body: schemas.CafeStatusUpdate,
    db: Session = Depends(database.get_db),
    current_user: models.User = Depends(cafe_admin_only),
):
    staff = db.query(models.User).filter(
        models.User.id == staff_id,
        models.User.role == models.Role.STAFF,
    ).first()
    if not staff:
        raise HTTPException(status_code=404, detail="Staff not found")
    assert_ownership(staff.cafe_id, current_user)
    staff.is_active = body.is_active
    db.commit()
    db.refresh(staff)
    return staff


@app.delete("/staff/{staff_id}")
def delete_staff(
    staff_id: str,
    db: Session = Depends(database.get_db),
    current_user: models.User = Depends(cafe_admin_only),
):
    staff = db.query(models.User).filter(
        models.User.id == staff_id,
        models.User.role == models.Role.STAFF,
    ).first()
    if not staff:
        raise HTTPException(status_code=404, detail="Staff not found")
    assert_ownership(staff.cafe_id, current_user)
    db.delete(staff)
    db.commit()
    return {"msg": "Staff removed successfully"}


# ============================================================
# Floors
# ============================================================

@app.post("/floors", response_model=schemas.FloorResponse)
def create_floor(
    floor: schemas.FloorCreate,
    db: Session = Depends(database.get_db),
    current_user: models.User = Depends(admin_only),
):
    new_floor = models.Floor(name=floor.name, admin_id=current_user.id)
    db.add(new_floor)
    db.commit()
    db.refresh(new_floor)
    return new_floor


@app.get("/floors", response_model=List[schemas.FloorResponse])
def read_floors(
    db: Session = Depends(database.get_db),
    current_user: models.User = Depends(staff_only),
):
    return apply_scope(db.query(models.Floor), models.Floor, current_user).all()


@app.get("/floors/{floor_id}", response_model=schemas.FloorResponse)
def read_floor(
    floor_id: int,
    db: Session = Depends(database.get_db),
    current_user: models.User = Depends(staff_only),
):
    floor = db.query(models.Floor).filter(models.Floor.id == floor_id).first()
    if not floor:
        raise HTTPException(status_code=404, detail="Floor not found")
    assert_ownership(floor.admin_id, current_user)
    return floor


@app.put("/floors/{floor_id}", response_model=schemas.FloorResponse)
def update_floor(
    floor_id: int,
    floor_update: schemas.FloorUpdate,
    db: Session = Depends(database.get_db),
    current_user: models.User = Depends(admin_only),
):
    floor = db.query(models.Floor).filter(models.Floor.id == floor_id).first()
    if not floor:
        raise HTTPException(status_code=404, detail="Floor not found")
    assert_ownership(floor.admin_id, current_user)
    if floor_update.name is not None:
        floor.name = floor_update.name
    db.commit()
    db.refresh(floor)
    return floor


@app.delete("/floors/{floor_id}")
def delete_floor(
    floor_id: int,
    db: Session = Depends(database.get_db),
    current_user: models.User = Depends(admin_only),
):
    floor = db.query(models.Floor).filter(models.Floor.id == floor_id).first()
    if not floor:
        raise HTTPException(status_code=404, detail="Floor not found")
    assert_ownership(floor.admin_id, current_user)
    db.delete(floor)
    db.commit()
    return {"msg": "Floor deleted successfully"}


# ============================================================
# Tables
# ============================================================

@app.post("/tables", response_model=schemas.TableResponse)
def create_table(
    table: schemas.TableCreate,
    db: Session = Depends(database.get_db),
    current_user: models.User = Depends(admin_only),
):
    new_table = models.Table(**table.model_dump(), admin_id=current_user.id)
    db.add(new_table)
    db.commit()
    db.refresh(new_table)
    return new_table


@app.get("/tables", response_model=List[schemas.TableResponse])
def read_tables(
    db: Session = Depends(database.get_db),
    current_user: models.User = Depends(staff_only),
):
    return apply_scope(db.query(models.Table), models.Table, current_user).all()


@app.get("/tables/{table_id}", response_model=schemas.TableResponse)
def read_table(
    table_id: int,
    db: Session = Depends(database.get_db),
    current_user: models.User = Depends(staff_only),
):
    table = db.query(models.Table).filter(models.Table.id == table_id).first()
    if not table:
        raise HTTPException(status_code=404, detail="Table not found")
    assert_ownership(table.admin_id, current_user)
    return table


@app.put("/tables/{table_id}", response_model=schemas.TableResponse)
def update_table(
    table_id: int,
    table_update: schemas.TableUpdate,
    db: Session = Depends(database.get_db),
    current_user: models.User = Depends(admin_only),
):
    table = db.query(models.Table).filter(models.Table.id == table_id).first()
    if not table:
        raise HTTPException(status_code=404, detail="Table not found")
    assert_ownership(table.admin_id, current_user)
    if table_update.table_number is not None:
        table.table_number = table_update.table_number
    if table_update.table_name is not None:
        table.table_name = table_update.table_name
    db.commit()
    db.refresh(table)
    return table


@app.delete("/tables/{table_id}")
def delete_table(
    table_id: int,
    db: Session = Depends(database.get_db),
    current_user: models.User = Depends(admin_only),
):
    table = db.query(models.Table).filter(models.Table.id == table_id).first()
    if not table:
        raise HTTPException(status_code=404, detail="Table not found")
    assert_ownership(table.admin_id, current_user)
    db.delete(table)
    db.commit()
    return {"msg": "Table deleted successfully"}


# ============================================================
# Menu Items
# ============================================================

@app.post("/menu-items", response_model=schemas.MenuItemResponse)
def create_menu_item(
    item: schemas.MenuItemCreate,
    db: Session = Depends(database.get_db),
    current_user: models.User = Depends(admin_only),
):
    new_item = models.MenuItem(**item.model_dump(), admin_id=current_user.id)
    db.add(new_item)
    db.commit()
    db.refresh(new_item)
    return new_item


@app.get("/menu-items", response_model=List[schemas.MenuItemResponse])
def get_menu(
    available_only: bool = False,
    db: Session = Depends(database.get_db),
    current_user: models.User = Depends(staff_only),
):
    query = apply_scope(db.query(models.MenuItem), models.MenuItem, current_user)
    if available_only:
        query = query.filter(models.MenuItem.is_available == True)
    return query.all()


@app.get("/menu-items/{item_id}", response_model=schemas.MenuItemResponse)
def get_menu_item(
    item_id: int,
    db: Session = Depends(database.get_db),
    current_user: models.User = Depends(staff_only),
):
    item = db.query(models.MenuItem).filter(models.MenuItem.id == item_id).first()
    if not item:
        raise HTTPException(status_code=404, detail="Menu item not found")
    assert_ownership(item.admin_id, current_user)
    return item


@app.put("/menu-items/{item_id}", response_model=schemas.MenuItemResponse)
def update_menu_item(
    item_id: int,
    item_update: schemas.MenuItemUpdate,
    db: Session = Depends(database.get_db),
    current_user: models.User = Depends(admin_only),
):
    item = db.query(models.MenuItem).filter(models.MenuItem.id == item_id).first()
    if not item:
        raise HTTPException(status_code=404, detail="Menu item not found")
    assert_ownership(item.admin_id, current_user)
    if item_update.name is not None:
        item.name = item_update.name
    if item_update.price is not None:
        item.price = item_update.price
    if item_update.is_available is not None:
        item.is_available = item_update.is_available
    db.commit()
    db.refresh(item)
    return item


@app.patch("/menu-items/{item_id}/availability", response_model=schemas.MenuItemResponse)
def toggle_menu_item_availability(
    item_id: int,
    is_available: bool,
    db: Session = Depends(database.get_db),
    current_user: models.User = Depends(admin_only),
):
    item = db.query(models.MenuItem).filter(models.MenuItem.id == item_id).first()
    if not item:
        raise HTTPException(status_code=404, detail="Menu item not found")
    assert_ownership(item.admin_id, current_user)
    item.is_available = is_available
    db.commit()
    db.refresh(item)
    return item


@app.delete("/menu-items/{item_id}")
def delete_menu_item(
    item_id: int,
    db: Session = Depends(database.get_db),
    current_user: models.User = Depends(admin_only),
):
    item = db.query(models.MenuItem).filter(models.MenuItem.id == item_id).first()
    if not item:
        raise HTTPException(status_code=404, detail="Menu item not found")
    assert_ownership(item.admin_id, current_user)
    db.delete(item)
    db.commit()
    return {"msg": "Menu item deleted successfully"}


# ============================================================
# Staff Item Requests
# ============================================================

@app.post("/staff/request-item")
def request_new_item(
    req: schemas.ItemRequestCreate,
    db: Session = Depends(database.get_db),
    current_user: models.User = Depends(staff_only),
):
    admin_id = get_scope(current_user)
    existing = db.query(models.ItemRequest).filter(
        models.ItemRequest.item_name == req.item_name,
        models.ItemRequest.admin_id == admin_id,
    ).first()
    if existing:
        existing.request_count += 1
        db.commit()
    else:
        db.add(models.ItemRequest(
            **req.model_dump(),
            requested_by_id=current_user.id,
            admin_id=admin_id,
        ))
        db.commit()
    return {"msg": "Request logged"}


@app.get("/admin/item-requests", response_model=List[schemas.ItemRequestResponse])
def get_item_requests(
    db: Session = Depends(database.get_db),
    current_user: models.User = Depends(admin_only),
):
    return apply_scope(
        db.query(models.ItemRequest).order_by(models.ItemRequest.request_count.desc()),
        models.ItemRequest,
        current_user,
    ).all()


@app.delete("/admin/item-requests/{request_id}")
def delete_item_request(
    request_id: int,
    db: Session = Depends(database.get_db),
    current_user: models.User = Depends(admin_only),
):
    item_request = db.query(models.ItemRequest).filter(models.ItemRequest.id == request_id).first()
    if not item_request:
        raise HTTPException(status_code=404, detail="Item request not found")
    assert_ownership(item_request.admin_id, current_user)
    db.delete(item_request)
    db.commit()
    return {"msg": "Item request deleted successfully"}


# ============================================================
# Reservations
# ============================================================

def check_table_availability(table_id, start_time, end_time, db, exclude_id=None):
    query = db.query(models.Reservation).filter(
        models.Reservation.table_id == table_id,
        models.Reservation.start_time < end_time,
        models.Reservation.end_time > start_time,
    )
    if exclude_id:
        query = query.filter(models.Reservation.id != exclude_id)
    return query.count() == 0


@app.post("/reservations", response_model=schemas.ReservationResponse)
def book_table(
    booking: schemas.ReservationCreate,
    db: Session = Depends(database.get_db),
    current_user: models.User = Depends(staff_only),
):
    admin_id = get_scope(current_user)
    table = db.query(models.Table).filter(
        models.Table.id == booking.table_id,
        models.Table.admin_id == admin_id,
    ).first()
    if not table:
        raise HTTPException(status_code=404, detail="Table not found")
    if booking.start_time >= booking.end_time:
        raise HTTPException(status_code=400, detail="End time must be after start time")
    if not check_table_availability(booking.table_id, booking.start_time, booking.end_time, db):
        raise HTTPException(status_code=400, detail="Table is not available for the requested time slot")
    new_res = models.Reservation(**booking.model_dump(), admin_id=admin_id)
    db.add(new_res)
    db.commit()
    db.refresh(new_res)
    return new_res


@app.get("/reservations", response_model=List[schemas.ReservationResponse])
def get_reservations(
    table_id: int = None,
    db: Session = Depends(database.get_db),
    current_user: models.User = Depends(staff_only),
):
    query = apply_scope(db.query(models.Reservation), models.Reservation, current_user)
    if table_id:
        query = query.filter(models.Reservation.table_id == table_id)
    return query.all()


@app.get("/reservations/{reservation_id}", response_model=schemas.ReservationResponse)
def get_reservation(
    reservation_id: int,
    db: Session = Depends(database.get_db),
    current_user: models.User = Depends(staff_only),
):
    res = db.query(models.Reservation).filter(models.Reservation.id == reservation_id).first()
    if not res:
        raise HTTPException(status_code=404, detail="Reservation not found")
    assert_ownership(res.admin_id, current_user)
    return res


@app.delete("/reservations/{reservation_id}")
def cancel_reservation(
    reservation_id: int,
    db: Session = Depends(database.get_db),
    current_user: models.User = Depends(staff_only),
):
    res = db.query(models.Reservation).filter(models.Reservation.id == reservation_id).first()
    if not res:
        raise HTTPException(status_code=404, detail="Reservation not found")
    assert_ownership(res.admin_id, current_user)
    db.delete(res)
    db.commit()
    return {"msg": "Reservation cancelled successfully"}


# ============================================================
# Orders
# ============================================================

@app.get("/tables/{table_id}/active-order", response_model=schemas.OrderResponse)
def get_active_order_for_table(
    table_id: int,
    db: Session = Depends(database.get_db),
    current_user: models.User = Depends(staff_only),
):
    """Get the current active order on a table including all its items."""
    admin_id = get_scope(current_user)
    table = db.query(models.Table).filter(
        models.Table.id == table_id,
        models.Table.admin_id == admin_id,
    ).first()
    if not table:
        raise HTTPException(status_code=404, detail="Table not found")
    order = db.query(models.Order).filter(
        models.Order.table_id == table_id,
        models.Order.status.in_(ACTIVE_ORDER_STATUSES),
    ).first()
    if not order:
        raise HTTPException(status_code=404, detail="No active order on this table")
    return order

def _resolve_order_items(items, db, admin_id):
    order_items = []
    for item in items:
        menu_item = db.query(models.MenuItem).filter(
            models.MenuItem.id == item.menu_item_id,
            models.MenuItem.admin_id == admin_id,
        ).first()
        if not menu_item:
            raise HTTPException(status_code=404, detail=f"Menu item {item.menu_item_id} not found")
        if not menu_item.is_available:
            raise HTTPException(status_code=400, detail=f"'{menu_item.name}' is not available")
        order_items.append(models.OrderItem(
            menu_item_id=menu_item.id,
            name=menu_item.name,
            price=menu_item.price,
            quantity=item.quantity,
            status="ordered",
        ))
    return order_items


@app.post("/orders", response_model=schemas.OrderResponse)
def create_order(
    order_data: schemas.OrderCreate,
    db: Session = Depends(database.get_db),
    current_user: models.User = Depends(staff_only),
):
    admin_id = get_scope(current_user)

    table = db.query(models.Table).filter(
        models.Table.id == order_data.table_id,
        models.Table.admin_id == admin_id,
    ).first()
    if not table:
        raise HTTPException(status_code=404, detail="Table not found")

    # If an active order already exists on this table, add items to it instead
    active = db.query(models.Order).filter(
        models.Order.table_id == table.id,
        models.Order.status.in_(ACTIVE_ORDER_STATUSES),
    ).first()

    if active:
        order_items = _resolve_order_items(order_data.items, db, admin_id)
        for oi in order_items:
            oi.order_id = active.id
            db.add(oi)
        db.flush()
        recalculate_total(active)
        log_history(
            db, active.id, "item_added",
            f"Added items: {', '.join(oi.name for oi in order_items)}",
            actor_id=current_user.id,
        )
        db.commit()
        db.refresh(active)
        return active

    new_order = models.Order(
        admin_id=admin_id,
        table_id=table.id,
        table_number=table.table_number,
        table_name=table.table_name,
        staff_id=current_user.id,
        status="pending",
    )
    db.add(new_order)
    db.flush()

    order_items = _resolve_order_items(order_data.items, db, admin_id)
    for oi in order_items:
        oi.order_id = new_order.id
        db.add(oi)

    db.flush()
    recalculate_total(new_order)

    log_history(
        db, new_order.id, "order_created",
        f"Order created for Table {table.table_number} ({table.table_name}). Items: {', '.join(oi.name for oi in order_items)}",
        actor_id=current_user.id,
    )

    db.commit()
    db.refresh(new_order)
    return new_order


@app.get("/orders", response_model=List[schemas.OrderResponse])
def get_orders(
    table_id: int = None,
    status: str = None,
    db: Session = Depends(database.get_db),
    current_user: models.User = Depends(staff_only),
):
    query = apply_scope(db.query(models.Order), models.Order, current_user)
    if table_id:
        query = query.filter(models.Order.table_id == table_id)
    if status:
        query = query.filter(models.Order.status == status)
    return query.all()


@app.get("/orders/{order_id}", response_model=schemas.OrderResponse)
def get_order(
    order_id: int,
    db: Session = Depends(database.get_db),
    current_user: models.User = Depends(staff_only),
):
    order = db.query(models.Order).filter(models.Order.id == order_id).first()
    if not order:
        raise HTTPException(status_code=404, detail="Order not found")
    assert_ownership(order.admin_id, current_user)
    return order


@app.post("/orders/{order_id}/items", response_model=schemas.OrderResponse)
def add_items_to_order(
    order_id: int,
    body: schemas.AddItemsToOrder,
    db: Session = Depends(database.get_db),
    current_user: models.User = Depends(staff_only),
):
    order = db.query(models.Order).filter(models.Order.id == order_id).first()
    if not order:
        raise HTTPException(status_code=404, detail="Order not found")
    assert_ownership(order.admin_id, current_user)
    if order.status not in ACTIVE_ORDER_STATUSES:
        raise HTTPException(status_code=400, detail="Cannot add items to a completed order")

    admin_id = get_scope(current_user)
    order_items = _resolve_order_items(body.items, db, admin_id)
    for oi in order_items:
        oi.order_id = order.id
        db.add(oi)

    db.flush()
    recalculate_total(order)
    log_history(db, order.id, "item_added",
                f"Added items: {', '.join(oi.name for oi in order_items)}",
                actor_id=current_user.id)
    db.commit()
    db.refresh(order)
    return order


@app.patch("/orders/{order_id}/items/{item_id}/status", response_model=schemas.OrderResponse)
def update_item_status(
    order_id: int,
    item_id: int,
    body: schemas.OrderItemStatusUpdate,
    db: Session = Depends(database.get_db),
    current_user: models.User = Depends(staff_only),
):
    order = db.query(models.Order).filter(models.Order.id == order_id).first()
    if not order:
        raise HTTPException(status_code=404, detail="Order not found")
    assert_ownership(order.admin_id, current_user)

    order_item = db.query(models.OrderItem).filter(
        models.OrderItem.id == item_id,
        models.OrderItem.order_id == order_id,
    ).first()
    if not order_item:
        raise HTTPException(status_code=404, detail="Order item not found")

    old_status = order_item.status
    order_item.status = body.status.value
    log_history(db, order.id, "item_status_changed",
                f"'{order_item.name}' status: {old_status} → {body.status.value}",
                actor_id=current_user.id)
    db.commit()
    db.refresh(order)
    return order


@app.patch("/orders/{order_id}/status", response_model=schemas.OrderResponse)
def update_order_status(
    order_id: int,
    status_update: schemas.OrderStatusUpdate,
    db: Session = Depends(database.get_db),
    current_user: models.User = Depends(staff_only),
):
    order = db.query(models.Order).filter(models.Order.id == order_id).first()
    if not order:
        raise HTTPException(status_code=404, detail="Order not found")
    assert_ownership(order.admin_id, current_user)
    if order.status == "completed":
        raise HTTPException(status_code=400, detail="Cannot update a completed order")

    old_status = order.status
    new_status = status_update.status.value
    order.status = new_status
    event_type = "status_changed"
    log_history(db, order.id, event_type,
                f"Status changed: {old_status} → {new_status}",
                actor_id=current_user.id)
    db.commit()
    db.refresh(order)
    return order


@app.post("/orders/{order_id}/transfer", response_model=schemas.OrderResponse)
def transfer_table(
    order_id: int,
    body: schemas.TableTransferRequest,
    db: Session = Depends(database.get_db),
    current_user: models.User = Depends(staff_only),
):
    order = db.query(models.Order).filter(models.Order.id == order_id).first()
    if not order:
        raise HTTPException(status_code=404, detail="Order not found")
    assert_ownership(order.admin_id, current_user)
    if order.status not in ACTIVE_ORDER_STATUSES:
        raise HTTPException(status_code=400, detail="Only active orders can be transferred")
    if order.table_id == body.target_table_id:
        raise HTTPException(status_code=400, detail="Order is already at that table")

    admin_id = get_scope(current_user)
    target_table = db.query(models.Table).with_for_update().filter(
        models.Table.id == body.target_table_id,
        models.Table.admin_id == admin_id,   # cannot transfer to another admin's table
    ).first()
    if not target_table:
        raise HTTPException(status_code=404, detail="Target table not found")

    conflict = db.query(models.Order).filter(
        models.Order.table_id == target_table.id,
        models.Order.status.in_(ACTIVE_ORDER_STATUSES),
    ).first()
    if conflict:
        raise HTTPException(status_code=400, detail="Target table already has an active order")

    from_number = order.table_number
    from_name = order.table_name
    order.table_id = target_table.id
    order.table_number = target_table.table_number
    order.table_name = target_table.table_name

    log_history(db, order.id, "table_transferred",
                f"Transferred from Table {from_number} ({from_name}) to Table {target_table.table_number} ({target_table.table_name})",
                actor_id=current_user.id)
    db.commit()
    db.refresh(order)
    return order


@app.delete("/orders/{order_id}")
def delete_order(
    order_id: int,
    db: Session = Depends(database.get_db),
    current_user: models.User = Depends(admin_only),
):
    order = db.query(models.Order).filter(models.Order.id == order_id).first()
    if not order:
        raise HTTPException(status_code=404, detail="Order not found")
    assert_ownership(order.admin_id, current_user)
    db.delete(order)
    db.commit()
    return {"msg": "Order deleted successfully"}


# ============================================================
# Order History
# ============================================================

@app.get("/orders/{order_id}/history", response_model=List[schemas.OrderHistoryResponse])
def get_order_history(
    order_id: int,
    db: Session = Depends(database.get_db),
    current_user: models.User = Depends(staff_only),
):
    order = db.query(models.Order).filter(models.Order.id == order_id).first()
    if not order:
        raise HTTPException(status_code=404, detail="Order not found")
    assert_ownership(order.admin_id, current_user)
    return (db.query(models.OrderHistory)
            .filter(models.OrderHistory.order_id == order_id)
            .order_by(models.OrderHistory.created_at)
            .all())


@app.get("/history", response_model=List[schemas.OrderHistoryResponse])
def get_all_history(
    order_id: Optional[int] = None,
    event_type: Optional[str] = None,
    db: Session = Depends(database.get_db),
    current_user: models.User = Depends(admin_only),
):
    # join through orders to apply admin scope
    scope = get_scope(current_user)
    query = db.query(models.OrderHistory).join(models.Order)
    if scope is not None:
        query = query.filter(models.Order.admin_id == scope)
    if order_id:
        query = query.filter(models.OrderHistory.order_id == order_id)
    if event_type:
        query = query.filter(models.OrderHistory.event_type == event_type)
    return query.order_by(models.OrderHistory.created_at.desc()).all()


# ============================================================
# Bills & Payments
# ============================================================

@app.post("/orders/{order_id}/bill", response_model=schemas.BillResponse)
def generate_bill(
    order_id: int,
    db: Session = Depends(database.get_db),
    current_user: models.User = Depends(staff_only),
):
    order = db.query(models.Order).filter(models.Order.id == order_id).first()
    if not order:
        raise HTTPException(status_code=404, detail="Order not found")
    assert_ownership(order.admin_id, current_user)
    if order.status == "completed":
        raise HTTPException(status_code=400, detail="Bill already settled — order is completed")
    if order.bill:
        raise HTTPException(status_code=400, detail="Bill already generated for this order")

    recalculate_total(order)
    bill = models.Bill(
        order_id=order.id,
        table_number=order.table_number,
        table_name=order.table_name,
        total_amount=order.total_amount,
    )
    db.add(bill)
    log_history(db, order.id, "bill_generated",
                f"Bill generated. Total: {order.total_amount}",
                actor_id=current_user.id)
    db.commit()
    db.refresh(bill)
    return build_bill_response(bill, db)


@app.get("/orders/{order_id}/bill", response_model=schemas.BillResponse)
def get_bill(
    order_id: int,
    db: Session = Depends(database.get_db),
    current_user: models.User = Depends(staff_only),
):
    order = db.query(models.Order).filter(models.Order.id == order_id).first()
    if not order:
        raise HTTPException(status_code=404, detail="Order not found")
    assert_ownership(order.admin_id, current_user)
    if not order.bill:
        raise HTTPException(status_code=404, detail="No bill found for this order")
    return build_bill_response(order.bill, db)


@app.post("/bills/{bill_id}/pay", response_model=schemas.BillResponse)
def pay_bill(
    bill_id: int,
    body: schemas.PayRequest,
    db: Session = Depends(database.get_db),
    current_user: models.User = Depends(staff_only),
):
    bill = db.query(models.Bill).filter(models.Bill.id == bill_id).first()
    if not bill:
        raise HTTPException(status_code=404, detail="Bill not found")
    assert_ownership(bill.order.admin_id, current_user)
    if bill.is_paid:
        raise HTTPException(status_code=400, detail="Bill is already paid")

    order = bill.order
    active_items = [i for i in order.items if i.status != "cancelled"]
    items_summary = ", ".join(
        f"{i.name} x{i.quantity} (${i.price * i.quantity:.2f})"
        for i in active_items
    )

    bill.is_paid = True
    bill.pay_type = body.pay_type.value
    bill.paid_at = datetime.now(timezone.utc)
    order.status = "completed"

    log_history(
        db, bill.order_id, "payment_received",
        f"Table {order.table_number} ({order.table_name}) | "
        f"Items: {items_summary} | "
        f"Total: ${bill.total_amount:.2f} | "
        f"Paid via: {body.pay_type.value}",
        actor_id=current_user.id,
    )
    db.commit()
    return build_bill_response(bill, db)


@app.get("/bills", response_model=List[schemas.BillResponse])
def get_all_bills(
    is_paid: Optional[bool] = None,
    date: Optional[date_type] = None,
    db: Session = Depends(database.get_db),
    current_user: models.User = Depends(staff_only),
):
    scope = get_scope(current_user)
    query = (
        db.query(models.Bill)
        .join(models.Order, models.Bill.order_id == models.Order.id)
    )
    if scope is not None:
        query = query.filter(models.Order.admin_id == scope)
    if is_paid is not None:
        query = query.filter(models.Bill.is_paid == is_paid)
    if date is not None:
        start = datetime(date.year, date.month, date.day, 0, 0, 0, tzinfo=timezone.utc)
        end = datetime(date.year, date.month, date.day, 23, 59, 59, tzinfo=timezone.utc)
        query = query.filter(models.Bill.paid_at >= start, models.Bill.paid_at <= end)
    query = query.order_by(models.Bill.paid_at.desc())
    return [build_bill_response(bill, db) for bill in query.all()]


@app.get("/bills/daily-summary", response_model=schemas.DailySalesResponse)
def daily_sales_summary(
    date: Optional[date_type] = None,
    db: Session = Depends(database.get_db),
    current_user: models.User = Depends(admin_only),
):
    target = date or datetime.now(timezone.utc).date()
    start = datetime(target.year, target.month, target.day, 0, 0, 0, tzinfo=timezone.utc)
    end = datetime(target.year, target.month, target.day, 23, 59, 59, tzinfo=timezone.utc)

    scope = get_scope(current_user)
    query = (
        db.query(models.Bill)
        .join(models.Order, models.Bill.order_id == models.Order.id)
        .filter(
            models.Bill.is_paid == True,
            models.Bill.paid_at >= start,
            models.Bill.paid_at <= end,
        )
    )
    if scope is not None:
        query = query.filter(models.Order.admin_id == scope)

    bills = query.order_by(models.Bill.paid_at.asc()).all()

    total_sales = sum(b.total_amount for b in bills)
    cash_total = sum(b.total_amount for b in bills if b.pay_type == "cash")
    qr_total = sum(b.total_amount for b in bills if b.pay_type == "qr")

    return schemas.DailySalesResponse(
        date=target.strftime("%Y-%m-%d"),
        total_orders=len(bills),
        total_sales=round(total_sales, 2),
        cash_total=round(cash_total, 2),
        qr_total=round(qr_total, 2),
        bills=[build_bill_response(b, db) for b in bills],
    )


# ============================================================
# Revenue Analytics
# ============================================================

def _build_revenue_period(bills, breakdown_points: list) -> schemas.RevenuePeriod:
    return schemas.RevenuePeriod(
        total_sales=round(sum(b.total_amount for b in bills), 2),
        total_orders=len(bills),
        cash_total=round(sum(b.total_amount for b in bills if b.pay_type == "cash"), 2),
        qr_total=round(sum(b.total_amount for b in bills if b.pay_type == "qr"), 2),
        breakdown=breakdown_points,
    )


@app.get("/analytics/revenue", response_model=schemas.RevenueAnalyticsResponse)
def revenue_analytics(
    db: Session = Depends(database.get_db),
    current_user: models.User = Depends(admin_only),
):
    now = datetime.now(timezone.utc)
    scope = get_scope(current_user)

    def scoped_bills(start: datetime, end: datetime):
        q = (
            db.query(models.Bill)
            .join(models.Order, models.Bill.order_id == models.Order.id)
            .filter(
                models.Bill.is_paid == True,
                models.Bill.paid_at >= start,
                models.Bill.paid_at <= end,
            )
        )
        if scope is not None:
            q = q.filter(models.Order.admin_id == scope)
        return q.all()

    # --- Day: today, hourly breakdown ---
    day_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
    day_end = now.replace(hour=23, minute=59, second=59, microsecond=999999)
    day_bills = scoped_bills(day_start, day_end)

    hour_buckets: dict[int, list] = {h: [] for h in range(24)}
    for b in day_bills:
        hour_buckets[b.paid_at.astimezone(timezone.utc).hour].append(b)
    day_breakdown = [
        schemas.RevenueDataPoint(
            label=f"{h:02d}:00",
            total_sales=round(sum(b.total_amount for b in hour_buckets[h]), 2),
            total_orders=len(hour_buckets[h]),
            cash_total=round(sum(b.total_amount for b in hour_buckets[h] if b.pay_type == "cash"), 2),
            qr_total=round(sum(b.total_amount for b in hour_buckets[h] if b.pay_type == "qr"), 2),
        )
        for h in range(24)
    ]

    # --- Week: last 7 days, daily breakdown ---
    week_start = (now - timedelta(days=6)).replace(
        hour=0, minute=0, second=0, microsecond=0
    )
    week_bills = scoped_bills(week_start, day_end)

    day_labels = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]
    week_buckets: dict[int, list] = {i: [] for i in range(7)}
    for b in week_bills:
        weekday = b.paid_at.astimezone(timezone.utc).weekday()  # 0=Mon
        week_buckets[weekday].append(b)
    week_breakdown = [
        schemas.RevenueDataPoint(
            label=day_labels[i],
            total_sales=round(sum(b.total_amount for b in week_buckets[i]), 2),
            total_orders=len(week_buckets[i]),
            cash_total=round(sum(b.total_amount for b in week_buckets[i] if b.pay_type == "cash"), 2),
            qr_total=round(sum(b.total_amount for b in week_buckets[i] if b.pay_type == "qr"), 2),
        )
        for i in range(7)
    ]

    # --- Month: current month, daily breakdown ---
    month_start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    last_day = calendar.monthrange(now.year, now.month)[1]
    month_end = now.replace(day=last_day, hour=23, minute=59, second=59, microsecond=999999)
    month_bills = scoped_bills(month_start, month_end)

    month_buckets: dict[int, list] = {d: [] for d in range(1, last_day + 1)}
    for b in month_bills:
        month_buckets[b.paid_at.astimezone(timezone.utc).day].append(b)
    month_breakdown = [
        schemas.RevenueDataPoint(
            label=str(d),
            total_sales=round(sum(b.total_amount for b in month_buckets[d]), 2),
            total_orders=len(month_buckets[d]),
            cash_total=round(sum(b.total_amount for b in month_buckets[d] if b.pay_type == "cash"), 2),
            qr_total=round(sum(b.total_amount for b in month_buckets[d] if b.pay_type == "qr"), 2),
        )
        for d in range(1, last_day + 1)
    ]

    # --- Year: current year, monthly breakdown ---
    year_start = now.replace(month=1, day=1, hour=0, minute=0, second=0, microsecond=0)
    year_end = now.replace(month=12, day=31, hour=23, minute=59, second=59, microsecond=999999)
    year_bills = scoped_bills(year_start, year_end)

    month_names = ["Jan", "Feb", "Mar", "Apr", "May", "Jun",
                   "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]
    year_buckets: dict[int, list] = {m: [] for m in range(1, 13)}
    for b in year_bills:
        year_buckets[b.paid_at.astimezone(timezone.utc).month].append(b)
    year_breakdown = [
        schemas.RevenueDataPoint(
            label=month_names[m - 1],
            total_sales=round(sum(b.total_amount for b in year_buckets[m]), 2),
            total_orders=len(year_buckets[m]),
            cash_total=round(sum(b.total_amount for b in year_buckets[m] if b.pay_type == "cash"), 2),
            qr_total=round(sum(b.total_amount for b in year_buckets[m] if b.pay_type == "qr"), 2),
        )
        for m in range(1, 13)
    ]

    return schemas.RevenueAnalyticsResponse(
        day=_build_revenue_period(day_bills, day_breakdown),
        week=_build_revenue_period(week_bills, week_breakdown),
        month=_build_revenue_period(month_bills, month_breakdown),
        year=_build_revenue_period(year_bills, year_breakdown),
    )
