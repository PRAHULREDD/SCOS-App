<div align="center">
  <h1>SCOS: Smart Waste Collection Optimization System</h1>
  <p><i>Real-time municipal waste management platform integrating citizen reporting, driver routing, and administrative dispatch.</i></p>

  [![Deployment](https://img.shields.io/badge/Live_Demo-Render-46E3B7?style=for-the-badge&logo=render&logoColor=white)](https://scos-app.onrender.com)
  [![FastAPI](https://img.shields.io/badge/FastAPI-005571?style=for-the-badge&logo=fastapi)](https://fastapi.tiangolo.com/)
  [![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg?style=for-the-badge)](https://opensource.org/licenses/MIT)

</div>

---

## 🌍 Live Demonstration
The system is currently deployed and live at: **[https://scos-app.onrender.com](https://scos-app.onrender.com)**

*Note: The platform is running on a cloud container. Please allow up to 30 seconds for the application to wake from sleep on the initial load.*

## Overview

SCOS is designed to modernize municipal waste management. By transitioning from scheduled, static collection routes to a dynamic, data-driven model, SCOS improves fleet efficiency and city cleanliness. The system provides tailored interfaces for three distinct roles: Citizens, Drivers, and Administrators.

### Core Architecture
The platform utilizes a decoupled monolithic architecture optimized for high concurrency and rapid deployment:
- **Backend:** Python `FastAPI` providing asynchronous REST API endpoints.
- **Database:** `SQLite` for local development, scaling to `PostgreSQL` via SQLAlchemy ORM for production.
- **Authentication:** Stateless `JWT` with strict Role-Based Access Control.
- **Frontend:** Server-delivered static HTML, styled with `Tailwind CSS`, utilizing Vanilla JavaScript for lightweight, fast DOM manipulation and routing.

## Features by Role

### Citizen Portal
- **Incident Reporting:** Users can upload photos of illegal dumping or overflowing bins.
- **Location Tagging:** GPS metadata is automatically attached to reports for precise routing.
- **Complaint Tracking:** Live status updates on submitted reports (Pending, In Progress, Resolved).

### Driver Interface
- **Dynamic Assignments:** Drivers receive real-time route updates based on proximity and urgency.
- **Pickup Verification:** Mandatory visual proof capture (via mobile camera) to verify bin clearance.
- **Status Toggling:** En-route tracking and emergency dispatch triggers.

### Admin Control Center
- **Isomorphic Heatmaps:** High-level visualization of waste clusters and cleanliness metrics across municipal wards.
- **Live Fleet Tracking:** Monitor active driver routes and deployment status.
- **Automated Dispatch:** Rapid-response unit assignment for high-priority incidents.

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
uvicorn main:app --reload --host 127.0.0.1 --port 8000
```
The application will boot at `http://127.0.0.1:8000/`.

---

## Deployment (Render)

SCOS is containerized for seamless, zero-config deployment on platforms like Render.

1. Connect your repository to Render.
2. Select **Web Service** -> **Build and deploy from Git repository**.
3. Set the **Root Directory** to `backend`.
4. Render will automatically detect the Dockerfile, build the container, and expose the live application securely via HTTPS.

---

## Contributing
Please see [CONTRIBUTING.md](CONTRIBUTING.md) for details on submitting pull requests and reporting issues.

## License
This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.
