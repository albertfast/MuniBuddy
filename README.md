# MuniBuddy

MuniBuddy is a real-time public transit web application for San Francisco. It displays nearby bus and BART stops, arrival times, and vehicle locations on an interactive map.

**Live Site:** [https://munibuddy.live](https://munibuddy.live)  
**API Docs:** [https://munibuddy.live/docs](https://munibuddy.live/docs)

> Real-time transit tracking · GTFS/SIRI API · FastAPI · React · Docker · DigitalOcean

---

## Features

- Real-time Muni bus and BART arrivals
- Google Maps integration with vehicle markers
- Stop-level predictions grouped by direction and destination
- Support for light/dark/system themes
- Mobile-first responsive design
- Click-to-search and locate-me geolocation functionality

## Tech Stack

**Frontend:**
- React + Vite
- Material UI (MUI)
- Axios, Google Maps JS API
- Responsive SCSS/CSS with custom theming

**Backend:**
- FastAPI (Python)
- GTFS parsing and real-time SIRI API integration
- PostgreSQL + SQLAlchemy
- Redis caching
- Dockerized microservice architecture

**DevOps:**
- Docker + Docker Compose
- Caddy (reverse proxy + SSL)
- DigitalOcean deployment
- CI/CD via GitHub Actions

## Project Structure (Simplified)

```
munibuddy/
├── backend/             # FastAPI backend with GTFS, SIRI integration
│   └── app/
│       ├── routers/     # API route handlers
│       ├── services/    # GTFS, cache, and SIRI logic
├── frontend/            # React frontend with Google Maps + Material UI
│   └── src/
│       ├── components/  # Map and TransitInfo display
│       └── assets/      # CSS and visual styles
```

## API Endpoints

- Nearby Stops: `/api/v1/nearby-stops`
- Muni Predictions: `/api/v1/bus-positions/by-stop`
- BART Predictions: `/api/v1/bart-positions/by-stop`
- Swagger Docs: `/api/v1/docs`

## GTFS

- Located in `backend/gtfs_data/`
- Use `load_gtfs_to_postgres.py` to import into PostgreSQL

## Getting Started

### Prerequisites

- Python 3.10+
- Node.js 18+
- Docker & Docker Compose
- PostgreSQL

### Setup

1. Clone the repository:
   ```bash
   git clone https://github.com/albertfast/MuniBuddy.git
   cd MuniBuddy
   ```

2. Set up the backend:
   ```bash
   cd backend
   python -m venv venv
   source venv/bin/activate
   pip install -r requirements.txt
   ```

3. Set up the frontend:
   ```bash
   cd frontend
   npm install
   npm run dev
   ```

4. To run with Docker:
   ```bash
   docker-compose up --build
   ```

## Team

- Ahmet Sahiner
- Leslie Cain
- Linda Fernandez
- Jeanelle Cristobal

## Contributions

This project was collaboratively developed as a capstone for CNIT 198. Each team member contributed to both frontend and backend development, testing, deployment, and UX design.

## Attribution

This project uses public data and services from:

- [511.org](https://511.org/open-data) for Muni and BART real-time transit data (SIRI + GTFS)
- [BART API](https://www.bart.gov/schedules/developers) for live train departure data (ETD)
- [Google Maps JavaScript API](https://developers.google.com/maps/documentation/javascript/overview) for mapping and geolocation

All data and APIs are used under their respective terms of service. This project is not officially affiliated with BART, SFMTA, MTC, or Google.

## License

This project is released under a custom license: **"Proprietary – MuniBuddy Only"**.

You may view and contribute to the code for the MuniBuddy project only.
Any other use, including reuse, redistribution, or replication, is **strictly prohibited**.

See [LICENSE](./LICENSE) for full details.

© 2025 MuniBuddy. Developed as part of CNIT 195 — Web Development Capstone Course at City College of San Francisco.

