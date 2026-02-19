# 🚨 RSS Intel Monitor

A lightweight, human-in-the-loop intelligence pipeline. This tool ingests hundreds of RSS feeds concurrently, scores them based on custom keyword weights, and bubbles up critical infrastructure and security threats for review. It features a built-in Machine Learning engine that learns from your acknowledgment patterns to take over scoring automatically.

## 🏗️ Architecture

* **Frontend:** Streamlit (Python)
* **Backend Worker:** Python `schedule` with multithreaded `requests`
* **Database:** PostgreSQL 15
* **AI/ML:** Scikit-Learn (TF-IDF Vectorizer + Naive Bayes Classifier)
* **Deployment:** Docker Compose

## ⚙️ System Requirements

This application is highly optimized and designed to run efficiently on minimal hardware. The requirements below are based on real-world telemetry with 100+ active RSS feeds and the Machine Learning engine active.

### **Minimum Hardware**
* **CPU:** 1 Core
* **RAM:** 1 GB (Application consumes ~550 MB under active load)
* **Storage:** 5 GB (Accommodates Docker images and PostgreSQL text storage)

### **Recommended Hardware (For smooth ML training & concurrent fetching)**
* **CPU:** 2+ Cores (UI operations like model retraining can briefly utilize >100% of a single thread)
* **RAM:** 2 GB 
* **Storage:** 10 GB SSD (Improves database read/write speeds for large archives)

### **Software Requirements**
* **Docker:** Engine v20.10.0 or higher
* **Docker Compose:** v2.0.0 or higher
* **OS:** Any Linux distribution (Ubuntu/Debian recommended), Windows (via WSL2), or macOS.

### **Resource Allocation Breakdown**
Typical baseline memory consumption per container:
* `web` (Streamlit + ML Brain): ~250 MB - 300 MB
* `worker` (Multithreaded Fetcher): ~200 MB - 250 MB
* `db` (PostgreSQL 15): ~40 MB - 60 MB

## 🚀 Installation & Deployment

1. **Clone the repository** and navigate to the project folder.
2. **Set up environment variables:** Edit the `.env` file to change default database passwords if deploying to production.
3. **Build and start the containers:**
```bash
docker-compose up --build -d

```


4. **Access the Dashboard:** Open a web browser and navigate to `http://localhost:8501`.

## 📖 Usage Guide

The application is built around an **"Inbox Zero"** workflow.

1. **Configuration:** Navigate to the `Configuration` tab. Use the bulk-add text areas to load your RSS feed URLs and define your initial Keywords and Weights (e.g., `grid collapse, 95`).
2. **The Inbox (High Priority):** The `Dashboard` will display unreviewed articles that scored above the alert threshold.
* Click **✅ Acknowledge** for valid threats.
* Click **❌ Dismiss** for noise/false positives.


3. **The Archive:** Dismissed articles vanish from the UI. Acknowledged articles are moved to the `Acknowledged (Confirmed)` tab for permanent record-keeping.

## 🧠 Machine Learning & Tuning

This system suffers from the "Cold Start Problem"—the ML model knows nothing until you teach it.

### Phase 1: Rule-Based (The Default)

Out of the box, the system uses the `KeywordScorer`. It scans text for your configured keywords and adds up the weights. If `Total Score >= 45`, it bubbles the article to the Inbox.

### Phase 2: Training the Brain

Every time you click "Acknowledge" or "Dismiss", you are labeling training data.

1. Review at least 50-100 articles manually using the UI to build a solid dataset.
2. Navigate to the `Training Data` tab.
3. Click **🚀 Retrain Model Now**.
4. The system will generate a Naive Bayes model (`ml_model.pkl`) based on your specific operational preferences.

### Phase 3: ML Takeover

Once `ml_model.pkl` exists, the backend worker automatically detects it and switches from `KeywordScorer` to `MLScorer`. The ML model evaluates the contextual probability of an article being important, rather than relying on rigid keyword matching.

* *Note: You can always fall back to rule-based scoring by deleting the `ml_model.pkl` file and restarting the worker.*

## 🛠️ Troubleshooting & Commands

**View Live Worker Logs (To monitor RSS scraping):**

```bash
docker-compose logs -f worker

```

**Restart the Worker (Required after manual code changes):**

```bash
docker-compose restart worker

```

**System Reset:**
If the database becomes bloated or you want to start fresh, navigate to `Configuration` -> `Danger Zone` in the UI to perform a safe SQL truncation of the articles table, or a complete factory reset.

---

**Would you like to explore adding a data export feature (like downloading the acknowledged threats as a CSV or PDF report) as the next step?**
