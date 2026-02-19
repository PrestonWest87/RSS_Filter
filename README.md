That is great to hear! Getting those data pipelines flowing smoothly is always the hardest part.

Since you engineered this with traditional machine learning and standard Python multithreading instead of resource-hungry Generative AI, this stack is incredibly lightweight. It won't even wake up the cooling fans on a standard enterprise homelab server.

### **How to Measure Your Resource Usage**

To see exactly what the application is consuming in real-time, use Docker's built-in metrics tool. Run this in your terminal:

```bash
docker stats

```

**Expected Baseline Requirements:**

* **CPU:** 1-2 Cores. The multithreading relies on Network I/O (waiting for websites to respond), not heavy CPU crunching. The only time the CPU will spike is for a few seconds when you hit the "Retrain Model" button.
* **RAM:** ~500MB to 1GB total.
* `db` (Postgres): ~150MB - 300MB
* `web` (Streamlit): ~150MB - 250MB
* `worker` (Scheduler): ~100MB (spiking slightly during the concurrent fetch)


* **Disk:** < 5GB. The Docker images take up about 1GB. PostgreSQL text storage is highly efficient; 100,000 articles will barely use a few hundred megabytes.

---

Here is the complete `README.md` for your project repository.

---

# 🚨 RSS Intel Monitor

A lightweight, human-in-the-loop intelligence pipeline. This tool ingests hundreds of RSS feeds concurrently, scores them based on custom keyword weights, and bubbles up critical infrastructure and security threats for review. It features a built-in Machine Learning engine that learns from your acknowledgment patterns to take over scoring automatically.

## 🏗️ Architecture

* **Frontend:** Streamlit (Python)
* **Backend Worker:** Python `schedule` with multithreaded `requests`
* **Database:** PostgreSQL 15
* **AI/ML:** Scikit-Learn (TF-IDF Vectorizer + Naive Bayes Classifier)
* **Deployment:** Docker Compose

## ⚙️ Prerequisites

* Docker and Docker Compose installed.
* Minimum hardware: 1 CPU Core, 1GB RAM, 5GB Disk Space.

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
