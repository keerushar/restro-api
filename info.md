# Restaurant Management System — API Guide

FastAPI + PostgreSQL + Docker | Multi-tenant café management backend.

**Base URL:** `http://localhost:8000`
**Swagger UI:** `http://localhost:8000/docs`

---

## Quick Start

```bash
docker-compose up --build
```

> **Fresh reset:** `docker-compose down -v && docker-compose up --build`

---

## Roles & Permissions

| Role | `super_admin` | `cafe_admin` | `staff` |
|------|:---:|:---:|:---:|
| Create / manage cafés | ✅ | ❌ | ❌ |
| Toggle café active status | ✅ | ❌ | ❌ |
| Create staff | ❌ | ✅ | ❌ |
| Toggle staff active status | ❌ | ✅ | ❌ |
| Manage floors / tables / menu | ❌ | ✅ | ❌ |
| Orders / reservations / bills | ❌ | ✅ | ✅ |
| View analytics / history | ❌ | ✅ | ❌ |

---

## Authentication

### Default super_admin (auto-seeded on startup)
```
username: superadmin
password: super123
```

### Login
```bash
curl -X POST "http://localhost:8000/auth/login" \
  -H "Content-Type: application/x-www-form-urlencoded" \
  -d "username=superadmin&password=super123"
```

**Response:**
```json
{ "access_token": "eyJ...", "token_type": "bearer" }
```

Use the token on all protected routes:
```
Authorization: Bearer <token>
```

**Login blocks if:**
- User `is_active = false` → `403 Account is inactive`
- Café `is_active = false` → `403 Cafe is inactive`

### Get profile
```bash
curl "http://localhost:8000/profile" \
  -H "Authorization: Bearer TOKEN"
```

### Logout
```bash
curl -X POST "http://localhost:8000/logout" \
  -H "Authorization: Bearer TOKEN"
```

---

## Cafes

### Create café + admin (one request)
```bash
curl -X POST "http://localhost:8000/cafes" \
  -H "Authorization: Bearer SUPERADMIN_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "cafe_name": "The Coffee House",
    "cafe_username": "coffee_house",
    "admin": {
      "name": "John Doe",
      "username": "john_admin",
      "password": "secret123"
    }
  }'
```

**Response:**
```json
{
  "cafe": {
    "id": "uuid",
    "name": "The Coffee House",
    "username": "coffee_house",
    "is_active": true,
    "created_at": "2026-03-31T10:00:00Z"
  },
  "admin": {
    "id": "uuid",
    "name": "John Doe",
    "username": "john_admin",
    "role": "cafe_admin",
    "is_active": true,
    "cafe_id": "uuid",
    "created_at": "2026-03-31T10:00:00Z"
  }
}
```

### List all cafés
```bash
curl "http://localhost:8000/cafes" \
  -H "Authorization: Bearer SUPERADMIN_TOKEN"
```

### Toggle café active/inactive
```bash
# Deactivate — blocks all users of this café from logging in
curl -X PATCH "http://localhost:8000/cafes/{cafe_id}/status" \
  -H "Authorization: Bearer SUPERADMIN_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{ "is_active": false }'

# Reactivate
curl -X PATCH "http://localhost:8000/cafes/{cafe_id}/status" \
  -H "Authorization: Bearer SUPERADMIN_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{ "is_active": true }'
```

---

## Staff

### Create staff
```bash
curl -X POST "http://localhost:8000/staff" \
  -H "Authorization: Bearer ADMIN_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "name": "Jane Smith",
    "username": "jane_staff",
    "password": "pass123",
    "is_active": true
  }'
```

Staff is automatically assigned to the calling admin's café.

### List staff
```bash
curl "http://localhost:8000/staff" \
  -H "Authorization: Bearer ADMIN_TOKEN"
```

### Toggle staff active/inactive
```bash
curl -X PATCH "http://localhost:8000/staff/{staff_id}/status" \
  -H "Authorization: Bearer ADMIN_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{ "is_active": false }'
```

### Delete staff
```bash
curl -X DELETE "http://localhost:8000/staff/{staff_id}" \
  -H "Authorization: Bearer ADMIN_TOKEN"
```

---

## Floors

```bash
# Create
curl -X POST "http://localhost:8000/floors" \
  -H "Authorization: Bearer ADMIN_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{ "name": "Ground Floor" }'

# List (scoped to caller's café)
curl "http://localhost:8000/floors" \
  -H "Authorization: Bearer TOKEN"

# Get one
curl "http://localhost:8000/floors/1" \
  -H "Authorization: Bearer TOKEN"

# Update
curl -X PUT "http://localhost:8000/floors/1" \
  -H "Authorization: Bearer ADMIN_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{ "name": "Rooftop" }'

# Delete
curl -X DELETE "http://localhost:8000/floors/1" \
  -H "Authorization: Bearer ADMIN_TOKEN"
```

---

## Tables

```bash
# Create
curl -X POST "http://localhost:8000/tables" \
  -H "Authorization: Bearer ADMIN_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{ "table_number": 5, "table_name": "Window Table" }'

# List
curl "http://localhost:8000/tables" \
  -H "Authorization: Bearer TOKEN"

# Get one
curl "http://localhost:8000/tables/1" \
  -H "Authorization: Bearer TOKEN"

# Get active order on a table
curl "http://localhost:8000/tables/1/active-order" \
  -H "Authorization: Bearer TOKEN"

# Update
curl -X PUT "http://localhost:8000/tables/1" \
  -H "Authorization: Bearer ADMIN_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{ "table_name": "Corner Table" }'

# Delete
curl -X DELETE "http://localhost:8000/tables/1" \
  -H "Authorization: Bearer ADMIN_TOKEN"
```

---

## Menu Items

```bash
# Create
curl -X POST "http://localhost:8000/menu-items" \
  -H "Authorization: Bearer ADMIN_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{ "name": "Butter Chicken", "price": 12.99, "is_available": true }'

# List (add ?available_only=true to filter)
curl "http://localhost:8000/menu-items" \
  -H "Authorization: Bearer TOKEN"

# Get one
curl "http://localhost:8000/menu-items/1" \
  -H "Authorization: Bearer TOKEN"

# Update
curl -X PUT "http://localhost:8000/menu-items/1" \
  -H "Authorization: Bearer ADMIN_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{ "name": "Butter Chicken", "price": 13.99 }'

# Toggle availability
curl -X PATCH "http://localhost:8000/menu-items/1/availability?is_available=false" \
  -H "Authorization: Bearer ADMIN_TOKEN"

# Delete
curl -X DELETE "http://localhost:8000/menu-items/1" \
  -H "Authorization: Bearer ADMIN_TOKEN"
```

---

## Orders

### Order statuses: `pending` → `completed`
### Item statuses: `ordered` → `placed` | `cancelled`

### Create order
If a table already has an active order, items are added to it automatically.
```bash
curl -X POST "http://localhost:8000/orders" \
  -H "Authorization: Bearer STAFF_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "table_id": 1,
    "items": [
      { "menu_item_id": 1, "quantity": 2 },
      { "menu_item_id": 3, "quantity": 1 }
    ]
  }'
```

### Add items to existing order
```bash
curl -X POST "http://localhost:8000/orders/1/items" \
  -H "Authorization: Bearer STAFF_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{ "items": [{ "menu_item_id": 4, "quantity": 1 }] }'
```

### Toggle item status
```bash
curl -X PATCH "http://localhost:8000/orders/1/items/3/status" \
  -H "Authorization: Bearer STAFF_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{ "status": "placed" }'
```

### Update order status
```bash
curl -X PATCH "http://localhost:8000/orders/1/status" \
  -H "Authorization: Bearer STAFF_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{ "status": "completed" }'
```

### Transfer order to another table
```bash
curl -X POST "http://localhost:8000/orders/1/transfer" \
  -H "Authorization: Bearer STAFF_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{ "target_table_id": 5 }'
```

### List / get orders
```bash
curl "http://localhost:8000/orders" -H "Authorization: Bearer STAFF_TOKEN"
curl "http://localhost:8000/orders?table_id=1" -H "Authorization: Bearer STAFF_TOKEN"
curl "http://localhost:8000/orders?status=pending" -H "Authorization: Bearer STAFF_TOKEN"
curl "http://localhost:8000/orders/1" -H "Authorization: Bearer STAFF_TOKEN"
```

### Delete order (admin only)
```bash
curl -X DELETE "http://localhost:8000/orders/1" \
  -H "Authorization: Bearer ADMIN_TOKEN"
```

---

## Bills & Payments

### Generate bill
```bash
curl -X POST "http://localhost:8000/orders/1/bill" \
  -H "Authorization: Bearer STAFF_TOKEN"
```

### Get bill
```bash
curl "http://localhost:8000/orders/1/bill" \
  -H "Authorization: Bearer STAFF_TOKEN"
```

### Pay bill
`pay_type`: `cash` | `qr`
```bash
curl -X POST "http://localhost:8000/bills/1/pay" \
  -H "Authorization: Bearer STAFF_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{ "pay_type": "cash" }'
```

### List all bills
```bash
curl "http://localhost:8000/bills" -H "Authorization: Bearer STAFF_TOKEN"
curl "http://localhost:8000/bills?is_paid=true" -H "Authorization: Bearer STAFF_TOKEN"
curl "http://localhost:8000/bills?date=2026-03-31" -H "Authorization: Bearer STAFF_TOKEN"
```

### Daily sales summary (admin)
```bash
curl "http://localhost:8000/bills/daily-summary" \
  -H "Authorization: Bearer ADMIN_TOKEN"

# Specific date
curl "http://localhost:8000/bills/daily-summary?date=2026-03-31" \
  -H "Authorization: Bearer ADMIN_TOKEN"
```

---

## Order History

### History for one order
```bash
curl "http://localhost:8000/orders/1/history" \
  -H "Authorization: Bearer STAFF_TOKEN"
```

### All history (admin)
```bash
curl "http://localhost:8000/history" -H "Authorization: Bearer ADMIN_TOKEN"
curl "http://localhost:8000/history?order_id=1" -H "Authorization: Bearer ADMIN_TOKEN"
curl "http://localhost:8000/history?event_type=payment_received" -H "Authorization: Bearer ADMIN_TOKEN"
```

**Event types:** `order_created`, `item_added`, `item_status_changed`, `status_changed`, `table_transferred`, `bill_generated`, `payment_received`

---

## Revenue Analytics

```bash
curl "http://localhost:8000/revenue" \
  -H "Authorization: Bearer ADMIN_TOKEN"
```

Returns breakdown for `day` (hourly), `week` (daily), `month` (daily), `year` (monthly).

---

## Reservations

```bash
# Book a table
curl -X POST "http://localhost:8000/reservations" \
  -H "Authorization: Bearer STAFF_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "table_id": 1,
    "customer_name": "John Doe",
    "start_time": "2026-04-01T18:00:00",
    "end_time": "2026-04-01T20:00:00"
  }'

# List (filter by table: ?table_id=1)
curl "http://localhost:8000/reservations" -H "Authorization: Bearer STAFF_TOKEN"

# Get one
curl "http://localhost:8000/reservations/1" -H "Authorization: Bearer STAFF_TOKEN"

# Cancel
curl -X DELETE "http://localhost:8000/reservations/1" \
  -H "Authorization: Bearer STAFF_TOKEN"
```

> Overlapping time slots for the same table are rejected automatically.

---

## Staff Item Requests

```bash
# Request new item
curl -X POST "http://localhost:8000/staff/request-item" \
  -H "Authorization: Bearer STAFF_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{ "item_name": "Vegan Burger", "description": "Customers keep asking for it" }'

# Admin: view all requests (sorted by request count)
curl "http://localhost:8000/admin/item-requests" \
  -H "Authorization: Bearer ADMIN_TOKEN"

# Admin: delete a request
curl -X DELETE "http://localhost:8000/admin/item-requests/1" \
  -H "Authorization: Bearer ADMIN_TOKEN"
```

---

## Full Endpoint Reference

### Auth
| Method | Path | Auth | Description |
|--------|------|------|-------------|
| POST | `/auth/login` | Public | Login, get JWT |
| POST | `/logout` | Any | Invalidate token |
| GET | `/profile` | Any | Current user info |

### Cafes
| Method | Path | Auth | Description |
|--------|------|------|-------------|
| POST | `/cafes` | super_admin | Create café + admin |
| GET | `/cafes` | super_admin | List all cafés |
| PATCH | `/cafes/{id}/status` | super_admin | Toggle active/inactive |

### Staff
| Method | Path | Auth | Description |
|--------|------|------|-------------|
| POST | `/staff` | cafe_admin | Create staff |
| GET | `/staff` | cafe_admin | List staff |
| PATCH | `/staff/{id}/status` | cafe_admin | Toggle active/inactive |
| DELETE | `/staff/{id}` | cafe_admin | Remove staff |

### Floors
| Method | Path | Auth | Description |
|--------|------|------|-------------|
| POST | `/floors` | cafe_admin | Create floor |
| GET | `/floors` | staff | List floors |
| GET | `/floors/{id}` | staff | Get floor |
| PUT | `/floors/{id}` | cafe_admin | Update floor |
| DELETE | `/floors/{id}` | cafe_admin | Delete floor |

### Tables
| Method | Path | Auth | Description |
|--------|------|------|-------------|
| POST | `/tables` | cafe_admin | Create table |
| GET | `/tables` | staff | List tables |
| GET | `/tables/{id}` | staff | Get table |
| GET | `/tables/{id}/active-order` | staff | Active order on table |
| PUT | `/tables/{id}` | cafe_admin | Update table |
| DELETE | `/tables/{id}` | cafe_admin | Delete table |

### Menu Items
| Method | Path | Auth | Description |
|--------|------|------|-------------|
| POST | `/menu-items` | cafe_admin | Create item |
| GET | `/menu-items` | staff | List items (`?available_only=true`) |
| GET | `/menu-items/{id}` | staff | Get item |
| PUT | `/menu-items/{id}` | cafe_admin | Update item |
| PATCH | `/menu-items/{id}/availability` | cafe_admin | Toggle availability |
| DELETE | `/menu-items/{id}` | cafe_admin | Delete item |

### Orders
| Method | Path | Auth | Description |
|--------|------|------|-------------|
| POST | `/orders` | staff | Create order |
| GET | `/orders` | staff | List orders |
| GET | `/orders/{id}` | staff | Get order |
| POST | `/orders/{id}/items` | staff | Add items |
| PATCH | `/orders/{id}/items/{item_id}/status` | staff | Toggle item status |
| PATCH | `/orders/{id}/status` | staff | Update order status |
| POST | `/orders/{id}/transfer` | staff | Transfer to another table |
| DELETE | `/orders/{id}` | cafe_admin | Delete order |

### Bills & Payments
| Method | Path | Auth | Description |
|--------|------|------|-------------|
| POST | `/orders/{id}/bill` | staff | Generate bill |
| GET | `/orders/{id}/bill` | staff | Get bill |
| POST | `/bills/{id}/pay` | staff | Mark as paid |
| GET | `/bills` | staff | List bills |
| GET | `/bills/daily-summary` | cafe_admin | Daily sales summary |

### History & Analytics
| Method | Path | Auth | Description |
|--------|------|------|-------------|
| GET | `/orders/{id}/history` | staff | Order audit log |
| GET | `/history` | cafe_admin | All events |
| GET | `/revenue` | cafe_admin | Revenue analytics |

### Reservations
| Method | Path | Auth | Description |
|--------|------|------|-------------|
| POST | `/reservations` | staff | Book table |
| GET | `/reservations` | staff | List (`?table_id=`) |
| GET | `/reservations/{id}` | staff | Get reservation |
| DELETE | `/reservations/{id}` | staff | Cancel |

### Staff Item Requests
| Method | Path | Auth | Description |
|--------|------|------|-------------|
| POST | `/staff/request-item` | staff | Request new item |
| GET | `/admin/item-requests` | cafe_admin | View requests |
| DELETE | `/admin/item-requests/{id}` | cafe_admin | Delete request |

---

## Database Tables

| Table | Purpose |
|-------|---------|
| `cafes` | Café accounts with `is_active` flag |
| `users` | All users (super_admin / cafe_admin / staff) with `is_active` flag |
| `floors` | Floors per café |
| `tables` | Tables per café |
| `menu_items` | Menu per café |
| `item_requests` | Staff-requested menu additions |
| `reservations` | Table bookings |
| `orders` | Orders (table/price snapshotted at creation) |
| `order_items` | Line items per order |
| `order_history` | Audit log |
| `bills` | Bills and payment state |
| `token_blocklist` | Revoked JWT tokens |

---

## Development Commands

```bash
# Start
docker-compose up --build

# View API logs
docker-compose logs -f backend

# Connect to DB
docker exec -it restro-api-db-1 psql -U user -d restaurant_db

# Stop
docker-compose down

# Full reset (drops all data)
docker-compose down -v
```
