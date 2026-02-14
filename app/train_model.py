"""
Simple sentiment classifier training script.
Run this once to create the model file.
"""
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import LogisticRegression
from sklearn.pipeline import Pipeline
import joblib
import os

# Training data - expanded sentiment examples
texts = [
    # Positive reviews (1)
    "This product is amazing and works great",
    "Excellent quality and fast shipping",
    "Best purchase I've made this year",
    "Wonderful experience, highly recommend",
    "Outstanding product, exceeded expectations",
    "Love it, very satisfied with my purchase",
    "Fantastic service and great product",
    "Highly recommended, worth every penny",
    "Absolutely perfect, couldn't be happier",
    "Superb quality, exactly what I needed",
    "Great value for money, very pleased",
    "Impressive performance, works flawlessly",
    "Delighted with this purchase, five stars",
    "Exceptional product, highly satisfied",
    "Amazing quality, will buy again",
    "Perfect condition, fast delivery",
    "Brilliant product, exceeded my expectations",
    "Very happy with this, great buy",
    "Excellent customer service and product",
    "Top quality, highly recommend to everyone",
    "Fantastic, works better than expected",
    "Really good product, very satisfied",
    "Great purchase, no complaints at all",
    "Wonderful item, exactly as described",
    "Very impressed, excellent quality",
    
    # Negative reviews (0)
    "Terrible product, waste of money",
    "Poor quality and broke after one use",
    "Very disappointed with this purchase",
    "Awful experience, do not buy",
    "Complete garbage, total waste",
    "Worst product ever, very unhappy",
    "Bad quality, not worth the price",
    "Horrible, returned immediately",
    "Defective item, doesn't work at all",
    "Cheap materials, fell apart quickly",
    "Not as described, very misleading",
    "Useless product, complete disappointment",
    "Waste of time and money, avoid",
    "Poor craftsmanship, broke easily",
    "Terrible quality, do not recommend",
    "Disappointing purchase, not worth it",
    "Faulty product, stopped working",
    "Very poor quality, regret buying",
    "Awful, nothing like the description",
    "Substandard quality, very unhappy",
    "Broken on arrival, terrible service",
    "Not good at all, very disappointed",
    "Cheap and nasty, avoid this",
    "Rubbish product, complete waste",
    "Very bad quality, don't buy"
]

# Labels: 1 = positive, 0 = negative
labels = [
    1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1,  # 25 positive
    0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0   # 25 negative
]

# Create pipeline with TF-IDF and Logistic Regression
model = Pipeline([
    ('tfidf', TfidfVectorizer(max_features=100, ngram_range=(1, 2))),
    ('classifier', LogisticRegression(random_state=42, max_iter=1000))
])

# Train the model
print("Training sentiment classifier...")
model.fit(texts, labels)

# Create models directory if it doesn't exist
os.makedirs('models', exist_ok=True)

# Save the model
model_path = 'models/sentiment_model.joblib'
joblib.dump(model, model_path)
print(f"Model saved to {model_path}")

# Test the model
test_texts = [
    "This is great!",
    "This is terrible!"
]
predictions = model.predict(test_texts)
probabilities = model.predict_proba(test_texts)

print("\nTest predictions:")
for text, pred, prob in zip(test_texts, predictions, probabilities):
    sentiment = "positive" if pred == 1 else "negative"
    confidence = max(prob)
    print(f"  '{text}' -> {sentiment} (confidence: {confidence:.2f})")
