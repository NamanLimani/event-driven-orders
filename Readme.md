#  Cloud-Native Event-Driven Order Processing System

##  Overview
This project is a production-ready, highly decoupled microservices architecture designed to demonstrate the **Saga Choreography Pattern** for distributed transactions. Built with **FastAPI, Apache Kafka, and PostgreSQL**, it resolves the complexities of maintaining data consistency across isolated services without relying on slow, synchronous HTTP calls. 

To provide an intuitive way to interact with the backend infrastructure, the project features a **Streamlit Agentic Dashboard** that visualizes real-time state machine transitions, event streams, and warehouse stock deductions.

---

##  Architecture & System Design

### The Saga Pattern (Choreography)
In a traditional monolithic application, placing an order and deducting inventory happens in a single database transaction. In this microservices architecture, the Order Service and Inventory Service have **entirely isolated databases**. 

We handle transactions asynchronously using the **Saga Pattern**:
1. **Order Creation:** The user places an order. The Order Service saves it to its PostgreSQL database with a state of `PENDING` and publishes an `OrderCreated` event to Kafka.
2. **Inventory Deduction:** The Inventory Service listens to the Kafka topic. Upon receiving the event, it checks its own database. 
   - If stock exists, it deducts it and publishes an `InventoryReserved` event.
   - If out of stock, it publishes an `InventoryFailed` event.
3. **State Resolution:** The Order Service acts as a consumer for the reply events. It catches the Inventory Service's broadcast and updates the original order status to either `COMPLETED` or `CANCELLED`.

### Bi-Directional Event Streaming
Both microservices utilize `aiokafka` as an asynchronous background task (via FastAPI's `lifespan` manager). This allows the APIs to remain instantly responsive while the heavy lifting of event production and consumption happens continuously in the background using UTF-8 JSON byte serialization.

---

##  Tech Stack
* **Backend Framework:** FastAPI (Asynchronous Python)
* **Message Broker:** Apache Kafka / Zookeeper (Official Docker Images)
* **Database:** PostgreSQL (using `asyncpg` drivers)
* **ORM & Migrations:** SQLAlchemy 2.0 & Alembic
* **Frontend:** Streamlit & Requests
* **Testing & DevOps:** Pytest, HTTPX, GitHub Actions CI/CD pipeline

---

## Directory Structure & File Purpose


```text
event-driven-orders/
│
├── docker-compose.yml       # Provisions Kafka, Zookeeper, and the shared PostgreSQL container
├── requirements.txt         # Version-locked Python dependencies
│
├── order_service/           # MICROSERVICE 1: Handles order creation and final state tracking
│   ├── main.py              # FastAPI app, Kafka Producer (OrderCreated), Kafka Consumer (Inventory replies)
│   ├── database.py          # Asynchronous PostgreSQL connection engine
│   ├── models.py            # SQLAlchemy ORM definitions (Order table)
│   ├── schemas.py           # Pydantic V2 models for strict request/response data validation
│   ├── alembic/             # Database migration history and configuration
│   └── test_order_api.py    # Pytest integration tests (HTTPX ASGITransport)
│
├── inventory_service/       # MICROSERVICE 2: Manages warehouse stock
│   ├── main.py              # FastAPI app, Kafka Consumer (Order events), Kafka Producer (Inventory replies)
│   ├── database.py          # Isolated DB connection (points to inventory_db)
│   ├── models.py            # SQLAlchemy ORM definitions (ProductInventory table)
│   ├── schemas.py           # Pydantic V2 models for warehouse stock validation
│   └── alembic/             # Database migration history for the inventory database
│
├── frontend/                # USER INTERFACE
│   └── app.py               # Streamlit dashboard for real-time visual system interaction
│
└── .github/workflows/       # DEVOPS
    └── ci.yml               # GitHub Actions pipeline for automated Pytest execution on push
```

---

## Installation & Setup Guide

### Prerequisites
* Docker Desktop installed and running.
* Python 3.13 installed.

### Step 1: Environment Setup
Clone the repository and create an isolated virtual environment.
```bash
git clone <your-repo-url>
cd event-driven-orders
python -m venv venv
source venv/bin/activate  # On Windows use: venv\\Scripts\\activate
pip install -r requirements.txt
```

### Step 2: Spin Up Infrastructure
Start the Kafka broker, Zookeeper, and PostgreSQL container.
```bash
docker-compose up -d
```

### Step 3: Database Provisioning
The `docker-compose.yml` creates a default `orders_db`. We must manually create the isolated `inventory_db` for the second microservice to respect the Database-per-Service rule.
```bash
docker exec -it order_db psql -U admin -d orders_db -c "CREATE DATABASE inventory_db;"
```

### Step 4: Apply Database Migrations
Run Alembic to build the tables in both databases.
```bash
# Order Service Migrations
cd order_service
alembic upgrade head
cd ..

# Inventory Service Migrations
cd inventory_service
alembic upgrade head
cd ..
```

### Step 5: Start the Microservices
You need two separate terminal windows (with the virtual environment activated in both) to run the isolated backend services.

**Terminal 1 (Order Service):**
```bash
cd order_service
uvicorn main:app --reload --port 8000
```

**Terminal 2 (Inventory Service):**
```bash
cd inventory_service
uvicorn main:app --reload --port 8001
```

*Note: You can seed initial inventory via the Swagger UI at `http://127.0.0.1:8001/docs`.*

### Step 6: Launch the Agentic Dashboard
Open a third terminal window to start the Streamlit UI.
```bash
cd frontend
streamlit run app.py
```
This will open `http://localhost:8501` in your browser. From here, you can dispatch orders and watch the Saga architecture seamlessly transition the states in real-time!

---

##  Testing & CI/CD
This project includes automated integration tests using `pytest` and `httpx`.
To run the tests locally:
```bash
cd order_service
pytest test_order_api.py -v
```
