# Restaurant Management System - Backend API

A comprehensive FastAPI-based backend for restaurant management with PostgreSQL and Docker.

## Features

- **Multi-role Authentication**: Admin, Staff, and Customer roles with JWT-based authentication
- **Floor & Table Management**: Organize tables across multiple floors
- **Menu Management**: Categories and menu items with availability tracking
- **Reservations**: Table booking with conflict checking
- **Order Management**: Complete order workflow with status tracking
- **Staff Requests**: Staff can request frequently asked menu items for admin review

## Tech Stack

- **Backend**: FastAPI
- **Database**: PostgreSQL 13
- **ORM**: SQLAlchemy
- **Authentication**: JWT (python-jose) + OAuth2
- **Password Hashing**: passlib with bcrypt
- **Containerization**: Docker + Docker Compose

## API Endpoints

### Authentication
- `POST /register` - Register new user
- `POST /token` - Login and get JWT token

### Floors (Admin only for CUD, Public for Read)
- `POST /floors` - Create floor
- `GET /floors` - List all floors
- `GET /floors/{id}` - Get floor details
- `PUT /floors/{id}` - Update floor
- `DELETE /floors/{id}` - Delete floor

### Tables (Admin only for CUD, Public for Read)
- `POST /tables` - Create table
- `GET /tables` - List all tables
- `GET /tables/{id}` - Get table details
- `PUT /tables/{id}` - Update table
- `DELETE /tables/{id}` - Delete table

### Categories (Admin only for CUD, Public for Read)
- `POST /categories` - Create category
- `GET /categories` - List all categories
- `PUT /categories/{id}` - Update category
- `DELETE /categories/{id}` - Delete category

### Menu Items (Admin only for CUD, Public for Read)
- `POST /menu-items` - Create menu item
- `GET /menu-items` - List menu items (optional: ?available_only=true)
- `GET /menu-items/{id}` - Get menu item details
- `PUT /menu-items/{id}` - Update menu item
- `PATCH /menu-items/{id}/availability` - Toggle availability
- `DELETE /menu-items/{id}` - Delete menu item

### Reservations (Public)
- `POST /reservations` - Book a table
- `GET /reservations` - List reservations (optional: ?table_id=1)
- `GET /reservations/{id}` - Get reservation details
- `DELETE /reservations/{id}` - Cancel reservation

### Orders (Staff/Admin only)
- `POST /orders` - Create order
- `GET /orders` - List orders (optional: ?table_id=1&status=pending)
- `GET /orders/{id}` - Get order details
- `PATCH /orders/{id}/status` - Update order status
- `DELETE /orders/{id}` - Delete order (Admin only)

### Staff Item Requests
- `POST /staff/request-item` - Request new menu item (Staff only)
- `GET /admin/item-requests` - View all item requests (Admin only)
- `DELETE /admin/item-requests/{id}` - Delete item request (Admin only)

## Quick Start

### Using Docker (Recommended)

1. Clone the repository and navigate to the project directory:
   ```bash
   cd restro-api
   ```

2. Start the services:
   ```bash
   docker-compose up --build
   ```

3. Access the API documentation at: **http://localhost:8000/docs**

### Manual Setup

1. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```

2. Set up PostgreSQL database and update DATABASE_URL in app/database.py

3. Run the application:
   ```bash
   uvicorn app.main:app --reload
   ```

## Database Schema

- **users**: User accounts with roles
- **floors**: Restaurant floors
- **tables**: Tables assigned to floors
- **categories**: Menu categories
- **menu_items**: Food/beverage items
- **item_requests**: Staff-requested items
- **reservations**: Table bookings
- **orders**: Customer orders
- **order_items**: Items in each order

## Security

- Passwords are hashed using bcrypt
- JWT tokens expire after 60 minutes
- Role-based access control for all endpoints
- For production, change SECRET_KEY in docker-compose.yml

## Default Credentials

After starting, register your first admin user via `/register` endpoint:

```json
{
  "username": "admin",
  "password": "your-secure-password",
  "role": "admin"
}
```

Then login via `/token` to get your JWT token for authenticated requests.
