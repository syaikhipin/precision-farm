from sqlalchemy import create_engine, Column, Integer, String, JSON, DateTime, ForeignKey, text
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, relationship
from datetime import datetime
import os
from dotenv import load_dotenv
from werkzeug.security import generate_password_hash, check_password_hash

load_dotenv()

DB_URL = os.getenv('DATABASE_URL', 'postgresql://postgres:postgres@localhost:5432/agridata')

engine = create_engine(DB_URL)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

class User(Base):
    __tablename__ = 'users'
    
    id = Column(Integer, primary_key=True)
    email = Column(String, unique=True, nullable=False)
    password_hash = Column(String, nullable=False)
    role = Column(String, nullable=False, default='user')
    lands = relationship('Land', back_populates='user')
    
    def set_password(self, password):
        self.password_hash = generate_password_hash(password, method='pbkdf2:sha256')
    
    def check_password(self, password):
        return check_password_hash(self.password_hash, password)

class Land(Base):
    __tablename__ = 'lands'
    
    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey('users.id'))
    name = Column(String, nullable=False)
    coordinates = Column(JSON)
    soil_type = Column(String)
    area = Column(Integer)
    user = relationship('User', back_populates='lands')
    recommendations = relationship('Recommendation', back_populates='land')

class Recommendation(Base):
    __tablename__ = 'recommendations'
    
    id = Column(Integer, primary_key=True)
    land_id = Column(Integer, ForeignKey('lands.id'))
    data = Column(JSON)
    created_at = Column(DateTime, default=datetime.utcnow)
    land = relationship('Land', back_populates='recommendations')

def init_database():
    Base.metadata.create_all(bind=engine)

def get_user(email):
    db = SessionLocal()
    try:
        return db.query(User).filter(User.email == email).first()
    finally:
        db.close()

def create_user(email, password, role='user'):
    db = SessionLocal()
    try:
        user = User(email=email, role=role)
        user.set_password(password)
        db.add(user)
        db.commit()
        db.refresh(user)
        return user
    finally:
        db.close()

def sign_in(email, password):
    db = SessionLocal()
    try:
        user = db.query(User).filter(User.email == email).first()
        if user and user.check_password(password):
            return user
        return None
    finally:
        db.close()

def save_land(user_id, name, coordinates, soil_type, area):
    db = SessionLocal()
    try:
        land = Land(
            user_id=user_id,
            name=name,
            coordinates=coordinates,
            soil_type=soil_type,
            area=area
        )
        db.add(land)
        db.commit()
        db.refresh(land)
        return land
    finally:
        db.close()

def get_user_lands(user_id):
    db = SessionLocal()
    try:
        return db.query(Land).filter(Land.user_id == user_id).all()
    finally:
        db.close()

def save_recommendation(land_id, recommendation_data):
    db = SessionLocal()
    try:
        recommendation = Recommendation(
            land_id=land_id,
            data=recommendation_data,
            created_at=datetime.utcnow()
        )
        db.add(recommendation)
        db.commit()
        db.refresh(recommendation)
        return recommendation
    finally:
        db.close()

def get_land_recommendations(land_id):
    db = SessionLocal()
    try:
        return db.query(Recommendation)\
            .filter(Recommendation.land_id == land_id)\
            .order_by(Recommendation.created_at.desc())\
            .all()
    finally:
        db.close()