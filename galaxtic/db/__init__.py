from surrealdb import AsyncSurreal
from galaxtic import settings

__all__ = ["get_db", "setup_database"]

# Global database instance - initialize it with None first
db = None


async def setup_database() -> None:
    """Initialize database connection"""
    global db
    try:
        # Initialize the database connection with settings
        # Note: The URL should be in format "ws://localhost:8000/rpc"
        db = AsyncSurreal(f"{settings.SURREALDB.URL}/rpc")

        # Sign in with root credentials using the correct format
        await db.signin(
            {
                "username": settings.SURREALDB.USERNAME,
                "password": settings.SURREALDB.PASSWORD,
            }
        )

        # Use the specified namespace and database
        await db.use(settings.SURREALDB.NS, settings.SURREALDB.DB)

        # Test the connection with a simple query
        await db.query("INFO FOR DB;")

    except Exception as e:
        raise Exception(f"Failed to initialize database: {str(e)}")


def get_db():
    """Get database instance"""
    if db is None:
        raise Exception("Database not initialized")
    return db
