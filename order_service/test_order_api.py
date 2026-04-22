import pytest
from httpx import AsyncClient , ASGITransport
from main import app

# This tells pytest that this is an asynchronous test
@pytest.mark.asyncio
async def test_create_order_validation():
    # We now wrap the FastAPI app in an ASGITransport layer
    transport = ASGITransport(app=app)

    # We use httpx.AsyncClient to send fake requests to our FastAPI app
    async with AsyncClient(transport=transport , base_url='http://test') as ac :
        # We send bad data (missing total_price) to test our Pydantic validation
        response = await ac.post('/orders/' , json={
            "product_name" : "Test Item",
            "quantity" : 1
        })
    
    # We expect a 422 Unprocessable Entity error because the data is bad
    assert response.status_code == 422