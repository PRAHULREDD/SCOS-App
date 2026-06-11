<div align="center">
  <img src="https://raw.githubusercontent.com/PRAHULREDD/SCOS-App/main/backend/static/img/hero-banner.png" alt="SCOS Banner" onerror="this.style.display='none'"/>
  
  <h1> SCOS: Smart Waste Collection Optimization System</h1>
  <p><i>An Enterprise-Grade, Cross-Platform Municipal Waste Management Solution</i></p>

  [![Build Status](https://img.shields.io/badge/build-passing-brightgreen?style=for-the-badge&logo=githubactions)](https://github.com/PRAHULREDD/SCOS-App/actions)
  [![Platform](https://img.shields.io/badge/platform-Web%20%7C%20Android%20%7C%20iOS-lightgrey?style=for-the-badge)](https://scos-app.onrender.com)
  [![Backend](https://img.shields.io/badge/FastAPI-005571?style=for-the-badge&logo=fastapi)](https://fastapi.tiangolo.com/)
  [![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg?style=for-the-badge)](https://opensource.org/licenses/MIT)

</div>

---

##  Live Demonstrations

* **Web Platform**: [https://scos-app.onrender.com](https://scos-app.onrender.com)
* **Mobile App (Android)**: Generate the `.apk` using Capacitor by pulling the `/mobile` directory in this repository.

> **Production Note**: SCOS is designed to run asynchronously 24/7. When deploying to free-tier cloud environments (like Render), we utilize an integrated `/health` ping-service loop via `cron-job.org` to ensure absolute zero-latency cold-starts for our mobile users.

---

##  System Architecture

SCOS utilizes a highly decoupled, cross-platform architecture built to scale horizontally:

### 1. High-Performance Asynchronous Backend
- **Framework**: Python `FastAPI` serving high-concurrency async REST APIs.
- **Database**: Async SQLAlchemy ORM connected to SQLite (Development) or PostgreSQL (Production).
- **Security**: Stateless JSON Web Tokens (JWT) for robust Role-Based Access Control (RBAC). 
- **CI/CD**: Fully automated testing pipeline using `pytest` and `pytest-asyncio` on GitHub Actions.

### 2. Cross-Platform Frontend (Web & Mobile)
SCOS uses a single, unified codebase to serve both standard web traffic and native mobile applications:
- **Web App**: Vanilla JS and HTML wrapped in a dynamic SPA architecture, styled beautifully with TailwindCSS and custom Glassmorphism aesthetics.
- **Native Mobile Integration**: The web artifacts are injected with `Capacitor` core plugins to compile seamlessly into a native Android `.apk`. It utilizes smart platform-detection (`window.Capacitor.isNativePlatform()`) to hardware-accelerate UI interactions (like the Android back button) and dynamically route API calls to our production cloud environment.

---

##  The SCOS Workflow (Use Cases)

SCOS gamifies municipal cleanliness and streamlines contractor logistics in a continuous 3-step loop:

### Step 1: Citizen Reporting & Gamification
Citizens log into the native app to geolocate and report illegal dumping. They upload photographic evidence and earn `EcoPoints` once the report is validated.
* **Feature**: The integrated Rewards Store allows citizens to spend EcoPoints on transit passes and municipal vouchers dynamically fetched from the API.

### Step 2: Algorithmic Driver Dispatch
The system assigns the reported coordinate to the nearest available driver. The driver receives a push alert on their dashboard.
* **Feature**: Turn-by-Turn GPS Wayfinding routes the driver to the incident. To close the task, the driver must submit a photographic proof-of-completion to the backend.

### Step 3: Admin Command Center
Municipal administrators supervise the entire ecosystem from a centralized dashboard.
* **Feature**: Live Geospatial Heatmaps visualize waste density and contractor efficiency across city wards in real-time.

---

##  Quick Start & Deployment

### 1. Local Development
```bash
# Clone the repository
git clone https://github.com/PRAHULREDD/SCOS-App.git
cd SCOS-App/backend

# Initialize Virtual Environment
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate

# Install Dependencies and Run PyTest Validation
pip install -r requirements.txt
python -m pytest

# Run Local Server
python -m uvicorn main:app --reload --host 127.0.0.1 --port 8000
```
*The auto-seeder will immediately provision your local database with mock data. Access the web platform at `http://127.0.0.1:8000/`.*

### 2. Cloud Deployment (Render)
SCOS is natively optimized for Render cloud platforms:
1. Connect this repository to Render.
2. Select **Web Service** → **Build and deploy from Git repository**.
3. Set the **Root Directory** to `backend`. Render will detect the `Dockerfile` and provision the container over HTTPS automatically.

### 3. Android Mobile Build
To build the `.apk` for Android:
```bash
cd mobile
npm install
npx cap sync android
npx cap open android
```
*(Requires Android Studio to compile the final `.apk`)*

---

## 🛡️ Testing & CI/CD
SCOS maintains a strict CI/CD pipeline via GitHub Actions. **100% of our API endpoints are covered by production-grade integration tests**. Pushing to the `main` branch will automatically trigger `pytest` validation and deploy to Render upon success.

---

##  Contributing & License
- See [CONTRIBUTING.md](CONTRIBUTING.md) for pull request guidelines.
- Licensed under the MIT License - see [LICENSE](LICENSE) for details.
