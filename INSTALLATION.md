# Detaillierte Installationsanleitung

## Für Windows

### 1. Python installieren

1. Download von [python.org](https://www.python.org/downloads/)
2. Installer ausführen
3. ✅ **Wichtig:** "Add Python to PATH" anhaken
4. "Install Now" klicken

### 2. Git installieren (optional, aber empfohlen)

1. Download von [git-scm.com](https://git-scm.com/download/win)
2. Installer mit Standard-Einstellungen ausführen

### 3. Repository herunterladen

**Mit Git:**
```bash
git clone https://github.com/HeikoBre/screening-dashboard-sandbox.git
cd screening-dashboard-sandbox
```

**Ohne Git:**
1. Auf GitHub: Code → Download ZIP
2. ZIP entpacken
3. In PowerShell zum Ordner navigieren:
   ```bash
   cd C:\Pfad\zum\screening-dashboard-sandbox
   ```

### 4. Virtuelle Umgebung erstellen

```bash
python -m venv venv
venv\Scripts\activate
```

Sie sollten jetzt `(venv)` vor Ihrer Eingabeaufforderung sehen.

### 5. Dependencies installieren

```bash
pip install -r requirements.txt
```

### 6. App starten

```bash
streamlit run streamlit_app_improved.py
```

Browser öffnet sich automatisch auf `http://localhost:8501`

## Für Mac

### 1. Python installieren

**Option A: Homebrew (empfohlen)**
```bash
# Homebrew installieren (falls nicht vorhanden)
/bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"

# Python installieren
brew install python
```

**Option B: Von python.org**
1. Download von [python.org](https://www.python.org/downloads/)
2. .pkg Installer ausführen

### 2. Repository klonen

```bash
git clone https://github.com/HeikoBre/screening-dashboard-sandbox.git
cd screening-dashboard-sandbox
```

### 3. Virtuelle Umgebung

```bash
python3 -m venv venv
source venv/bin/activate
```

### 4. Dependencies

```bash
pip install -r requirements.txt
```

### 5. App starten

```bash
streamlit run streamlit_app_improved.py
```

## Für Linux (Ubuntu/Debian)

### 1. Python und Git installieren

```bash
sudo apt update
sudo apt install python3 python3-pip python3-venv git
```

### 2. Repository klonen

```bash
git clone https://github.com/HeikoBre/screening-dashboard-sandbox.git
cd screening-dashboard-sandbox
```

### 3. Virtuelle Umgebung

```bash
python3 -m venv venv
source venv/bin/activate
```

### 4. Dependencies

```bash
pip install -r requirements.txt
```

### 5. App starten

```bash
streamlit run streamlit_app_improved.py
```

## Troubleshooting

### Problem: "python" Befehl nicht gefunden

**Windows:**
```bash
# Verwenden Sie py statt python
py -m venv venv
```

**Mac/Linux:**
```bash
# Verwenden Sie python3
python3 -m venv venv
```

### Problem: pip install schlägt fehl

**Lösung 1: pip upgraden**
```bash
python -m pip install --upgrade pip
```

**Lösung 2: Einzelne Pakete installieren**
```bash
pip install streamlit
pip install pandas
pip install plotly
pip install reportlab
```

### Problem: Port 8501 bereits belegt

**Lösung: Anderen Port verwenden**
```bash
streamlit run streamlit_app_improved.py --server.port 8502
```

### Problem: "Module not found" Fehler

**Ursache:** Virtuelle Umgebung nicht aktiviert

**Lösung:**
```bash
# Windows
venv\Scripts\activate

# Mac/Linux
source venv/bin/activate
```

Sie sollten `(venv)` vor der Eingabeaufforderung sehen.

### Problem: Streamlit öffnet sich nicht automatisch

**Lösung:** Manuell öffnen:
- Öffnen Sie Browser
- Gehen Sie zu: `http://localhost:8501`

## Aktualisierung der App

### Git-Version aktualisieren

```bash
# In den App-Ordner wechseln
cd screening-dashboard-sandbox

# Virtuelle Umgebung aktivieren
source venv/bin/activate  # Mac/Linux
venv\Scripts\activate     # Windows

# Neueste Version holen
git pull

# Dependencies aktualisieren (falls geändert)
pip install -r requirements.txt --upgrade

# App starten
streamlit run streamlit_app_improved.py
```

## Deinstallation

### Vollständige Entfernung

```bash
# Virtuelle Umgebung deaktivieren (falls aktiv)
deactivate

# Ordner löschen
rm -rf screening-dashboard-sandbox  # Mac/Linux
rmdir /s screening-dashboard-sandbox  # Windows
```

## Production Deployment

### Für lokale Netzwerk-Nutzung

```bash
streamlit run streamlit_app_improved.py --server.address 0.0.0.0
```

Dann können andere im gleichen Netzwerk über Ihre IP-Adresse zugreifen:
`http://[Ihre-IP]:8501`

### Für öffentliches Hosting

⚠️ **Vorsicht:** Diese App verarbeitet möglicherweise sensible Daten!

**Empfohlene Plattformen:**
- **Streamlit Community Cloud** (kostenlos, aber öffentlich)
- **Heroku** (kostenpflichtig)
- **AWS/Azure** mit Authentifizierung

**Nicht empfohlen ohne:**
- Passwortschutz
- HTTPS/SSL
- Datenschutz-Prüfung

## Hilfe

Bei Problemen:
1. Prüfen Sie diese Anleitung
2. Suchen Sie in [GitHub Issues](https://github.com/HeikoBre/screening-dashboard-sandbox/issues)
3. Erstellen Sie ein neues Issue mit:
   - Betriebssystem
   - Python-Version (`python --version`)
   - Fehlermeldung (komplett)
   - Was Sie versucht haben
