# SCOS — Web–Mobile Parity & Synchronization Report (Post-Remediation)

## 1. Unified Architecture

```
                        ┌─────────────────────────────────┐
                        │       Client Applications       │
                        └──────────────┬──────────────────┘
                                       │
                ┌──────────────────────┴──────────────────────┐
                │                                             │
                ▼                                             ▼
     ┌──────────────────────┐                      ┌──────────────────────┐
     │   Web Application    │                      │  Mobile Application  │
     │  (Browser / FastAPI) │                      │ (Capacitor Android)  │
     └──────────┬───────────┘                      └──────────┬───────────┘
                │                                             │
                │        HTTP REST / WebSocket Push           │
                └──────────────────────┬──────────────────────┘
                                       ▼
                       ┌───────────────────────────────┐
                       │    Shared FastAPI Backend     │
                       │    (Port 8000 / Port 8035)    │
                       └───────────────┬───────────────┘
                                       ▼
                       ┌───────────────────────────────┐
                       │   Shared PostgreSQL / SQLite  │
                       │       (Unified Database)      │
                       └───────────────────────────────┘
```

Both platforms connect to the same authoritative shared FastAPI backend application, use the same authentication credentials, and share live application state in a unified database.

---

## 2. Feature-by-Feature Parity Comparison

| Feature / Capability | Web Implementation (`backend/static`) | Android Mobile Implementation (`mobile/android/app/src/main/assets/public/`) | Parity Status | Verification Evidence |
|---|---|---|:---:|---|
| **Role Gateway** | Citizen, Driver, Admin tabs; JWT token stored in `localStorage`. | Identical tabs; JWT token stored in `localStorage`. | **VERIFIED** | Both enforce 3-role gateway; rejected on unauthenticated. |
| **User Registration** | Forces role `CITIZEN` via `/api/auth/register`. | Forces role `CITIZEN` via `/api/auth/register`. | **VERIFIED** | Admin/Driver registration blocked on both. |
| **Citizen Geolocation** | `navigator.geolocation` with error handling; submits real GPS or `null`. | Same JS code; submits real GPS or `null` without Bengaluru fallback. | **VERIFIED** | Verified `12.9716, 77.5946` eliminated from mobile `citizen.js`. |
| **Complaint Description** | Form has `#waste-description`; serializes in payload and displays in history. | Form has `#waste-description`; serializes in payload and displays in history. | **VERIFIED** | Cross-platform tests CP-01 & CP-02 verified visibility. |
| **Proof Photo Upload** | Binary `multipart/form-data` upload in `/complete_pickup`. Images stored in filesystem (`backend/uploads/proof_photos/`); DB stores URL reference. Citizen & Admin UI display unimplemented. | Same `FormData` upload via Capacitor WebView. Images stored in filesystem; DB stores URL reference. Citizen & Admin UI display unimplemented. | **PARTIAL** | Backend upload & validation validated via `test_proof_photo.py` (7/7 tests passed). Citizen/Admin UI display remains unimplemented. |
| **Community Leaderboard** | Dynamic query to `/api/citizen/leaderboard`, real ranking, points. | Dynamic query to `/api/citizen/leaderboard`, real ranking, points. | **VERIFIED** | Hardcoded cards removed; live leaderboard rendered from authoritative DB. |
| **Reward Redemption** | Calls `API.redeemReward`; atomic lock on `User` and `Reward`. Decrements DB eco-points. | Calls `API.redeemReward`; updates local points and toast. State synchronizes on subsequent navigation/query. | **VERIFIED (State) / PARTIAL (UI)** | Authoritative DB state decrements atomically (CP-07); cross-client UI update requires page navigation/query. |
| **Admin Heatmap** | Interactive Leaflet 1.9.4 map with status-coded markers (Red/Amber/Green). | Interactive Leaflet 1.9.4 map with status-coded markers. | **VERIFIED** | Leaflet bundle and container synced to compiled Android assets. |
| **Driver Task Assignment** | Interactive modal; validates `driver.role == 'DRIVER'`; locks complaint. | Interactive modal; real task assignment API. | **VERIFIED** | Fake dispatch buttons removed completely. |
| **Driver Task Completion** | Strictly requires complaint ID; transitions status to `RESOLVED`. | Strictly requires complaint ID; transitions status to `RESOLVED`. | **VERIFIED** | `\|\| 1` fallback eliminated from both clients. |
| **Real-Time WebSockets** | Connects to `/api/ws/driver/{driver_id}` via standard WebSocket. | Connects to `/api/ws/driver/{driver_id}` via standard WebSocket on `http://localhost`. | **VERIFIED (Push) / NOT IMPLEMENTED (Auto-reconnect)** | Real-time push delivery verified on Web and Android emulator (CDP port 9222). Automatic WebSocket reconnection is NOT implemented. |

---

## 3. Proof-Photo Storage Strategy

- **Development Storage:** Uploaded image files are stored on the local filesystem in `backend/uploads/proof_photos/`.
- **Database Reference:** The database stores URL references (e.g. `/api/driver/proof/{task_id}`); it does not store binary image blobs.
- **Persistence Assessment:**
  - Local filesystem storage works reliably during local development.
  - Render's standard execution environment utilizes an **ephemeral filesystem**, which does **not** guarantee persistence across service restarts, redeployments, or instance recycling. The current deployment cannot be described as durable.
  - Production durability requires mounting a **Render Persistent Disk** to the `backend/uploads/` directory or offloading binary storage to an object storage service (such as AWS S3, Cloudflare R2, or Google Cloud Storage).
- **Client Rendering Status:** The backend upload endpoint, file signature verification, and retrieval endpoints are implemented and tested. However, frontend display of proof photos in the Citizen Complaint History and Admin Investigation views remains unimplemented (`PARTIAL`).

---

## 4. Backend URL Resolution & Environment Profiles (`config.js`)

[`config.js`](file:///C:/Users/rr001/Downloads/SCOS/backend/static/js/config.js) prevents Web and Mobile from inadvertently connecting to different databases during cross-platform testing:

```javascript
// Environment Profiles in window.SCOS_CONFIG:
1. Local Web Development:
   window.location.origin (automatically matches hosting FastAPI server)

2. Android Emulator (Capacitor):
   Configurable host: SCOS_EMULATOR_URL or 'http://10.0.2.2:8000'
   Active when SCOS_ENV === 'emulator'

3. Physical Android Device / LAN:
   Configurable host: SCOS_DEV_SERVER_URL (e.g. 'http://192.168.1.50:8000')
   Active when SCOS_ENV === 'device' or 'lan'

4. Production:
   PRODUCTION_REST_URL ('https://scos-app.onrender.com')
   Active when SCOS_ENV === 'production' or default native fallback

5. Explicit Override:
   localStorage.getItem('SCOS_BACKEND_URL') or window.SCOS_BACKEND_URL
   (Highest priority, universal for Web and Mobile)
```

### Diagnostic Tracking
Each client exposes `window.SCOS_CONFIG.getDiagnosticInfo()` on initialization:
```json
{
  "platform": "Capacitor Android Native",
  "isNative": true,
  "configuredEnv": "emulator",
  "activeBackendUrl": "http://10.0.2.2:8000",
  "activeWsUrl": "ws://10.0.2.2:8000/ws/driver/1",
  "status": "RESOLVED"
}
```

---

## 5. Repeatable Mobile Sync Pipeline

To ensure future frontend changes cannot silently leave the Android build stale, a repeatable sync verification script is maintained:

- **Script Path:** [`scripts/verify_mobile_sync.py`](file:///C:/Users/rr001/Downloads/SCOS/scripts/verify_mobile_sync.py)
- **Execution:**
  ```bash
  python scripts/verify_mobile_sync.py [--fix]
  ```
- **Behavior:** Performs bitwise comparison of all 34 assets between `backend/static/` and `mobile/android/app/src/main/assets/public/`. If discrepancies exist, `--fix` executes `npx cap copy` and re-verifies.
- **Verification Result:**
  ```text
  [SCOS Mobile Sync] Auditing frontend assets between Web and Android Mobile...
  [PASS] All 34 frontend assets are 100% synchronized between Web and Android Mobile.
  ```
