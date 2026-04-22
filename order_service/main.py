from fastapi import FastAPI , Depends , HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
import json
from contextlib import asynccontextmanager
from aiokafka import AIOKafkaProducer , AIOKafkaConsumer
import asyncio

# Import local files
import models
import schemas
from database import get_db , AsyncSessionLocal

# We declare a global variable to hold our Kafka producer
producer = None

async def consume_inventory_events():
    # Wait for the FastAPI server and Kafka broker to stabilize
    await asyncio.sleep(2)
    try :
        # Initialize the Consumer to listen to the Inventory Service
        consumer = AIOKafkaConsumer(
            'inventory_events',
            bootstrap_servers='localhost:9092',
            group_id="order_group",
            auto_offset_reset="earliest",
            value_deserializer=lambda m : json.loads(m.decode('utf-8'))
        )

        await consumer.start()
        print("Order Service listening to 'inventory_events'...")

        try :
            async for msg in consumer:
                event = msg.value
                event_type = event.get('event_type')
                order_data = event.get('data' , {})
                order_id = order_data.get('id')

                if not order_id:
                    continue

                async with AsyncSessionLocal() as db :
                    # Fetch the existing order from PostgreSQL
                    result = await db.execute(select(models.Order).where(models.Order.id == order_id))
                    order = result.scalar_one_or_none()

                    if order:
                        # State Machine Logic
                        if event_type == 'InventoryReserved':
                            order.status = 'COMPLETED'
                            print(f"SUCCESS: Order {order_id} status updated to completed")
                        elif event_type == 'InventoryFailed' :
                            order.status = 'CANCELLED'
                            print(f"FAILED: Order {order_id} status updated to cancelled")
                        
                        # Save the updated status to the database
                        await db.commit()
        
        finally :
            await consumer.stop()
    
    except Exception as e :
        print(f"\n Critical Order Consumer Error: {e}\n")

# The Lifespan context manager
@asynccontextmanager
async def lifespan(app : FastAPI):
    global producer
    # 1. Initialize the producer on startup
    producer = AIOKafkaProducer(
        bootstrap_servers= 'localhost:9092',
        # Automatically serialize Python dicts to JSON bytes
        value_serializer=lambda v : json.dumps(v).encode('utf-8')
    )
    # Connect to the Kafka broker
    await producer.start()
    print("Kafta Producer Started Successfully")

    # Start the background task to listen for inventory replies
    task = asyncio.create_task(consume_inventory_events())

    yield # This is where the FastAPI app runs
    task.cancel()

    # 2. Gracefully shut down the producer when the server stops
    await producer.stop()
    print("Kafka Priducer Shut Down Successfully")


# Initialize FastAPI with the lifespan manager    
app = FastAPI(title='Order Service API' , lifespan=lifespan)

@app.post("/orders/" , response_model=schemas.OrderResponse)
async def create_order(order : schemas.OrderCreate , db : AsyncSession = Depends(get_db)):
    # 1. Convert the Pydantic schema into a SQLAlchemy model
    new_order = models.Order(
        product_name = order.product_name,
        quantity = order.quantity,
        total_price = order.total_price
    )

    # 2. Add it to the database session
    db.add(new_order)

    # 3. Commit the transaction to save it to PostgreSQL
    await db.commit()

    # 4. Refresh the model to get the generated 'id' from the database
    await db.refresh(new_order)

    # 5. Construct the Event Payload
    order_event = {
        "event_type" : "OrderCreated",
        "data" : {
            "id" : new_order.id,
            "product_name" : new_order.product_name,
            "quantity" : new_order.quantity,
            "total_price" : new_order.total_price,
            "status" : new_order.status
        }
    }

    # 6. Publish the Event to Kafka
    # We send it to a topic named 'order_events'
    await producer.send_and_wait("order_events" , order_event)

    return new_order

@app.get("/orders/{order_id}" , response_model=schemas.OrderResponse)
async def get_order(order_id : int , db : AsyncSession = Depends(get_db)):
    # Query the database for the specific order ID
    result = await db.execute(select(models.Order).where(models.Order.id == order_id))
    order = result.scalar_one_or_none()

    if order is None:
        raise HTTPException(status_code=404 , detail='Order Not Found')
    
    return order