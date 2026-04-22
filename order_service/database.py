from sqlalchemy.ext.asyncio import create_async_engine , async_sessionmaker , AsyncSession
from sqlalchemy.orm import declarative_base

DATABASE_URL = "postgresql+asyncpg://admin:password123@localhost:5432/orders_db"

# The engine is the core interface to the database
engine = create_async_engine(DATABASE_URL , echo = True)

# The session factory creates individual database sessions for our API requests
AsyncSessionLocal = async_sessionmaker(
    bind=engine,
    class_=AsyncSession,
    expire_on_commit=False
)

# The base class that all our database models will inherit from
Base = declarative_base()

# A dependency function we will use in FastAPI to get a database session
async def get_db():
    async with AsyncSessionLocal() as session :
        yield session