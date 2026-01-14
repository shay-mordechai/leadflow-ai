import asyncio
from src.database.session import engine
from src.database.models import Base

async def reset_database():
    print("WARNING: Dropping all tables and creating new SaaS schema...")
    async with engine.begin() as conn:
        # Drop all existing tables
        await conn.run_sync(Base.metadata.drop_all)
        print("Dropped old tables.")
        
        # Create new tables based on updated models
        await conn.run_sync(Base.metadata.create_all)
        print("Created new tables (Users, Leads, MediaInteraction, Integrations).")
        
    print("Database schema reset successfully!")

if __name__ == "__main__":
    asyncio.run(reset_database())