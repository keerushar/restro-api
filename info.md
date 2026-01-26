# Restaurant Management System - API Usage Guide

A comprehensive FastAPI-based backend for restaurant management with PostgreSQL and Docker.

## Quick Start

### 1. Start the Application

```bash
docker-compose up --build
```

The API will be available at: **http://localhost:8000**

Interactive API documentation (Swagger UI): **http://localhost:8000/docs**

### 2. Register Your First Admin User

```bash
curl -X POST "http://localhost:8000/register" \
  -H "Content-Type: application/json" \
  -d '{
    "username": "admin",
    "password": "admin123",
    "role": "admin"
  }'
```

### 3. Login to Get JWT Token

```bash
curl -X POST "http://localhost:8000/token" \
  -H "Content-Type: application/x-www-form-urlencoded" \
  -d "username=admin&password=admin123"
```

Save the `access_token` from the response. You'll need it for authenticated requests.

---

## User Roles

- **admin** - Full access to all endpoints (floors, tables, menu management, view orders)
- **staff** - Can create orders, request menu items, view menu
- **customer** - Can view floors/menu, make reservations

---

## Common API Workflows

### Setting Up Restaurant Structure (Admin)

#### 1. Create Floors
```bash
curl -X POST "http://localhost:8000/floors" \
  -H "Authorization: Bearer YOUR_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"name": "Ground Floor"}'
```

#### 2. Add Tables to Floor
```bash
curl -X POST "http://localhost:8000/tables" \
  -H "Authorization: Bearer YOUR_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "floor_id": 1,
    "table_number": "T1",
    "capacity": 4
  }'
```

#### 3. Create Menu Categories
```bash
curl -X POST "http://localhost:8000/categories" \
  -H "Authorization: Bearer YOUR_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"name": "Breakfast"}'
```

#### 4. Add Menu Items
```bash
curl -X POST "http://localhost:8000/menu-items" \
  -H "Authorization: Bearer YOUR_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "name": "Pancakes",
    "price": 8.99,
    "category_id": 1,
    "is_available": true
  }'
```

### Customer Operations

#### View Available Floors and Tables
```bash
curl -X GET "http://localhost:8000/floors"
```

#### View Menu (Available Items Only)
```bash
curl -X GET "http://localhost:8000/menu-items?available_only=true"
```

#### Make a Reservation
```bash
curl -X POST "http://localhost:8000/reservations" \
  -H "Content-Type: application/json" \
  -d '{
    "table_id": 1,
    "customer_name": "John Doe",
    "start_time": "2026-01-26T18:00:00",
    "end_time": "2026-01-26T20:00:00"
  }'
```

### Staff Operations

#### Create an Order
```bash
curl -X POST "http://localhost:8000/orders" \
  -H "Authorization: Bearer STAFF_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "table_id": 1,
    "items": [
      {"menu_item_id": 1, "quantity": 2},
      {"menu_item_id": 2, "quantity": 1}
    ]
  }'
```

#### Update Order Status
```bash
curl -X PATCH "http://localhost:8000/orders/1/status" \
  -H "Authorization: Bearer STAFF_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"status": "completed"}'
```

#### Request New Menu Item
```bash
curl -X POST "http://localhost:8000/staff/request-item" \
  -H "Authorization: Bearer STAFF_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "item_name": "Vegan Burger",
    "description": "Multiple customers have asked for this"
  }'
```

### Admin Operations

#### View Staff Item Requests
```bash
curl -X GET "http://localhost:8000/admin/item-requests" \
  -H "Authorization: Bearer ADMIN_TOKEN"
```

#### Toggle Menu Item Availability
```bash
curl -X PATCH "http://localhost:8000/menu-items/1/availability?is_available=false" \
  -H "Authorization: Bearer ADMIN_TOKEN"
```

#### View All Orders
```bash
curl -X GET "http://localhost:8000/orders" \
  -H "Authorization: Bearer ADMIN_TOKEN"
```

Filter by table: `?table_id=1`
Filter by status: `?status=pending`

---

## API Endpoint Summary

### Authentication
- `POST /register` - Register new user (public)
- `POST /token` - Login (public)

### Floors (Admin CUD, Public Read)
- `POST /floors` - Create floor
- `GET /floors` - List all floors with tables
- `GET /floors/{id}` - Get specific floor
- `PUT /floors/{id}` - Update floor
- `DELETE /floors/{id}` - Delete floor

### Tables (Admin CUD, Public Read)
- `POST /tables` - Create table
- `GET /tables` - List all tables
- `GET /tables/{id}` - Get specific table
- `PUT /tables/{id}` - Update table
- `DELETE /tables/{id}` - Delete table

### Categories (Admin CUD, Public Read)
- `POST /categories` - Create category
- `GET /categories` - List all categories
- `PUT /categories/{id}` - Update category
- `DELETE /categories/{id}` - Delete category

### Menu Items (Admin CUD, Public Read)
- `POST /menu-items` - Create menu item
- `GET /menu-items` - List menu items
- `GET /menu-items/{id}` - Get specific item
- `PUT /menu-items/{id}` - Update menu item
- `PATCH /menu-items/{id}/availability` - Toggle availability
- `DELETE /menu-items/{id}` - Delete menu item

### Reservations (Public Create/Read/Delete)
- `POST /reservations` - Book a table
- `GET /reservations` - List reservations
- `GET /reservations/{id}` - Get specific reservation
- `DELETE /reservations/{id}` - Cancel reservation

### Orders (Staff/Admin)
- `POST /orders` - Create order (staff+)
- `GET /orders` - List orders (staff+)
- `GET /orders/{id}` - Get specific order (staff+)
- `PATCH /orders/{id}/status` - Update status (staff+)
- `DELETE /orders/{id}` - Delete order (admin only)

### Staff Requests
- `POST /staff/request-item` - Request new item (staff+)
- `GET /admin/item-requests` - View requests (admin only)
- `DELETE /admin/item-requests/{id}` - Delete request (admin only)

---

## Database Schema

**9 Tables:**
- `users` - User accounts with roles
- `floors` - Restaurant floors
- `tables` - Tables assigned to floors
- `categories` - Menu categories
- `menu_items` - Food/beverage items
- `item_requests` - Staff-requested items
- `reservations` - Table bookings
- `orders` - Customer orders
- `order_items` - Items in each order

---

## Features

✅ Multi-role authentication (Admin/Staff/Customer)
✅ JWT-based authorization
✅ Complete CRUD for all entities
✅ Reservation conflict checking
✅ Menu item availability tracking
✅ Staff item request system with count aggregation
✅ Order management with status tracking
✅ Cascade deletion for related entities
✅ Interactive API documentation
✅ Docker containerization

---

## Tech Stack

- **Backend**: FastAPI
- **Database**: PostgreSQL (latest)
- **ORM**: SQLAlchemy
- **Auth**: JWT with OAuth2
- **Password Hashing**: bcrypt
- **Container**: Docker + Docker Compose

---

## Environment Variables

Set in `docker-compose.yml`:
- `DATABASE_URL` - PostgreSQL connection string
- `SECRET_KEY` - JWT signing key (change in production!)
- `POSTGRES_USER` - Database user
- `POSTGRES_PASSWORD` - Database password
- `POSTGRES_DB` - Database name

---

## Development

Access PostgreSQL directly:
```bash
docker exec -it restro-api-db-1 psql -U user -d restaurant_db
```

View logs:
```bash
docker-compose logs -f backend
```

Stop services:
```bash
docker-compose down
```

Remove volumes (fresh start):
```bash
docker-compose down -v
```