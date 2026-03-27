# Restaurant Management System — API Guide

FastAPI + PostgreSQL + Docker backend for restaurant management.

**Base URL:** `http://localhost:8000`
**Interactive docs (Swagger):** `http://localhost:8000/docs`

---

## Quick Start

```bash
docker-compose up --build
```

> **Fresh database reset (after schema changes):**
> ```bash
> docker-compose down -v && docker-compose up --build
> ```

---

## Authentication

### Register a user
```bash
curl -X POST "http://localhost:8000/register" \
  -H "Content-Type: application/json" \
  -d '{"username": "admin", "password": "admin123", "role": "admin"}'
```

### Login
```bash
curl -X POST "http://localhost:8000/login" \
  -H "Content-Type: application/x-www-form-urlencoded" \
  -d "username=admin&password=admin123"
```
Save the `access_token`. Use it as `Authorization: Bearer <token>` on all protected routes.

### Roles
| Role | Access |
|------|--------|
| `superadmin` | Everything |
| `admin` | Everything (floor/table/menu management + orders) |
| `staff` | Orders, item requests |

---

## Floors (Admin)

```bash
# Create
curl -X POST "http://localhost:8000/floors" \
  -H "Authorization: Bearer TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"name": "Ground Floor"}'

# List all (public)
curl "http://localhost:8000/floors"

# Get one (public)
curl "http://localhost:8000/floors/1"

# Update
curl -X PUT "http://localhost:8000/floors/1" \
  -H "Authorization: Bearer TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"name": "Rooftop"}'

# Delete
curl -X DELETE "http://localhost:8000/floors/1" \
  -H "Authorization: Bearer TOKEN"
```

---

## Tables (Admin)

Each table has an `id` (primary key), `table_number` (integer), and `table_name` (display name). Tables are independent — no floor dependency.

```bash
# Create
curl -X POST "http://localhost:8000/tables" \
  -H "Authorization: Bearer TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"table_number": 5, "table_name": "Window Table"}'

# List all (public)
curl "http://localhost:8000/tables"

# Get one (public)
curl "http://localhost:8000/tables/1"

# Update
curl -X PUT "http://localhost:8000/tables/1" \
  -H "Authorization: Bearer TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"table_name": "Corner Table"}'

# Delete
curl -X DELETE "http://localhost:8000/tables/1" \
  -H "Authorization: Bearer TOKEN"
```

---

## Menu Items (Admin)

```bash
# Create
curl -X POST "http://localhost:8000/menu-items" \
  -H "Authorization: Bearer TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"name": "Butter Chicken", "price": 12.99, "is_available": true}'

# List all (public) — add ?available_only=true to filter
curl "http://localhost:8000/menu-items?available_only=true"

# Get one (public)
curl "http://localhost:8000/menu-items/1"

# Update name or price
curl -X PUT "http://localhost:8000/menu-items/1" \
  -H "Authorization: Bearer TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"name": "Butter Chicken", "price": 13.99}'

# Toggle availability (admin dashboard)
curl -X PATCH "http://localhost:8000/menu-items/1/availability?is_available=false" \
  -H "Authorization: Bearer TOKEN"

# Delete
curl -X DELETE "http://localhost:8000/menu-items/1" \
  -H "Authorization: Bearer TOKEN"
```

---

## Orders (Staff)

### Order statuses
`ordering` → `placed` → `completed` → `cancelled`

### Item statuses
`ordered` → `placed`

---

### Create an order

When a customer sits down, create an order for that table. Item `name` and `price` are snapshotted automatically from the menu.

```bash
curl -X POST "http://localhost:8000/orders" \
  -H "Authorization: Bearer STAFF_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "table_id": 1,
    "items": [
      {"menu_item_id": 1, "quantity": 2},
      {"menu_item_id": 3, "quantity": 1}
    ]
  }'
```

**Response includes:** `id`, `tableNumber`, `tableName` (floor name), `status`, `totalAmount`, `items[]`, `createdAt`

> A table cannot have two active orders at the same time.

---

### Add more items to an existing order

Customer orders additional dishes after the initial order.

```bash
curl -X POST "http://localhost:8000/orders/1/items" \
  -H "Authorization: Bearer STAFF_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "items": [
      {"menu_item_id": 4, "quantity": 1}
    ]
  }'
```

> Only works if the order status is `ordering` or `placed`.

---

### Toggle an item's status (ordered → placed)

Staff marks individual items as sent to the kitchen.

```bash
curl -X PATCH "http://localhost:8000/orders/1/items/3/status" \
  -H "Authorization: Bearer STAFF_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"status": "placed"}'
```

`status` values: `ordered` | `placed`

---

### Update order status

```bash
curl -X PATCH "http://localhost:8000/orders/1/status" \
  -H "Authorization: Bearer STAFF_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"status": "placed"}'
```

`status` values: `ordering` | `placed` | `completed` | `cancelled`

> Cannot update a `completed` or `cancelled` order.

---

### Transfer order to another table

Move a customer's order to a different table.

```bash
curl -X POST "http://localhost:8000/orders/1/transfer" \
  -H "Authorization: Bearer STAFF_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"target_table_id": 5}'
```

**Conditions:**
- Source order must be active (`ordering` or `placed`)
- Target table must have no active order

---

### List / get orders

```bash
# All orders
curl "http://localhost:8000/orders" \
  -H "Authorization: Bearer STAFF_TOKEN"

# Filter by table
curl "http://localhost:8000/orders?table_id=1" \
  -H "Authorization: Bearer STAFF_TOKEN"

# Filter by status
curl "http://localhost:8000/orders?status=ordering" \
  -H "Authorization: Bearer STAFF_TOKEN"

# Get one order
curl "http://localhost:8000/orders/1" \
  -H "Authorization: Bearer STAFF_TOKEN"
```

---

## Bills & Payments (Staff)

### Generate a bill

Creates a bill snapshot from the current order. Can only be done once per order.

```bash
curl -X POST "http://localhost:8000/orders/1/bill" \
  -H "Authorization: Bearer STAFF_TOKEN"
```

**Response matches `OrderBill` model:** `orderId`, `tableNumber`, `tableName`, `items[]`, `totalAmount`, `generatedAt`, `isPaid`

---

### Get existing bill

```bash
curl "http://localhost:8000/orders/1/bill" \
  -H "Authorization: Bearer STAFF_TOKEN"
```

---

### Mark bill as paid

Sets `isPaid = true`, records `paidAt`, and automatically moves order status to `completed`.

```bash
curl -X POST "http://localhost:8000/bills/1/pay" \
  -H "Authorization: Bearer STAFF_TOKEN"
```

---

## Order History (Audit Log)

All key actions are automatically logged — no manual input needed.

### Events logged automatically
| Event | Trigger |
|-------|---------|
| `order_created` | New order created |
| `item_added` | Items added to existing order |
| `item_status_changed` | Item toggled ordered → placed |
| `status_changed` | Order status updated |
| `order_cancelled` | Order status set to cancelled |
| `table_transferred` | Order moved to another table |
| `bill_generated` | Bill created |
| `payment_received` | Bill marked as paid |

### Get history for a specific order
```bash
curl "http://localhost:8000/orders/1/history" \
  -H "Authorization: Bearer STAFF_TOKEN"
```

### Get all history (Admin)
```bash
# All events
curl "http://localhost:8000/history" \
  -H "Authorization: Bearer ADMIN_TOKEN"

# Filter by order
curl "http://localhost:8000/history?order_id=1" \
  -H "Authorization: Bearer ADMIN_TOKEN"

# Filter by event type
curl "http://localhost:8000/history?event_type=table_transferred" \
  -H "Authorization: Bearer ADMIN_TOKEN"
```

---

## Reservations (Public)

```bash
# Book a table
curl -X POST "http://localhost:8000/reservations" \
  -H "Content-Type: application/json" \
  -d '{
    "table_id": 1,
    "customer_name": "John Doe",
    "start_time": "2026-04-01T18:00:00",
    "end_time": "2026-04-01T20:00:00"
  }'

# List (filter by table: ?table_id=1)
curl "http://localhost:8000/reservations"

# Cancel
curl -X DELETE "http://localhost:8000/reservations/1"
```

> Overlapping time slots for the same table are rejected automatically.

---

## Staff Item Requests

Staff can request menu items for admin review.

```bash
# Request new item
curl -X POST "http://localhost:8000/staff/request-item" \
  -H "Authorization: Bearer STAFF_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"item_name": "Vegan Burger", "description": "Customers keep asking for it"}'

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
| POST | `/register` | Public | Register user |
| POST | `/login` | Public | Login, get JWT |

### Floors
| Method | Path | Auth | Description |
|--------|------|------|-------------|
| POST | `/floors` | Admin | Create floor |
| GET | `/floors` | Public | List all floors |
| GET | `/floors/{id}` | Public | Get floor |
| PUT | `/floors/{id}` | Admin | Update floor |
| DELETE | `/floors/{id}` | Admin | Delete floor |

### Tables
| Method | Path | Auth | Description |
|--------|------|------|-------------|
| POST | `/tables` | Admin | Create table (`table_number`, `table_name`) |
| GET | `/tables` | Public | List tables |
| GET | `/tables/{id}` | Public | Get table |
| PUT | `/tables/{id}` | Admin | Update table |
| DELETE | `/tables/{id}` | Admin | Delete table |

### Menu Items
| Method | Path | Auth | Description |
|--------|------|------|-------------|
| POST | `/menu-items` | Admin | Create item |
| GET | `/menu-items` | Public | List items (`?available_only=true`) |
| GET | `/menu-items/{id}` | Public | Get item |
| PUT | `/menu-items/{id}` | Admin | Update name / price |
| PATCH | `/menu-items/{id}/availability` | Admin | Toggle availability |
| DELETE | `/menu-items/{id}` | Admin | Delete item |

### Orders
| Method | Path | Auth | Description |
|--------|------|------|-------------|
| POST | `/orders` | Staff | Create order |
| GET | `/orders` | Staff | List orders (`?table_id=`, `?status=`) |
| GET | `/orders/{id}` | Staff | Get order |
| POST | `/orders/{id}/items` | Staff | Add items to order |
| PATCH | `/orders/{id}/items/{item_id}/status` | Staff | Toggle item status |
| PATCH | `/orders/{id}/status` | Staff | Update order status |
| POST | `/orders/{id}/transfer` | Staff | Transfer to another table |
| DELETE | `/orders/{id}` | Admin | Delete order |

### History
| Method | Path | Auth | Description |
|--------|------|------|-------------|
| GET | `/orders/{id}/history` | Staff | History for one order |
| GET | `/history` | Admin | All events (`?order_id=`, `?event_type=`) |

### Bills & Payments
| Method | Path | Auth | Description |
|--------|------|------|-------------|
| POST | `/orders/{id}/bill` | Staff | Generate bill |
| GET | `/orders/{id}/bill` | Staff | Get bill |
| POST | `/bills/{id}/pay` | Staff | Mark as paid |

### Reservations
| Method | Path | Auth | Description |
|--------|------|------|-------------|
| POST | `/reservations` | Public | Book table |
| GET | `/reservations` | Public | List (`?table_id=`) |
| GET | `/reservations/{id}` | Public | Get reservation |
| DELETE | `/reservations/{id}` | Public | Cancel |

### Staff Requests
| Method | Path | Auth | Description |
|--------|------|------|-------------|
| POST | `/staff/request-item` | Staff | Request new item |
| GET | `/admin/item-requests` | Admin | View requests |
| DELETE | `/admin/item-requests/{id}` | Admin | Delete request |

---

## Database Tables

| Table | Purpose |
|-------|---------|
| `users` | Accounts with roles |
| `floors` | Restaurant floors/sections |
| `tables` | Tables per floor |
| `menu_items` | Food & drink items (added by admin) |
| `item_requests` | Staff-requested additions |
| `reservations` | Table bookings |
| `orders` | Customer orders (with table/price snapshots) |
| `order_items` | Line items per order (name/price snapshotted) |
| `order_history` | Audit log of all order events |
| `bills` | Generated bills and payment state |

---

## Development Commands

```bash
# Start
docker-compose up --build

# View API logs
docker-compose logs -f backend

# Connect to DB directly
docker exec -it restro-api-db-1 psql -U user -d restaurant_db

# Stop
docker-compose down

# Full reset (drops all data)
docker-compose down -v
```

---

## Tech Stack

- **FastAPI** — API framework
- **PostgreSQL** — Database
- **SQLAlchemy** — ORM
- **JWT + OAuth2** — Authentication
- **bcrypt** — Password hashing
- **Docker Compose** — Containerization
