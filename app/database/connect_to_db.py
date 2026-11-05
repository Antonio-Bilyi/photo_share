from pathlib import Path
import os
from dotenv import load_dotenv

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

BASE_DIR = Path(__file__).resolve().parent.parent.parent
env_path = BASE_DIR / '.env'

load_dotenv(dotenv_path=env_path)

USER = os.getenv('POSTGRES_USER')
PASSWORD = os.getenv('POSTGRES_PASSWORD')
DB = os.getenv('POSTGRES_DB')
HOST = os.getenv('POSTGRES_HOST')
PORT = os.getenv('POSTGRES_PORT')

BASE_URL = (f'postgresql+psycopg2://{USER}:{PASSWORD}@{HOST}:{PORT}/{DB}')

engine = create_engine(BASE_URL)
Session = sessionmaker(autocommit=False, autoflush=False, bind=engine)

def db_connect():
    db = Session()
    try:
        yield db
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()