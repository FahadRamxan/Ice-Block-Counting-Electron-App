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

## How to run the app

All commands below assume you are in the **`mobile`** folder (next to the project root’s `backend/`).

### 1. One-time setup

```bash
cd mobile
npm install
```

### 2. Start the development server (Metro)

```bash
npm start
```

This opens the **Expo dev tools** in the terminal and usually a URL in the browser. From that menu you can:

| Action | Command |
|--------|---------|
| Open **Android** emulator / device | Press **`a`** in the terminal |
| Open **iOS** simulator (Mac + Xcode only) | Press **`i`** in the terminal |
| Open in **web browser** | Press **`w`** in the terminal |
| Reload app | Press **`r`** |
| Open dev menu | Press **`m`** |
| Quit | **`Ctrl+C`** |

**If port 8081 is busy** (or you see “Input is required” in a non-interactive shell):

```bash
npm run start:clear
```

This starts Metro on **port 8082** with a cleared cache.

**Manual port:**

```bash
npx expo start --port 8083
```

### 3. Run modes (direct commands)

You can skip the interactive menu and go straight to a target:

| Mode | Command | Notes |
|------|---------|--------|
| **Default** (then choose platform in terminal) | `npm start` | Same as `expo start` |
| **Web** (browser) | `npm run web` | Same as `expo start --web`. First time, Expo may prompt to install web dependencies; if it fails, run: `npx expo install react-dom react-native-web` |
| **Android** | `npm run android` | Needs Android SDK / emulator or USB device with debugging |
| **iOS simulator** | `npm run ios` | **Mac only**, Xcode installed |

Examples:

```bash
cd mobile
npm run web          # opens http://localhost:8081 (or the port Metro prints)
npm run android      # tries to launch Android build
npm run ios          # Mac: launches iOS Simulator
```

### 4. Physical phone with **Expo Go**

1. Start the server: `npm start` or `npm run start:clear`.
2. Install **[Expo Go](https://expo.dev/go)** (same **SDK 54** as this project).
3. On **Android:** scan the QR code with Expo Go.
4. On **iPhone:** open **Expo Go** → **Scan QR code** — do **not** use the system Camera app (it won’t open `exp://` links).
5. Phone and PC must be on the **same Wi‑Fi**. Set **Account → Backend API URL** to `http://YOUR_PC_IP:5000` (see above).

### 5. Backend (required for API screens)

From the **repository root** (parent of `mobile/`):

```bash
python backend/run_flask.py
```

The mobile app expects the API at the URL configured in **Account** (or defaults: `localhost` on simulator, `10.0.2.2` on Android emulator).

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
