# Stremet Hackathon - Steel Order Management System

A Django web application for managing steel manufacturing orders, tracking production stages, and providing real-time order status to customers.

## Features

- **Staff Dashboard** - Unified panel for administrators and manufacturers to create, search, and manage orders.
- **Manufacturing Flowchart Tracking** - Five-step production pipeline (Programming, Cutting, Forming, Joining, Delivery) with per-item status updates via AJAX.
- **Customer Portal** - Customers can look up their order by ID and view the current production status.
- **Role-Based Access** - User profiles with roles: Administrator, Customer, Manufacturer, Designer.
- **Order Management** - Full order lifecycle from creation through delivery, including file uploads, reference images, modification requests, and chat messages.

## Tech Stack

- **Backend:** Django 6.0 / Python 3.13
- **Database:** SQLite (development)
- **Frontend:** Django templates with static CSS

## Project Structure

```
my_django_setup/myproject/
├── manage.py
├── myproject/          # Project settings, root URL config, WSGI/ASGI
├── home/               # Core app: models, staff views, admin config
│   ├── models.py       # UserProfile, Client, Order, OrderItem, OrderImage, etc.
│   ├── views.py        # Staff login/logout, dashboard, status updates
│   ├── templates/home/ # Staff-facing HTML templates
│   └── migrations/
├── customer/           # Customer-facing app
│   ├── views.py        # Order lookup by ID
│   ├── templates/customer/
│   └── static/css/
└── media/              # Uploaded blueprints and reference images
```

## Getting Started

### Prerequisites

- Python 3.13+

### Installation

1. Clone the repository:

   ```bash
   git clone <repository-url>
   cd Stremet-Hackathon
   ```

2. Create and activate a virtual environment:

   ```bash
   python -m venv .venv
   # Windows
   .venv\Scripts\activate
   # macOS / Linux
   source .venv/bin/activate
   ```

3. Install dependencies:

   ```bash
   pip install -r requirements.txt
   ```

4. Apply database migrations:

   ```bash
   cd my_django_setup/myproject
   python manage.py migrate
   ```

5. Create a superuser:

   ```bash
   python manage.py createsuperuser
   ```

6. Run the development server:

   ```bash
   python manage.py runserver
   ```

7. Open your browser at `http://127.0.0.1:8000/`.

## URL Routes

| URL | Description |
|-----|-------------|
| `/` | Landing dashboard |
| `/login/` | Staff login |
| `/dashboard/` | Unified staff panel |
| `/customer/` | Customer order lookup |
| `/admin/` | Django admin interface |
