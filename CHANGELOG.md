# Changelog

Alle wichtigen Änderungen an diesem Projekt werden in dieser Datei dokumentiert.

Das Format basiert auf [Keep a Changelog](https://keepachangelog.com/de/1.0.0/),
und dieses Projekt folgt [Semantic Versioning](https://semver.org/lang/de/).

## [Unreleased]

### Geplant
- Export als Excel-Datei
- Mehrsprachigkeit (EN/DE)
- Batch-Processing für mehrere CSV-Dateien

## [1.0.0] - 2024-02-16

### Hinzugefügt
- ✨ Initiales Release der Expertenreview gNBS App
- 📊 CSV-Import von LimeSurvey-Exporten
- 🎨 Interaktive Visualisierung mit Pie Charts
- 🎯 Dropdown-Menü für strukturierte Bewertung (4 Optionen)
- 📝 Optionales Freitext-Kommentarfeld
- 📄 PDF-Export mit vollständiger Dokumentation
  - Automatisches Inhaltsverzeichnis
  - Eine Seite pro Gen
  - Farbcodierte Empfehlungen
  - Versions- und Repository-Information
- 📊 CSV-Export für Datenanalyse
  - Vollständige Umfrageergebnisse
  - Abweichungs-Analyse (Umfrage vs. Expertenentscheidung)
  - Strukturiert für wissenschaftliche Publikationen
- ⌨️ Tastatur-Navigation (Links/Rechts-Pfeile)
- 📈 Fortschrittsanzeige in Sidebar
- 🔤 Kursive Gen-Namen (wissenschaftliche Konvention)
- 🎨 Responsives Design mit Streamlit

### Technisch
- Robustes CSV-Parsing (Non-Breaking Spaces, verschiedene Encodings)
- Session-basierte Datenhaltung (keine persistente Speicherung)
- Automatische Git-Versions-Erkennung
- Custom PDF-Canvas mit Seitenzahlen und Footer

### Dokumentation
- Umfassende README.md mit Screenshots
- Vollständige API-Dokumentation im Code
- Beispiel-Daten für Testing

## Versionshistorie

### Versioning Schema
```
MAJOR.MINOR.PATCH

MAJOR: Inkompatible API-Änderungen
MINOR: Neue Funktionen (abwärtskompatibel)
PATCH: Bugfixes (abwärtskompatibel)
```

### Links
[Unreleased]: https://github.com/HeikoBre/screening-dashboard-sandbox/compare/v1.0.0...HEAD
[1.0.0]: https://github.com/HeikoBre/screening-dashboard-sandbox/releases/tag/v1.0.0
