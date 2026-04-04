from sqlalchemy import Column, String, Text, DateTime, func
from sqlalchemy.dialects.mysql import BIGINT
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker

Base = declarative_base()

class User(Base):
    __tablename__ = "users"

    id = Column(BIGINT, primary_key=True, autoincrement=True)
    email = Column(String(255), unique=True, nullable=True)
    display_name = Column(Text, nullable=True)
    role = Column(String(50), nullable=False, default='student')
    status = Column(String(50), nullable=False, default='active')
    password = Column(String(255), nullable=False)
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())