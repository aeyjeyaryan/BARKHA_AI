# app/core/database.py
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.ext.declarative import declarative_base
import redis
from pymongo import MongoClient

from core.config import DATABASE_URL, REDIS_URL, MONGODB_URL

# PostgreSQL setup
engine = create_engine(DATABASE_URL)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

# Redis setup
redis_client = redis.from_url(REDIS_URL, decode_responses=True)

# MongoDB setup
mongo_client = MongoClient(MONGODB_URL)
mongo_db = mongo_client.rtrwh_offline