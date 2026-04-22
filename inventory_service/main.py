import json
import asyncio
from contextlib import asynccontextmanager
from fastapi import FastAPI, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from aiokafka import AIOKafkaConsumer, AIOKafkaProducer

import models
import schemas
from database import get_db, AsyncSessionLocal

producer = None

async def consume_messages():
    # Wait 2 seconds to let FastAPI and the Kafka broker stabilize during a reload
    await asyncio.sleep(2) 
    try:
        consumer = AIOKafkaConsumer(
            'order_events',
            bootstrap_servers='localhost:9092',
            group_id="inventory_group",
            auto_offset_reset="earliest", # FORCE it to read missed messages!
            value_deserializer=lambda m: json.loads(m.decode('utf-8'))
        )
        await consumer.start()
        print("✅ Kafka Consumer fully connected and listening to 'order_events'...")
        
        try:
            async for msg in consumer:
                event = msg.value
                if event.get('event_type') == 'OrderCreated':
                    order_data = event.get('data', {})
                    print(f"\n🔔 Processing Order: {order_data.get('id')} for {order_data.get('product_name')}")
                    
                    # Open database session to check and deduct stock
                    async with AsyncSessionLocal() as db:
                        result = await db.execute(
                            select(models.ProductInventory).where(models.ProductInventory.product_name == order_data.get('product_name'))
                        )
                        product = result.scalar_one_or_none()
                        
                        if product and product.quantity_in_stock >= order_data.get('quantity', 0):
                            product.quantity_in_stock -= order_data['quantity']
                            await db.commit()
                            print(f"✅ Stock deducted. Remaining {product.product_name}: {product.quantity_in_stock}")
                            
                            if producer: # Ensure producer exists before sending
                                reply_event = {"event_type": "InventoryReserved", "data": order_data}
                                await producer.send_and_wait("inventory_events", reply_event)
                                print("📤 Published InventoryReserved event")
                        else:
                            print(f"❌ Out of stock or product not found!")
                            if producer:
                                reply_event = {"event_type": "InventoryFailed", "data": order_data}
                                await producer.send_and_wait("inventory_events", reply_event)
                                print("📤 Published InventoryFailed event")
        finally:
            await consumer.stop()
            
    except Exception as e:
        print(f"\n🚨 CRITICAL CONSUMER ERROR: {e}\n")


@asynccontextmanager
async def lifespan(app: FastAPI):
    global producer
    # Initialize the Producer so the Inventory Service can reply back
    producer = AIOKafkaProducer(
        bootstrap_servers='localhost:9092',
        value_serializer=lambda v: json.dumps(v).encode('utf-8')
    )
    await producer.start()
    print("Kafka Producer started successfully.")
    
    # Start the consumer loop in the background
    task = asyncio.create_task(consume_messages())
    yield
    
    # Graceful shutdown
    task.cancel()
    await producer.stop()


app = FastAPI(title="Inventory Service", lifespan=lifespan)


@app.post("/inventory/", response_model=schemas.InventoryResponse)
async def add_inventory(item: schemas.InventoryCreate, db: AsyncSession = Depends(get_db)):
    new_item = models.ProductInventory(
        product_name=item.product_name,
        quantity_in_stock=item.quantity_in_stock
    )
    db.add(new_item)
    await db.commit()
    await db.refresh(new_item)
    return new_item


@app.get("/inventory/{product_name}", response_model=schemas.InventoryResponse)
async def get_inventory(product_name: str, db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(models.ProductInventory).where(models.ProductInventory.product_name == product_name)
    )
    product = result.scalar_one_or_none()
    
    if not product:
        raise HTTPException(status_code=404, detail="Product not found")
    
    return product