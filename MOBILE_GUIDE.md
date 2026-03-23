# AgatClean – Przewodnik mobilizacji aplikacji (Capacitor)

> Architektura: Flask na Render.com (backend) + Capacitor Native Shell (Android/iOS) + Firestore (per-user sync)

---

## Spis treści

1. [Wymagania wstępne](#1-wymagania-wstepne)
2. [Konfiguracja Firebase Console](#2-konfiguracja-firebase-console)
3. [Zmienne środowiskowe na Render](#3-zmienne-srodowiskowe-na-render)
4. [Instalacja Capacitor i Node.js](#4-instalacja-capacitor-i-nodejs)
5. [Generowanie ikon i splash screena](#5-generowanie-ikon-i-splash-screena)
6. [Dodanie platform Android i iOS](#6-dodanie-platform-android-i-ios)
7. [Uruchomienie na emulatorze/telefonie](#7-uruchomienie-na-emulatorzeTelefonie)
8. [Budowanie AAB (Google Play)](#8-budowanie-aab-google-play)
9. [Budowanie IPA (App Store)](#9-budowanie-ipa-app-store)
10. [Podpisywanie i publikacja](#10-podpisywanie-i-publikacja)
11. [Firestore – migracja danych](#11-firestore--migracja-danych)
12. [Rozwiązywanie problemów](#12-rozwiazywanie-problemow)

---

## 1. Wymagania wstępne

### Na każdym systemie
| Narzędzie | Wersja | Instalacja |
|-----------|--------|------------|
| Node.js | ≥ 18 LTS | https://nodejs.org |
| npm | ≥ 9 | (dołączony z Node.js) |
| Python | 3.10+ | już masz |

### Dla Android
| Narzędzie | Wersja | Skąd |
|-----------|--------|------|
| Android Studio | Ladybug (2024) | https://developer.android.com/studio |
| JDK | 17 (dołączony z AS) | – |
| Android SDK | API 34 | Android Studio → SDK Manager |
| Emulator lub telefon | – | telefon w trybie Developer Mode |

### Dla iOS (tylko macOS)
| Narzędzie | Wersja | Skąd |
|-----------|--------|------|
| Xcode | ≥ 15 | Mac App Store |
| CocoaPods | ≥ 1.14 | `sudo gem install cocoapods` |
| Apple Developer Account | – | https://developer.apple.com |
| iOS 13+ device / simulator | – | Xcode → Simulator |

---

## 2. Konfiguracja Firebase Console

### Włącz Firestore

1. Otwórz https://console.firebase.google.com → projekt **agatclean-7fee5**
2. Build → **Firestore Database** → Create Database
3. Wybierz **Production mode** → Europe-west (lub bliższy region)
4. Potwierdź

### Zasady bezpieczeństwa Firestore

W zakładce **Rules** wklej:

```
rules_version = '2';
service cloud.firestore {
  match /databases/{database}/documents {
    match /users/{userId}/appdata/{doc} {
      allow read, write: if request.auth != null && request.auth.uid == userId;
    }
  }
}
```

> **Ważne:** te reguły chronią dane każdego użytkownika – tylko właściciel konta może je czytać i zapisywać.

### Pobierz serviceAccountKey.json

1. Firebase Console → Project Settings → Service accounts
2. Kliknij **Generate new private key**
3. Zapisz plik jako `agatclean-7fee5-firebase-adminsdk-fbsvc-7ea8ab4a03.json` w katalogu projektu
4. **NIE dodawaj go do git!** (już jest w `.gitignore`)

### Uzupełnij konfigurację web app

1. Firebase Console → Project Settings → General → Your apps → Web app
2. Skopiuj wartości `authDomain`, `projectId`, `storageBucket`, `messagingSenderId`, `appId`
3. Wpisz je w `firebase_config.py` w sekcji `FIREBASE_CLIENT_CONFIG`  
   lub (lepiej) ustaw jako zmienne środowiskowe na Render (patrz krok 3)

---

## 3. Zmienne środowiskowe na Render

W panelu Render → Environment → **Add environment variable**:

| Zmienna | Wartość |
|---------|---------|
| `FIREBASE_WEB_API_KEY` | AIzaSyD-xpDHq... (już ustawiona w kodzie) |
| `FIREBASE_AUTH_DOMAIN` | agatclean-7fee5.firebaseapp.com |
| `FIREBASE_PROJECT_ID` | agatclean-7fee5 |
| `FIREBASE_STORAGE_BUCKET` | agatclean-7fee5.appspot.com |
| `FIREBASE_MESSAGING_ID` | (z konsoli Firebase) |
| `FIREBASE_APP_ID` | (z konsoli Firebase) |
| `SECRET_KEY` | (losowy 64-znakowy ciąg, zmień!) |
| `SERVICE_ACCOUNT_KEY_PATH` | /etc/secrets/serviceAccountKey.json |

### Dodanie serviceAccountKey.json na Render jako Secret File

1. Render Dashboard → Service → **Files** → **Add Secret File**
2. Filename: `/etc/secrets/serviceAccountKey.json`
3. Content: wklej zawartość pobranego pliku JSON

---

## 4. Instalacja Capacitor i Node.js

```bash
# W katalogu C:\Projects\AgatClean

# Zainstaluj zależności Node.js
npm install

# Sprawdź czy Capacitor CLI działa
npx cap --version
```

Oczekiwany wynik: `6.x.x`

---

## 5. Generowanie ikon i splash screena

```bash
# Wygeneruj pliki źródłowe (wymaga Pillow – już w requirements.txt)
python generate_icons.py

# Wygeneruj ikony dla wszystkich rozmiarów Android/iOS
npm run icons
```

Po tym kroku w folderze `assets/` powstaną:
- `assets/icon.png` – 1024×1024
- `assets/splash.png` – 2732×2732

A narzędzie `@capacitor/assets` wygeneruje automatycznie wszystkie rozmiary do `android/` i `ios/`.

---

## 6. Dodanie platform Android i iOS

```bash
# Dodaj Android
npx cap add android

# Dodaj iOS (tylko macOS)
npx cap add ios

# Skopiuj www/ i zasoby do platform
npx cap sync
```

Powstaną katalogi `android/` i `ios/` w projekcie.

### Weryfikacja URL serwera

Otwórz `capacitor.config.json` i upewnij się, że URL jest poprawny:

```json
"server": {
  "url": "https://agatclean.onrender.com",
  ...
}
```

Jeśli Twoja aplikacja ma inny URL na Render, zmień tę wartość.

> **Podczas developmentu** możesz tymczasowo ustawić URL lokalnego serwera, np.:
> ```json
> "url": "http://192.168.1.100:5000"
> ```
> (zamień na swoje IP – np. z `ipconfig` w CMD)

---

## 7. Uruchomienie na emulatorze/telefonie

### Android

```bash
# Otwórz projekt w Android Studio
npx cap open android

# LUB uruchom bezpośrednio (telefon musi być podłączony USB z ADB)
npx cap run android
```

**Telefon Android:**
1. Ustawienia → O telefonie → kliknij 7x w "Numer wersji" 
2. Opcje programisty → Debugowanie USB → włącz
3. Podłącz przez USB i potwierdź authorization

**Emulator Android:**
1. Android Studio → AVD Manager → Create Device
2. Wybierz Pixel 8 (lub inny) → API 34
3. Uruchom AVD, potem `npx cap run android`

### iOS (macOS)

```bash
# Otwórz projekt w Xcode
npx cap open ios

# LUB uruchom bezpośrednio
npx cap run ios
```

W Xcode:
1. Wybierz urządzenie lub symulator z listy u góry
2. Kliknij ▶ (Run)

---

## 8. Budowanie AAB (Google Play)

### Wygeneruj keystore (jednorazowo)

```bash
keytool -genkey -v -keystore release.keystore -alias agatclean \
  -keyalg RSA -keysize 2048 -validity 10000
```

Zapisz hasła! Bez nich nie opublikujesz aktualizacji.

### Zbuduj AAB w Android Studio

1. `npx cap open android`
2. Build → **Generate Signed Bundle / APK**
3. Wybierz **Android App Bundle (AAB)**
4. Wskaż `release.keystore`, podaj alias i hasła
5. Wybierz `release` → kliknij **Create**

Wynikowy plik: `android/app/build/outputs/bundle/release/app-release.aab`

### Alternatywnie – z linii poleceń

```bash
cd android
./gradlew bundleRelease
```

Plik trafia do: `android/app/build/outputs/bundle/release/app-release.aab`

Podpianie (jeśli nie podpisałeś przez Android Studio):
```bash
jarsigner -verbose -sigalg SHA256withRSA -digestalg SHA-256 \
  -keystore release.keystore app-release.aab agatclean
```

---

## 9. Budowanie IPA (App Store)

> Wymagany komputer Mac z Xcode!

### Konfiguracja provisioning (jednorazowo)

1. Zaloguj się do Xcode → Preferences → Accounts → dodaj Apple ID
2. Otwórz projekt: `npx cap open ios`
3. W Xcode → wybierz target `App` → Signing & Capabilities
4. Zaznacz **Automatically manage signing**
5. Wybierz swój Team

### Budowanie IPA

1. Xcode → Product → **Archive**
2. Po archiwizacji otwiera się Organizer
3. Kliknij **Distribute App** → App Store Connect → Upload

### Z linii poleceń (CI/CD)

```bash
cd ios/App
xcodebuild -workspace App.xcworkspace \
  -scheme App \
  -configuration Release \
  -archivePath build/App.xcarchive \
  archive

xcodebuild -exportArchive \
  -archivePath build/App.xcarchive \
  -exportOptionsPlist ExportOptions.plist \
  -exportPath build/
```

---

## 10. Podpisywanie i publikacja

### Google Play

1. Otwórz https://play.google.com/console
2. **Create app** → wypełnij dane
3. Release → Production → **Create new release**
4. Prześlij plik `.aab`
5. Uzupełnij listing (opis, screenshoty)
6. Wyślij do recenzji

**Minimalne wymagania:**
- Ikona 512×512 PNG
- Feature graphic 1024×500 PNG  
- Min 2 screenshoty telefonu

### App Store

1. Otwórz https://appstoreconnect.apple.com
2. **New App** → wypełnij dane (Bundle ID: `pl.agatclean.app`)
3. Prześlij build przez Xcode Organizer lub Transporter
4. Uzupełnij metadane, screenshoty
5. Submit for Review

---

## 11. Firestore – migracja danych

### Jak to działa po zmianach

- Gdy użytkownik się **loguje**, Flask zapisuje `uid` w sesji
- `load_data()` najpierw szuka danych w Firestore (`users/{uid}/appdata/main`)
- Jeśli brak danych w Firestore, importuje `data.json` jako punkt startowy
- `save_data()` zapisuje do Firestore (z fallbackiem do pliku)
- Klient (przeglądarka/aplikacja mobilna) inicjalizuje Firebase JS SDK
- **Firestore offline persistence** (IndexedDB) działa automatycznie – dane dostępne bez internetu
- `onSnapshot` aktualizuje UI gdy dane zmienią się na innym urządzeniu

### Ręczna migracja istniejących danych

Jeśli masz dane w `data.json` i chcesz je przesłać do Firestore:

```python
# Uruchom ten skrypt jednorazowo
from firebase_config import get_firestore
import json

with open("data.json") as f:
    data = json.load(f)

db = get_firestore()
uid = "WPISZ_SWOJ_UID"  # z Firebase Console → Authentication → Users
db.collection("users").document(uid).collection("appdata").document("main").set(data)
print("Dane zmigrowane!")
```

### Sprawdzenie UID

W Firebase Console → Authentication → Users – w kolumnie "User UID".

---

## 12. Rozwiązywanie problemów

### "CLEARTEXT communication not permitted" (Android)

W `capacitor.config.json` sprawdź `"androidScheme": "https"` i że URL serwera używa HTTPS.

### Biały ekran po uruchomieniu

1. Sprawdź URL w `capacitor.config.json` → `server.url`
2. Otwórz Chrome na komputerze → `chrome://inspect` → podłącz urządzenie
3. Sprawdź konsolę JavaScript

### "Failed to load resource" dla ikon

Uruchom: `python generate_icons.py` → pliki ikon muszą istnieć w `static/icons/`

### Firestore "Missing or insufficient permissions"

Sprawdź reguły bezpieczeństwa w Firebase Console → Firestore → Rules.

### `npm run icons` nie generuje plików

```bash
npx @capacitor/assets generate --iconBackgroundColor '#1a73e8' --splashBackgroundColor '#f7faf9'
```

### CocoaPods błędy (iOS)

```bash
cd ios/App
pod deintegrate
pod install
```

### Aplikacja nie aktualizuje się po `npx cap sync`

```bash
npx cap sync android  # lub ios
npx cap copy android
```

---

## Szybki przewodnik poleceń

```bash
# 1. Instalacja
npm install

# 2. Generowanie ikon
python generate_icons.py
npm run icons

# 3. Dodanie platform
npx cap add android
npx cap add ios        # tylko macOS

# 4. Synchronizacja po zmianach kodu
npx cap sync

# 5. Uruchomienie
npx cap open android   # otwiera Android Studio
npx cap open ios       # otwiera Xcode

# 6. Deploy backendu na Render
git add -A
git commit -m "Mobile app setup"
git push
```

---

## Struktura plików po konfiguracji

```
AgatClean/
├── android/            ← wygenerowane przez npx cap add android
├── ios/                ← wygenerowane przez npx cap add ios
├── www/
│   └── index.html      ← fallback gdy serwer niedostępny
├── assets/
│   ├── icon.png        ← 1024x1024 (generuje generate_icons.py)
│   └── splash.png      ← 2732x2732
├── static/
│   ├── manifest.json
│   ├── sw.js           ← zaktualizowany
│   └── icons/          ← ikony PWA
├── app.py              ← zaktualizowany (Firestore + API)
├── firebase_config.py  ← zaktualizowany (Firestore Admin SDK)
├── capacitor.config.json ← nowy
├── package.json        ← nowy
├── generate_icons.py   ← nowy skrypt
└── requirements.txt    ← zaktualizowany (firebase-admin)
```
