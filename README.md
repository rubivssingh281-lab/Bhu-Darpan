# SatelliteAI: Automated Land Cover & Change Detection System

**Advancing insights from above, for a better tomorrow on Earth.**

[![Python](https://img.shields.io/badge/Python-3.9%2B-blue)](https://www.python.org/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.95%2B-green)](https://fastapi.tiangolo.com/)
[![React](https://img.shields.io/badge/React-18%2B-blueviolet)](https://reactjs.org/)
[![MongoDB](https://img.shields.io/badge/MongoDB-6.0%2B-success)](https://www.mongodb.com/)

---

## 📖 Project Overview

Thousands of high-resolution Earth observation satellite images are generated daily. Manual analysis of this massive data is slow, costly, and prone to human error, delaying critical responses in disaster management and environmental conservation.

**SatelliteAI** is an end-to-end, AI-powered web platform designed to automatically process Sentinel-2 and public EO datasets. It performs high-precision land-cover segmentation, real-time object detection, and bi-temporal change detection, transforming raw satellite imagery into actionable insights via an interactive dashboard and downloadable PDF reports.

---

## ✨ Key Features

- **🚀 Automatic Analysis:** Upload satellite images and let the backend pipeline handle preprocessing, segmentation, and detection automatically.
- **🗺️ Land Cover Segmentation:** Uses U-Net and SegFormer architectures to classify land into Forest, Water, Agriculture, Built-up, and Other categories.
- **🔍 Object Detection:** Leverages YOLOv11 to identify and localize key objects like buildings, roads, rivers, and lakes.
- **🔄 Bi-temporal Change Detection:** Compares historical and current images using Siamese CNNs to track changes over time (e.g., urban expansion, deforestation).
- **📊 Confidence Estimation:** Provides a confidence score (%) for every prediction to ensure reliability and transparency.
- **📄 Automated PDF Reports:** Generates comprehensive downloadable reports containing statistics, charts, and analysis results.
- **📈 Interactive Dashboard:** Visualizes land-cover distribution (pie charts), area changes (bar graphs), and mapped results using Leaflet/MapLibre.
- **⚡ Real-time Alerts (Optional):** Infrastructure to support immediate notifications for critical environmental changes.

---

## 🛠️ Tech Stack & System Architecture

### Frontend
- **React.js, HTML5, CSS3** — Dynamic and responsive user interface.
- **Chart.js, Leaflet/MapLibre** — Data visualization and interactive map rendering.
- **Axios** — API integration with the backend.

### Backend
- **FastAPI (Python)** — High-performance RESTful API handling.
- **Uvicorn** — ASGI server for asynchronous processing.
- **JWT Authentication** — Secure user session management.

### AI / Machine Learning
- **PyTorch, OpenCV, Scikit-learn** — Core ML frameworks.
- **U-Net** — Semantic segmentation of land-cover classes.
- **SegFormer** — Efficient Transformer-based segmentation for high accuracy.
- **YOLOv11** — Real-time object detection for infrastructure.
- **Siamese CNN** — Bi-temporal change detection.

### Database & Geospatial
- **MongoDB (GridFS)** — Storage for satellite images, results, and metadata.
- **GDAL, Rasterio, NumPy** — Geospatial data processing and array manipulation.
- **Sentinel-2 / Public EO Datasets** — Primary data source.

---

## 📊 Methodology Pipeline

The system operates through an automated 8-step pipeline:

1. **Image Acquisition** — Ingest images from Sentinel-2 or public Earth Observation (EO) databases.
2. **Preprocessing** — Apply radiometric correction, noise removal, image enhancement, and resizing.
3. **AI Segmentation** — Deep learning models (U-Net/SegFormer) segment the image into land-cover classes.
4. **Object Detection** — YOLOv11 identifies bounding boxes for roads, buildings, water bodies, etc.
5. **Change Detection** — Compares current and historical images to detect land-cover transformations.
6. **Confidence Estimation** — Calculates and assigns a reliability score to every prediction.
7. **Report Generation** — Compiles findings into an auto-generated PDF report with maps and statistics.
8. **Dashboard & Visualization** — Displays results via interactive charts and layered maps.

---

## 🚀 Installation & Setup

### Prerequisites
- Python 3.9+
- Node.js 18+ and npm
- MongoDB 6.0+ (local or cloud instance)
- Git

### 1. Clone the Repository
```bash
git clone https://github.com/your-repo/satellite-ai.git
cd satellite-ai
```

### 2. Backend Setup (FastAPI)
```bash
cd backend
python -m venv venv
# Activate virtual environment (Windows/Linux/Mac)
# Windows: venv\Scripts\activate
# Linux/Mac: source venv/bin/activate
pip install -r requirements.txt

# Set environment variables (e.g., MONGO_URI, JWT_SECRET)
# Run the backend server
uvicorn main:app --reload
```
The backend will run on `http://localhost:8000` by default.

### 3. Frontend Setup (React)
```bash
cd ../frontend
npm install
# Run the development server
npm start
```
The frontend will be available at `http://localhost:3000`.

### 4. Database Configuration
Ensure MongoDB is running locally or provide a connection string in your backend environment variables.

---

## 🧪 Usage / How It Works

1. **Login** to the web application.
2. **Upload** a satellite image or select a pair of images (for change detection) from the dashboard.
3. **Select Analysis Type** (Segmentation, Object Detection, or Change Detection).
4. **Click Analyze** – The backend will process the images using the AI models.
5. **View Results** – The dashboard will update with pie charts, categorized maps, and bounding boxes.
6. **Download Report** – Click "Generate Report" to download a high-quality PDF summarizing the findings.

---

## 👥 Team Members

This mini-project was developed by the Department of Computer Science & Engineering (Data Science) at ABES Institute of Technology, Ghaziabad (Affiliated to Dr. A.P.J. Abdul Kalam Technical University), Session 2026-27.

| Name | Roll No. |
|------|----------|
| Saksham Singh | 2402901540102 |
| Sanjay Vishkarma | 2402901540103 |
| Shubh Bhardwaj | 2402901540104 |
| Satyam Kumar | 2402901540115 |
| Satyam Kumar | 2402901540116 |

---

## 📚 References & Acknowledgements

- **U-Net:** Ronneberger et al. (2015) – Convolutional Networks for Biomedical Image Segmentation.
- **SegFormer:** Xie et al. (2021) – Simple and Efficient Design for Semantic Segmentation with Transformers.
- **YOLOv8/v11:** Jocher et al. (2023) – Ultralytics.
- **Sentinel-2:** Drusch et al. (2012) – ESA's Optical High-Resolution Mission.
- **Geospatial Processing:** ESRI ArcGIS Documentation, GDAL, and OpenCV.
- **Deep Learning:** Goodfellow, Bengio, Courville (2016) – Deep Learning.
