"""
Konfiguracja połączenia z Firebase.
Uzupełnij zmienne poniżej zgodnie z instrukcją FIREBASE_SETUP.md
"""

# ─────────────────────────────────────────────────────────
#  1. Ścieżka do pliku serviceAccountKey.json
#     Pobierz z: Firebase Console → Project Settings → Service accounts → Generate new private key
# ─────────────────────────────────────────────────────────
SERVICE_ACCOUNT_KEY_PATH = "agatclean-7fee5-firebase-adminsdk-fbsvc-7ea8ab4a03.json"

# ─────────────────────────────────────────────────────────
#  2. Web API key – z Firebase Console → Project Settings → General → Web API Key
# ─────────────────────────────────────────────────────────
FIREBASE_WEB_API_KEY = "AIzaSyD-xpDHqkddPOOeIR1lO53xIj5QgFZIkWc"

# ─────────────────────────────────────────────────────────
#  3. Klucz tajny Flask (zmień na losowy ciąg!)
# ─────────────────────────────────────────────────────────
SECRET_KEY = "a3f9c1d0b7e54c2f8d9a1c3e7f4b2d8c9e1f0a3b7c6d4e2f9a0b1c2d3e4f5a6"

# ─────────────────────────────────────────────────────────
#  4. Port serwera
# ─────────────────────────────────────────────────────────
APP_PORT = 5000
