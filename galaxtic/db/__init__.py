from surrealdb import AsyncSurreal
from galaxtic import settings

__all__ = ["get_db", "setup_database"]

# Global database instance - initialize it with None first
db = None


async def setup_database() -> None:
    """Initialize database connection"""
    global db
    try:
        print("DB URL: ", settings.SURREALDB.URL)
        db = AsyncSurreal(f"{settings.SURREALDB.URL}")

        await db.signin(
            {
                "username": settings.SURREALDB.USERNAME,
                "password": settings.SURREALDB.PASSWORD,
            }
        )

        await db.use(settings.SURREALDB.NS, settings.SURREALDB.DB)

        await db.query("INFO FOR DB;")

    except Exception as e:
        raise Exception(f"Failed to initialize database: {str(e)}")


def get_db():
    """Get database instance"""
    if db is None:
        raise Exception("Database not initialized")
    return db
