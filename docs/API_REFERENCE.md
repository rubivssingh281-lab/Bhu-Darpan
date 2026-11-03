# Bhū-Darpan — REST API Reference

The Bhū-Darpan backend exposes a modular REST API built with FastAPI.

## Interactive Documentation
- **Swagger UI**: `http://localhost:8000/docs`
- **ReDoc**: `http://localhost:8000/redoc`

## Key Endpoints

### 1. System Health
- **`GET /api/health`**
  - Returns backend version and runtime store status.
  - Response: `{"status": "ok", "version": "1.0.0"}`

### 2. Authentication
- **`POST /api/auth/otp/start`**
  - Request login/registration one-time password.
  - Payload: `{"email": "user@example.com", "purpose": "login"}`
- **`POST /api/auth/otp/verify`**
  - Verify OTP and receive JWT access token.
  - Response: `{"token": "<jwt>", "user": {...}}`

### 3. Satellite Analysis
- **`POST /api/analysis`**
  - Upload satellite image for EuroSAT classification & k-means clustering.
  - Form data: `file=@tile.tif`, `clusters=6`
- **`POST /api/change`**
  - Pairwise temporal difference analysis between two satellite scenes.

### 4. Climate Digital Twin
- **`GET /api/climate/overview`**
  - Regional climate indicators and baseline anomaly matrices.
- **`GET /api/hazards/summary`**
  - Current drought, flood, and fire risk scores for Jammu & Kashmir.
