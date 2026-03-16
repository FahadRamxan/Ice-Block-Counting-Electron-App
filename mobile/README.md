# Ice Block Counter — Mobile (React Native / Expo)

iOS and Android app that talks to the same Flask backend as the desktop app.

**Expo SDK 54** — Use **Expo Go for SDK 54** from the [App Store](https://apps.apple.com/app/expo-go/id982107779) or [Play Store](https://play.google.com/store/apps/details?id=host.exp.exponent). If you see "project uses SDK 51" while the project is on SDK 54, **clear the dev server cache**: stop the server (Ctrl+C), then run `npm run start:clear` and scan the QR code again.

**"Port 8081 is being used" / "Input is required"** — Another process (e.g. a previous Expo run) is using port 8081. Either stop that process or use: `npm run start:clear` (uses port 8082), or `npx expo start --clear --port 8082`.

## Prerequisites

- Node.js 18+
- Expo CLI (via `npx`)
- **iOS:** Mac with Xcode (for simulator or device)
- **Android:** Android Studio with emulator, or physical device with [Expo Go](https://expo.dev/go)
- Backend running: `python backend/run_flask.py` from the **project root** (parent of `mobile/`)

## API base URL / "Network request failed"

On a **physical iPhone** (or Android phone), the app cannot use `localhost` — that points to the phone. Use your **computer’s IP** so the phone can reach the Flask backend.

1. **Find your computer’s IP** (same Wi‑Fi as the phone):  
   - Windows: `ipconfig` → look for IPv4 (e.g. `192.168.8.165`)  
   - Mac: System Settings → Network → Wi‑Fi → Details
2. **In the app:** open **Account** (header) → **Backend API URL** → enter `http://YOUR_IP:5000` (e.g. `http://192.168.8.165:5000`) → **Save URL**.
3. Ensure **Flask is running** on that machine (`python backend/run_flask.py`) and the phone is on the same Wi‑Fi.

The URL is saved and used on next launch. If Statistics (or any screen) shows "network request failed", set the API URL in Account as above.

## Run the app

```bash
cd mobile
npm install
npm start
```

Then:

- **Android:** press `a` in the terminal or run `npm run android`
- **iOS (Mac only):** press `i` in the terminal or run `npm run ios`
- **Expo Go:** scan the QR code **inside the Expo Go app** (tap “Scan QR code”), not with the iPhone Camera app. The Camera app shows “no usable data found” for Expo’s `exp://` URL; Expo Go opens it correctly. Use the same Wi‑Fi as your PC.

## Screens

- **Home** — Shortcuts to NVRs, Recordings, Test, Statistics
- **NVRs** — List, add, delete NVRs (same API as desktop)
- **Recordings** — Pick NVR, date, channels; load recordings; run model on selection
- **Test** — Placeholder (full test pipeline is on desktop)
- **Statistics** — Filter by NVR, view totals and recent runs

## Build for store / device

- **Android:** `npx eas build --platform android` (Expo EAS) or `expo prebuild` then build in Android Studio
- **iOS:** `npx eas build --platform ios` (Mac required for local build) or EAS cloud build

Ensure the production API URL is set (e.g. your deployed Flask server with HTTPS) before building.
