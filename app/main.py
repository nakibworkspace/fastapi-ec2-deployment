from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from starlette_exporter import PrometheusMiddleware, handle_metrics
from sqlalchemy import create_engine, Column, Integer, String, DateTime, text
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from datetime import datetime
from pydantic import BaseModel
import os
import joblib
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

# Database setup - use DATABASE_URL if provided, otherwise build from components
DATABASE_URL = (
    os.getenv("DATABASE_URL")
    or f"postgresql://{os.getenv('POSTGRES_USER', 'user')}:{os.getenv('POSTGRES_PASSWORD', 'pass')}@{os.getenv('POSTGRES_HOST', 'localhost')}:5432/{os.getenv('POSTGRES_DB', 'appdb')}"
)

engine = create_engine(DATABASE_URL)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()


# Models
class Item(Base):
    __tablename__ = "items"
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, index=True)
    description = Column(String)
    created_at = Column(DateTime, default=datetime.utcnow)


# Pydantic schemas
class ItemCreate(BaseModel):
    name: str
    description: str


class ItemResponse(BaseModel):
    id: int
    name: str
    description: str
    created_at: datetime

    class Config:
        from_attributes = True


# ML Model schemas
class PredictionRequest(BaseModel):
    text: str


class PredictionResponse(BaseModel):
    text: str
    sentiment: str
    confidence: float


# FastAPI app
app = FastAPI(title="Scalable FastAPI on AWS", version="1.0.0")

# Global variable for ML model
ml_model = None

# Middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.add_middleware(PrometheusMiddleware)
app.add_route("/metrics", handle_metrics)


# Create tables and load ML model
@app.on_event("startup")
def startup():
    Base.metadata.create_all(bind=engine)

    # Load ML model
    global ml_model
    model_path = Path("models/sentiment_model.joblib")
    if model_path.exists():
        ml_model = joblib.load(model_path)
        print(f"✓ ML model loaded from {model_path}")
    else:
        print(f"⚠ Warning: ML model not found at {model_path}")
        print("  Run 'python train_model.py' to create the model")


@app.get("/")
def read_root():
    return {
        "status": "online",
        "service": "FastAPI on AWS EC2",
        "version": "1.0.0",
        "ml_model_loaded": ml_model is not None,
    }


@app.get("/health")
def health_check():
    try:
        db = SessionLocal()
        db.execute(text("SELECT 1"))
        db.close()
        return {
            "status": "healthy",
            "database": "connected",
            "ml_model": "loaded" if ml_model else "not loaded",
        }
    except Exception as e:
        return {"status": "unhealthy", "database": "disconnected", "error": str(e)}


@app.post("/items", response_model=ItemResponse)
def create_item(item: ItemCreate):
    db = SessionLocal()
    try:
        db_item = Item(name=item.name, description=item.description)
        db.add(db_item)
        db.commit()
        db.refresh(db_item)
        return db_item
    finally:
        db.close()


@app.get("/items", response_model=list[ItemResponse])
def list_items():
    db = SessionLocal()
    try:
        items = db.query(Item).all()
        return items
    finally:
        db.close()


@app.get("/items/{item_id}", response_model=ItemResponse)
def get_item(item_id: int):
    db = SessionLocal()
    try:
        item = db.query(Item).filter(Item.id == item_id).first()
        if not item:
            raise HTTPException(status_code=404, detail="Item not found")
        return item
    finally:
        db.close()


# ML Model endpoints
@app.post("/predict", response_model=PredictionResponse)
def predict_sentiment(request: PredictionRequest):
    """Predict sentiment of input text using ML model"""
    if ml_model is None:
        raise HTTPException(
            status_code=503, detail="ML model not loaded. Please train the model first."
        )

    try:
        # Get prediction
        prediction = ml_model.predict([request.text])[0]
        probabilities = ml_model.predict_proba([request.text])[0]
        confidence = float(max(probabilities))

        sentiment = "positive" if prediction == 1 else "negative"

        return PredictionResponse(
            text=request.text, sentiment=sentiment, confidence=confidence
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Prediction error: {str(e)}")


@app.get("/model/info")
def model_info():
    """Get information about the loaded ML model"""
    if ml_model is None:
        return {
            "loaded": False,
            "message": "No model loaded. Run 'python train_model.py' to create one.",
        }

    return {
        "loaded": True,
        "model_type": "Sentiment Classifier",
        "algorithm": "Logistic Regression with TF-IDF",
        "classes": ["negative", "positive"],
    }
