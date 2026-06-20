from sqlmodel import create_engine, Session
import os
from dotenv import load_dotenv

load_dotenv()

# We will read the DATABASE_URL from the environment
raw_url = os.getenv("DATABASE_URL")
if raw_url and raw_url.startswith("postgresql://"):
    # SQLAlchemy/psycopg2 does not support Prisma's query parameters like pgbouncer=true
    clean_url = raw_url.split("?")[0] if "?" in raw_url else raw_url
    DATABASE_URL = clean_url.replace("postgresql://", "postgresql+psycopg2://", 1)
else:
    DATABASE_URL = "sqlite:///./test.db"

engine = create_engine(DATABASE_URL, echo=True)

def get_session():
    with Session(engine) as session:
        yield session
