<div align="center">
  <img src="https://raw.githubusercontent.com/PRAHULREDD/SCOS-App/main/backend/static/img/hero-banner.png" alt="SCOS Banner" onerror="this.style.display='none'"/>
  
  <h1> SCOS: Smart Waste Collection Optimization System</h1>
  <p><i>A Next-Generation Municipal Waste Management & Civic Engagement Platform</i></p>

  [![Deployment](https://img.shields.io/badge/Live_Demo-Render-46E3B7?style=for-the-badge&logo=render&logoColor=white)](https://scos-app.onrender.com)
  [![FastAPI](https://img.shields.io/badge/FastAPI-005571?style=for-the-badge&logo=fastapi)](https://fastapi.tiangolo.com/)
  [![SQLite](https://img.shields.io/badge/SQLite-003B57?style=for-the-badge&logo=sqlite&logoColor=white)](https://www.sqlite.org/)
  [![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg?style=for-the-badge)](https://opensource.org/licenses/MIT)

</div>

---

##  Live Demonstration
Experience the fully interactive platform live at: **[https://scos-app.onrender.com](https://scos-app.onrender.com)**

> **Note on Cloud Hosting**: SCOS is currently deployed on Render's free tier. We have engineered a lightweight `/api/health` heartbeat endpoint that can be paired with UptimeRobot or Cron-job.org to prevent container sleep, ensuring 24/7 zero-latency availability.

---

##  Overview

SCOS is engineered to modernize municipal waste management by transitioning from static, scheduled collection routes to a **dynamic, data-driven operational model**. By gamifying citizen reporting and optimizing driver logistics, SCOS drastically improves fleet efficiency, reduces carbon footprints, and ensures city cleanliness.

###  Technical Architecture
SCOS utilizes a highly decoupled monolithic architecture optimized for rapid horizontal scaling:
- **Backend Core**: Python `FastAPI` serving high-concurrency asynchronous REST APIs.
- **Data Persistence**: `SQLite` (Development/Demo) scaling seamlessly to `PostgreSQL` via SQLAlchemy ORM. Includes an intelligent **Auto-Seeder** to instantly provision mock data (complaints, incidents, rewards) on cold boots.
- **Security**: Stateless `JWT` (JSON Web Tokens) providing robust, Role-Based Access Control (RBAC).
- **Frontend Layer**: A hyper-fast, vanilla JavaScript SPA (Single Page Application) utilizing `Tailwind CSS`, Glassmorphism aesthetics, and dynamic DOM manipulation without the overhead of heavy frameworks.

---

##  Key Features by Role

### 1. Citizen Portal & Gamification
- **Civic Incident Reporting**: Users can upload geotagged photos of illegal dumping or overflowing bins.
- **Eco-Rewards System (Live)**: Citizens earn `EcoPoints` for validated reports. The integrated Rewards Store fetches dynamic incentives (e.g., Transit Passes, Coffee Vouchers) directly from the database for real-time redemption.
- **Live Tracking**: Citizens monitor the lifecycle of their reports (Pending → Dispatched → Resolved) via an intuitive timeline.

### 2. Driver Logistics Interface
- **Dynamic Routing**: Drivers receive real-time, proximity-based task assignments.
- **Visual Verification**: Mandatory on-site photographic proof capture ensures bins are successfully cleared before a task is marked resolved.
- **Turn-by-Turn Navigation**: Embedded GPS wayfinding and emergency dispatch toggles.

### 3. Admin Command Center
- **Live Geospatial Heatmaps**: Real-time visualization of waste clusters, illegal dumping hotspots, and overall cleanliness metrics aggregated by municipal wards.
- **Fleet Analytics**: Monitor active contractor performance, driver completion rates, and average response times.
- **Automated Dispatching**: One-click rapid response unit deployment for high-severity or hazardous waste incidents.

---

## Quick Start (Local Development)

### 1. Clone the repository
```bash
git clone https://github.com/PRAHULREDD/SCOS-App.git
cd SCOS-App/backend
```

### 2. Set up the environment
```bash
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate
pip install -r requirements.txt
```

### 3. Run the development server
```bash
python -m uvicorn main:app --reload --host 127.0.0.1 --port 8000
```
*The auto-seeder will immediately provision your local database. Access the platform at `http://127.0.0.1:8000/`.*

---

## Zero-Config Deployment (Render)

SCOS is fully containerized and structurally optimized for immediate cloud deployment:
1. Connect this repository to Render.
2. Select **Web Service** → **Build and deploy from Git repository**.
3. Set the **Root Directory** to `backend`.
4. Render will automatically detect the `Dockerfile`, provision the environment, and securely expose the application over HTTPS.

---

## Contributing & License
- See [CONTRIBUTING.md](CONTRIBUTING.md) for pull request guidelines.
- Licensed under the MIT License - see [LICENSE](LICENSE) for details.

