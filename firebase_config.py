"""
Konfiguracja połączenia z Firebase + Firestore Admin SDK.
Uzupełnij zmienne poniżej zgodnie z instrukcją FIREBASE_SETUP.md
"""
import os

# ─────────────────────────────────────────────────────────
#  1. Ścieżka do pliku serviceAccountKey.json
#     Pobierz z: Firebase Console → Project Settings → Service accounts → Generate new private key
# ─────────────────────────────────────────────────────────
SERVICE_ACCOUNT_KEY_PATH = os.environ.get(
    "SERVICE_ACCOUNT_KEY_PATH",
    "agatclean-7fee5-firebase-adminsdk-fbsvc-7ea8ab4a03.json"
)

# ─────────────────────────────────────────────────────────
#  2. Web API key – z Firebase Console → Project Settings → General → Web API Key
# ─────────────────────────────────────────────────────────
FIREBASE_WEB_API_KEY = os.environ.get(
    "FIREBASE_WEB_API_KEY",
    "AIzaSyD-xpDHqkddPOOeIR1lO53xIj5QgFZIkWc"
)

# ─────────────────────────────────────────────────────────
#  3. Klucz tajny Flask (zmień na losowy ciąg!)
# ─────────────────────────────────────────────────────────
SECRET_KEY = os.environ.get(
    "SECRET_KEY",
    "a3f9c1d0b7e54c2f8d9a1c3e7f4b2d8c9e1f0a3b7c6d4e2f9a0b1c2d3e4f5a6"
)

# ─────────────────────────────────────────────────────────
#  4. Port serwera
# ─────────────────────────────────────────────────────────
APP_PORT = 5000

# ─────────────────────────────────────────────────────────
#  5. Konfiguracja Firebase JS SDK (client-side) – do wstrzyknięcia w HTML
#     Wartości znajdziesz w: Firebase Console → Project Settings → General → Your apps → Web app
# ─────────────────────────────────────────────────────────
FIREBASE_CLIENT_CONFIG = {
    "apiKey":            os.environ.get("FIREBASE_WEB_API_KEY", "AIzaSyD-xpDHqkddPOOeIR1lO53xIj5QgFZIkWc"),
    "authDomain":        os.environ.get("FIREBASE_AUTH_DOMAIN",    "agatclean-7fee5.firebaseapp.com"),
    "projectId":         os.environ.get("FIREBASE_PROJECT_ID",     "agatclean-7fee5"),
    "storageBucket":     os.environ.get("FIREBASE_STORAGE_BUCKET", "agatclean-7fee5.appspot.com"),
    "messagingSenderId": os.environ.get("FIREBASE_MESSAGING_ID",   ""),
    "appId":             os.environ.get("FIREBASE_APP_ID",         ""),
}

# ─────────────────────────────────────────────────────────
#  6. Inicjalizacja Firebase Admin SDK + Firestore
#     (importy tutaj, żeby cały projekt miał jeden punkt inicjalizacji)
# ─────────────────────────────────────────────────────────
_db = None  # Firestore client (leniwa inicjalizacja)

def get_firestore():
    """Zwraca klienta Firestore. Inicjalizuje Firebase Admin SDK przy pierwszym wywołaniu."""
    global _db
    if _db is not None:
        return _db
    try:
        import firebase_admin
        from firebase_admin import credentials, firestore

        if not firebase_admin._apps:
            key_path = SERVICE_ACCOUNT_KEY_PATH
            if os.path.exists(key_path):
                cred = credentials.Certificate(key_path)
            else:
                # Na Render możesz ustawić zmienną środowiskową GOOGLE_APPLICATION_CREDENTIALS
                cred = credentials.ApplicationDefault()
            firebase_admin.initialize_app(cred)

        _db = firestore.client()
        return _db
    except Exception as exc:
        # Jeśli firebase-admin nie jest zainstalowany lub brak klucza – fallback do data.json
        print(f"[Firestore] Niedostępny: {exc}. Używam data.json.")
        return None
