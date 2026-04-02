# Restaurant Management System — Backend API

A multi-tenant FastAPI backend for restaurant/café management with PostgreSQL and Docker.

## Features

- **Multi-tenant Architecture**: Each café's data is fully isolated
- **3-tier Role System**: Super Admin, Cafe Admin, Staff
- **JWT Authentication**: Token-based auth with blocklist (logout support)
- **Café Management**: Super admin creates cafés with their admin in one request
- **Staff Management**: Cafe admins create and manage their own staff
- **Table & Floor Management**: Organize tables across floors (per café)
- **Menu Management**: Menu items with availability toggling (per café)
- **Order Management**: Full order lifecycle with item-level status tracking
- **Reservations**: Table booking with conflict detection
- **Bills & Payments**: Bill generation, cash/QR payment, daily summaries
- **Revenue Analytics**: Hourly, daily, weekly, monthly breakdowns
- **Audit History**: Every order action is logged automatically

## Tech Stack

- **Backend**: FastAPI
- **Database**: PostgreSQL
- **ORM**: SQLAlchemy
- **Authentication**: JWT (python-jose) + OAuth2 + bcrypt
- **Containerization**: Docker + Docker Compose

## Quick Start

```bash
# Start all services
docker-compose up --build

# Swagger UI
http://localhost:8000/docs

# Fresh reset (drops all data)
docker-compose down -v && docker-compose up --build
```

## Default Credentials

A `super_admin` is auto-seeded on first startup:

| Field | Value |
|-------|-------|
| username | `superadmin` |
| password | `super123` |

> Change this in production via the `SECRET_KEY` environment variable in `docker-compose.yml`.

## Roles

| Role | Who | Access |
|------|-----|--------|
| `super_admin` | Platform owner | Create/manage cafés, view all data |
| `cafe_admin` | Café owner | Manage their café's staff, tables, menu, orders |
| `staff` | Café employee | Create/manage orders, reservations, bills |

## API Overview

### Authentication
| Method | Path | Auth | Description |
|--------|------|------|-------------|
| POST | `/auth/login` | Public | Login, get JWT |
| POST | `/logout` | Any | Invalidate token |
| GET | `/profile` | Any | Get current user |

### Cafes
| Method | Path | Auth | Description |
|--------|------|------|-------------|
| POST | `/cafes` | super_admin | Create café + admin in one request |
| GET | `/cafes` | super_admin | List all cafés |
| PATCH | `/cafes/{id}/status` | super_admin | Toggle café active/inactive |

### Staff
| Method | Path | Auth | Description |
|--------|------|------|-------------|
| POST | `/staff` | cafe_admin | Create staff member |
| GET | `/staff` | cafe_admin | List staff (own café only) |
| PATCH | `/staff/{id}/status` | cafe_admin | Toggle staff active/inactive |
| DELETE | `/staff/{id}` | cafe_admin | Remove staff member |

### Floors
| Method | Path | Auth | Description |
|--------|------|------|-------------|
| POST | `/floors` | cafe_admin | Create floor |
| GET | `/floors` | staff | List floors (scoped to café) |
| GET | `/floors/{id}` | staff | Get floor |
| PUT | `/floors/{id}` | cafe_admin | Update floor |
| DELETE | `/floors/{id}` | cafe_admin | Delete floor |

### Tables
| Method | Path | Auth | Description |
|--------|------|------|-------------|
| POST | `/tables` | cafe_admin | Create table |
| GET | `/tables` | staff | List tables (scoped to café) |
| GET | `/tables/{id}` | staff | Get table |
| GET | `/tables/{id}/active-order` | staff | Get active order on table |
| PUT | `/tables/{id}` | cafe_admin | Update table |
| DELETE | `/tables/{id}` | cafe_admin | Delete table |

### Menu Items
| Method | Path | Auth | Description |
|--------|------|------|-------------|
| POST | `/menu-items` | cafe_admin | Create menu item |
| GET | `/menu-items` | staff | List items (`?available_only=true`) |
| GET | `/menu-items/{id}` | staff | Get item |
| PUT | `/menu-items/{id}` | cafe_admin | Update item |
| PATCH | `/menu-items/{id}/availability` | cafe_admin | Toggle availability |
| DELETE | `/menu-items/{id}` | cafe_admin | Delete item |

### Orders
| Method | Path | Auth | Description |
|--------|------|------|-------------|
| POST | `/orders` | staff | Create order (or add to existing active order) |
| GET | `/orders` | staff | List orders (`?table_id=&status=`) |
| GET | `/orders/{id}` | staff | Get order |
| POST | `/orders/{id}/items` | staff | Add items to order |
| PATCH | `/orders/{id}/items/{item_id}/status` | staff | Toggle item status |
| PATCH | `/orders/{id}/status` | staff | Update order status |
| POST | `/orders/{id}/transfer` | staff | Transfer order to another table |
| DELETE | `/orders/{id}` | cafe_admin | Delete order |

### Bills & Payments
| Method | Path | Auth | Description |
|--------|------|------|-------------|
| POST | `/orders/{id}/bill` | staff | Generate bill |
| GET | `/orders/{id}/bill` | staff | Get bill |
| POST | `/bills/{id}/pay` | staff | Mark as paid (cash/qr) |
| GET | `/bills` | staff | List bills (`?is_paid=&date=`) |
| GET | `/bills/daily-summary` | cafe_admin | Daily sales summary |

### History & Analytics
| Method | Path | Auth | Description |
|--------|------|------|-------------|
| GET | `/orders/{id}/history` | staff | Audit log for one order |
| GET | `/history` | cafe_admin | All events (`?order_id=&event_type=`) |
| GET | `/revenue` | cafe_admin | Revenue analytics (day/week/month/year) |

### Reservations
| Method | Path | Auth | Description |
|--------|------|------|-------------|
| POST | `/reservations` | staff | Book a table |
| GET | `/reservations` | staff | List (`?table_id=`) |
| GET | `/reservations/{id}` | staff | Get reservation |
| DELETE | `/reservations/{id}` | staff | Cancel reservation |

### Staff Item Requests
| Method | Path | Auth | Description |
|--------|------|------|-------------|
| POST | `/staff/request-item` | staff | Request new menu item |
| GET | `/admin/item-requests` | cafe_admin | View requests (sorted by count) |
| DELETE | `/admin/item-requests/{id}` | cafe_admin | Delete request |

## Database Schema

| Table | Purpose |
|-------|---------|
| `cafes` | Café accounts (multi-tenant root) |
| `users` | All users — super_admin, cafe_admin, staff |
| `floors` | Floors per café |
| `tables` | Tables per café |
| `menu_items` | Menu per café |
| `item_requests` | Staff-requested menu additions |
| `reservations` | Table bookings |
| `orders` | Customer orders (table/price snapshotted) |
| `order_items` | Line items per order |
| `order_history` | Audit log of all order events |
| `bills` | Generated bills and payment state |
| `token_blocklist` | Revoked JWT tokens |

## Security

- Passwords hashed with bcrypt
- JWT tokens expire after 60 minutes
- Logged-out tokens are blocklisted
- All data scoped by `cafe_id` — no cross-café leakage
- Inactive café blocks login for all its users
- Inactive user account blocks individual login
