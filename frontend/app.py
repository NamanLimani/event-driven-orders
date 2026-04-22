import streamlit as st
import requests
import time

# Microservice URLs
ORDER_URL = "http://127.0.0.1:8000/orders/"
INVENTORY_URL = "http://127.0.0.1:8001/inventory/"

st.set_page_config(page_title="Saga Architecture Dashboard", layout="wide")
st.title("Event-Driven Saga Dashboard")

# Create two columns for our UI
col1, col2 = st.columns(2)

with col1:
    st.header("Command Center")
    st.markdown("Dispatch an order to trigger the Kafka event chain.")
    
    product = st.selectbox("Select Product", ["Laptop", "Air Conditioner"])
    qty = st.slider("Quantity", 1, 10, 1)
    
    # Mock pricing logic
    price = 1000.0 if product == "Laptop" else 500.0
    
    if st.button("Dispatch Order", type="primary"):
        payload = {
            "product_name": product,
            "quantity": qty,
            "total_price": price * qty
        }
        try:
            # 1. Fire the request to the Order Service
            res = requests.post(ORDER_URL, json=payload)
            if res.status_code == 200:
                order_id = res.json()['id']
                st.success(f"Event published! Order ID: {order_id} created as PENDING.")
                
                # 2. Give Kafka a fraction of a second to process the Saga loop
                time.sleep(0.5) 
                
                # 3. Check the final state
                track_res = requests.get(f"{ORDER_URL}{order_id}")
                final_status = track_res.json()['status']
                
                if final_status == "COMPLETED":
                    st.success(f"Saga Complete: Order {order_id} is {final_status}")
                else:
                    st.error(f" Saga Complete: Order {order_id} is {final_status} (Out of Stock)")
                
                # Force the UI to refresh the warehouse metrics
                time.sleep(2)
                st.rerun()
                
        except requests.exceptions.ConnectionError:
            st.error("Failed to connect. Ensure Order Service (Port 8000) is running.")

with col2:
    st.header("Live Warehouse")
    st.markdown("Monitors the Inventory Service database.")
    
    if st.button(" Sync Warehouse State"):
        st.rerun()
        
    try:
        # Fetch current stock from Inventory Service
        inv_res = requests.get(f"{INVENTORY_URL}{product}")
        if inv_res.status_code == 200:
            stock = inv_res.json()["quantity_in_stock"]
            
            # Display a nice visual metric
            if stock > 0:
                st.metric(label=f"Current {product} Stock", value=stock)
            else:
                st.metric(label=f"Current {product} Stock", value=stock, delta="- Out of Stock", delta_color="inverse")
        else:
            st.warning("Product not found in warehouse. Add it via the backend Swagger UI.")
    except requests.exceptions.ConnectionError:
        st.error("Failed to connect. Ensure Inventory Service (Port 8001) is running.")

st.divider()

# A manual tracking section
st.header(" Manual Saga Tracker")
st.markdown("Check the specific state machine status of any historical order.")

search_id = st.number_input("Order ID", min_value=1, value=1)
if st.button("Track Order"):
    try:
        track_res = requests.get(f"{ORDER_URL}{search_id}")
        if track_res.status_code == 200:
            data = track_res.json()
            st.json(data)
        else:
            st.warning("Order not found.")
    except Exception:
        st.error("Connection failed.")