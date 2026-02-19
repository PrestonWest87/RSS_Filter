import os
import joblib
from abc import ABC, abstractmethod
from src.database import SessionLocal, Keyword

MODEL_PATH = "src/ml_model.pkl"

class ScorerStrategy(ABC):
    @abstractmethod
    def score(self, text: str):
        pass

class KeywordScorer(ScorerStrategy):
    def __init__(self):
        # Fetch keywords from DB
        session = SessionLocal()
        self.keywords = {k.word: k.weight for k in session.query(Keyword).all()}
        session.close()

    def score(self, text: str):
        text = text.lower()
        score = 0
        matches = []
        for word, weight in self.keywords.items():
            if word in text:
                score += weight
                matches.append(word)
        return score, matches

class MLScorer(ScorerStrategy):
    def __init__(self, model_path):
        self.model = joblib.load(model_path)

    def score(self, text: str):
        prediction_prob = self.model.predict_proba([text])[0]
        # Class 1 is "Important"
        confidence = prediction_prob[1] * 100
        return confidence, ["ML Prediction"]

def get_scorer():
    if os.path.exists(MODEL_PATH):
        try:
            return MLScorer(MODEL_PATH)
        except:
            return KeywordScorer()
    else:
        return KeywordScorer()