import pandas as pd
import joblib
import os
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.naive_bayes import MultinomialNB
from sklearn.pipeline import make_pipeline
from sqlalchemy.orm import Session
from src.database import SessionLocal, Article

MODEL_PATH = "src/ml_model.pkl"

def train():
    session = SessionLocal()
    
    # 1. Fetch Training Data (Only articles you have reviewed)
    # human_feedback: 1 = Dismiss (Bad), 2 = Confirm (Good)
    query = session.query(Article.summary, Article.title, Article.human_feedback)\
        .filter(Article.human_feedback.in_([1, 2]))
    
    df = pd.read_sql(query.statement, session.bind)
    session.close()

    if len(df) < 10:
        print(f"⚠️ Not enough training data! You have {len(df)} labels. Please review at least 10 articles in the UI.")
        return

    print(f"🧠 Training on {len(df)} articles...")

    # 2. Preprocessing
    # Combine Title + Summary for better context
    df['text'] = df['title'] + " " + df['summary']
    
    # Map labels: 1 (Dismiss) -> 0, 2 (Confirm) -> 1
    y = df['human_feedback'].map({1: 0, 2: 1})
    X = df['text']

    # 3. Build Pipeline (TF-IDF Vectorizer + Naive Bayes Classifier)
    # TfidfVectorizer: Converts words to importance scores (ignoring common words like "the")
    model = make_pipeline(TfidfVectorizer(stop_words='english'), MultinomialNB())

    # 4. Train
    model.fit(X, y)

    # 5. Save the "Brain"
    joblib.dump(model, MODEL_PATH)
    print(f"✅ Model saved to {MODEL_PATH}")

if __name__ == "__main__":
    train()