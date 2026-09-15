# HealthFlow AI — Mobile (Expo)

React Native companion app for the Phase 1 demo, built with Expo SDK 57.
Color theme: yellow / brown / black.

## Features

- **Home** — overview and shortcuts
- **Intake** — agent chat (`POST /api/intake`)
- **Eligibility** — pick a patient, run a checks (`POST /api/eligibility/check`), view history

## Run with Expo Go

```bash
cd mobile
npm install
npx expo start
```

Scan the QR code with the Expo Go app (Android/iOS). The API base URL is
derived automatically from the Expo dev-server host, so the phone talks to
the FastAPI backend on your machine. Override if needed:

```bash
set EXPO_PUBLIC_API_URL=http://192.168.x.x:8000/api
npx expo start
```

Backend must be reachable from the phone — start it bound to all interfaces:

```bash
cd ../backend
.venv\Scripts\python -m uvicorn main:app --host 0.0.0.0 --port 8000
```