#!/usr/bin/env python3
"""
Melania Nutrizionista - Candidature CRM Server
Lightweight, zero-dependency Python 3 HTTP server + REST API.
Reads and writes directly to leads_candidature_catania.csv.
"""

import os
import sys
import csv
import json
import shutil
from datetime import datetime
from pathlib import Path
from http.server import HTTPServer, SimpleHTTPRequestHandler
import urllib.parse
import webbrowser

WORKSPACE_DIR = Path(__file__).resolve().parent
CSV_FILE = WORKSPACE_DIR / "leads_candidature_catania.csv"
BACKUP_DIR = WORKSPACE_DIR / ".csv_backups"

CORE_FIELDS = [
    "Cluster",
    "Nome_Struttura_Professionista",
    "Tipologia",
    "Indirizzo",
    "Zona_Quartiere",
    "Logistica_Distanza",
    "Telefono",
    "Email_PEC",
    "Sito_Web_Riferimento",
    "Note_Opportunita_Melania",
    "Stato_Candidatura"
]

OPTIONAL_FIELDS = [
    "Note_Followup",
    "Data_Ultimo_Contatto"
]

def ensure_backup_dir():
    BACKUP_DIR.mkdir(exist_ok=True)

def create_csv_backup():
    ensure_backup_dir()
    if CSV_FILE.exists():
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        backup_path = BACKUP_DIR / f"leads_backup_{timestamp}.csv"
        shutil.copy2(CSV_FILE, backup_path)
        # Keep only the last 15 backups
        backups = sorted(BACKUP_DIR.glob("leads_backup_*.csv"))
        if len(backups) > 15:
            for old_backup in backups[:-15]:
                try:
                    old_backup.unlink()
                except OSError:
                    pass

def get_fieldnames():
    if not CSV_FILE.exists():
        return CORE_FIELDS
    with open(CSV_FILE, mode="r", encoding="utf-8-sig") as f:
        reader = csv.reader(f)
        try:
            header = next(reader)
            clean_header = [h.strip().replace("\ufeff", "") for h in header if h.strip()]
            for fld in CORE_FIELDS:
                if fld not in clean_header:
                    clean_header.append(fld)
            return clean_header
        except StopIteration:
            return CORE_FIELDS

def read_leads():
    if not CSV_FILE.exists():
        return []
    fieldnames = get_fieldnames()
    leads = []
    with open(CSV_FILE, mode="r", encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)
        for idx, row in enumerate(reader):
            lead = {
                "id": idx + 1,
                "Cluster": row.get("Cluster", "").strip(),
                "Nome_Struttura_Professionista": row.get("Nome_Struttura_Professionista", "").strip(),
                "Tipologia": row.get("Tipologia", "").strip(),
                "Indirizzo": row.get("Indirizzo", "").strip(),
                "Zona_Quartiere": row.get("Zona_Quartiere", "").strip(),
                "Logistica_Distanza": row.get("Logistica_Distanza", "").strip(),
                "Telefono": row.get("Telefono", "").strip(),
                "Email_PEC": row.get("Email_PEC", "").strip(),
                "Sito_Web_Riferimento": row.get("Sito_Web_Riferimento", "").strip(),
                "Note_Opportunita_Melania": row.get("Note_Opportunita_Melania", "").strip(),
                "Stato_Candidatura": row.get("Stato_Candidatura", "Da contattare").strip() or "Da contattare",
                "Note_Followup": row.get("Note_Followup", "").strip(),
                "Data_Ultimo_Contatto": row.get("Data_Ultimo_Contatto", "").strip()
            }
            for k, v in row.items():
                clean_k = (k or "").strip().replace("\ufeff", "")
                if clean_k and clean_k not in lead:
                    lead[clean_k] = (v or "").strip()
            leads.append(lead)
    return leads

def write_leads(leads):
    create_csv_backup()
    all_fields = list(CORE_FIELDS)
    has_optional = any(lead.get("Note_Followup") or lead.get("Data_Ultimo_Contatto") for lead in leads)
    if has_optional:
        for opt in OPTIONAL_FIELDS:
            if opt not in all_fields:
                all_fields.append(opt)

    temp_file = WORKSPACE_DIR / "leads_candidature_catania.tmp.csv"
    with open(temp_file, mode="w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=all_fields, quoting=csv.QUOTE_ALL, extrasaction="ignore")
        writer.writeheader()
        for lead in leads:
            writer.writerow(lead)

    temp_file.replace(CSV_FILE)

class CRMRequestHandler(SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=str(WORKSPACE_DIR), **kwargs)

    def do_GET(self):
        parsed = urllib.parse.urlparse(self.path)
        path = parsed.path

        if path in ("/", "/crm", "/crm.html"):
            crm_html_path = WORKSPACE_DIR / "crm.html"
            if crm_html_path.exists():
                self.send_response(200)
                self.send_header("Content-Type", "text/html; charset=utf-8")
                self.end_headers()
                with open(crm_html_path, "rb") as f:
                    self.wfile.write(f.read())
            else:
                self.send_response(404)
                self.send_header("Content-Type", "text/html; charset=utf-8")
                self.end_headers()
                self.wfile.write(b"<h1>crm.html not found</h1>")
            return

        if path == "/api/leads":
            leads = read_leads()
            data = json.dumps({"leads": leads, "total": len(leads)}, ensure_ascii=False).encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Cache-Control", "no-cache, no-store, must-revalidate")
            self.end_headers()
            self.wfile.write(data)
            return

        if path == "/api/stats":
            leads = read_leads()
            clusters = {}
            stati = {}
            for l in leads:
                c = l.get("Cluster") or "Altro"
                s = l.get("Stato_Candidatura") or "Da contattare"
                clusters[c] = clusters.get(c, 0) + 1
                stati[s] = stati.get(s, 0) + 1
            data = json.dumps({"total": len(leads), "clusters": clusters, "stati": stati}, ensure_ascii=False).encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.end_headers()
            self.wfile.write(data)
            return

        if path == "/api/export":
            if CSV_FILE.exists():
                with open(CSV_FILE, "rb") as f:
                    content = f.read()
                self.send_response(200)
                self.send_header("Content-Type", "text/csv; charset=utf-8")
                self.send_header("Content-Disposition", 'attachment; filename="leads_candidature_catania.csv"')
                self.end_headers()
                self.wfile.write(content)
                return
            else:
                self.send_error(404, "CSV not found")
                return

        return super().do_GET()

    def do_POST(self):
        parsed = urllib.parse.urlparse(self.path)
        path = parsed.path

        if path == "/api/leads":
            length = int(self.headers.get("Content-Length", 0))
            body = self.rfile.read(length).decode("utf-8")
            try:
                new_lead = json.loads(body)
            except Exception as e:
                self.send_error(400, f"Invalid JSON: {e}")
                return

            leads = read_leads()
            new_lead["id"] = max([l.get("id", 0) for l in leads], default=0) + 1
            if not new_lead.get("Stato_Candidatura"):
                new_lead["Stato_Candidatura"] = "Da contattare"
            leads.append(new_lead)
            write_leads(leads)

            self.send_response(201)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.end_headers()
            self.wfile.write(json.dumps({"success": True, "lead": new_lead}, ensure_ascii=False).encode("utf-8"))
            return

        self.send_error(404, "Endpoint not found")

    def do_PUT(self):
        parsed = urllib.parse.urlparse(self.path)
        path = parsed.path

        if path.startswith("/api/leads/"):
            lead_id_str = path.replace("/api/leads/", "").strip()
            try:
                lead_id = int(lead_id_str)
            except ValueError:
                self.send_error(400, "Invalid lead id")
                return

            length = int(self.headers.get("Content-Length", 0))
            body = self.rfile.read(length).decode("utf-8")
            try:
                updates = json.loads(body)
            except Exception as e:
                self.send_error(400, f"Invalid JSON: {e}")
                return

            leads = read_leads()
            target_idx = None
            for idx, l in enumerate(leads):
                if l.get("id") == lead_id:
                    target_idx = idx
                    break

            if target_idx is None:
                self.send_error(404, f"Lead id {lead_id} not found")
                return

            for key, val in updates.items():
                if key != "id":
                    leads[target_idx][key] = val

            write_leads(leads)

            self.send_response(200)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.end_headers()
            self.wfile.write(json.dumps({"success": True, "lead": leads[target_idx]}, ensure_ascii=False).encode("utf-8"))
            return

        self.send_error(404, "Endpoint not found")

    def do_DELETE(self):
        parsed = urllib.parse.urlparse(self.path)
        path = parsed.path

        if path.startswith("/api/leads/"):
            lead_id_str = path.replace("/api/leads/", "").strip()
            try:
                lead_id = int(lead_id_str)
            except ValueError:
                self.send_error(400, "Invalid lead id")
                return

            leads = read_leads()
            initial_len = len(leads)
            leads = [l for l in leads if l.get("id") != lead_id]

            if len(leads) == initial_len:
                self.send_error(404, f"Lead id {lead_id} not found")
                return

            write_leads(leads)

            self.send_response(200)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.end_headers()
            self.wfile.write(json.dumps({"success": True, "deleted_id": lead_id}, ensure_ascii=False).encode("utf-8"))
            return

        self.send_error(404, "Endpoint not found")

def run_server(port=8000, auto_open=False):
    actual_port = port
    server = None
    for try_port in [actual_port, 8080, 8888, 5050, 5000]:
        try:
            server = HTTPServer(("127.0.0.1", try_port), CRMRequestHandler)
            actual_port = try_port
            break
        except OSError:
            continue

    if server is None:
        print("Error: Could not bind to any candidate port.")
        sys.exit(1)

    url = f"http://localhost:{actual_port}"
    print("=" * 60)
    print(f" Melania Nutrizionista - Candidature CRM")
    print(f" URL Locale: {url}")
    print(f" Database CSV: {CSV_FILE.name}")
    print(" Premere Ctrl+C per fermare il server.")
    print("=" * 60)
    sys.stdout.flush()

    if auto_open:
        try:
            webbrowser.open(url)
        except Exception:
            pass

    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nArresto server CRM...")
    finally:
        server.server_close()

if __name__ == "__main__":
    auto_open = "--open" in sys.argv
    port = 8000
    for arg in sys.argv[1:]:
        if arg.startswith("--port="):
            try:
                port = int(arg.split("=")[1])
            except ValueError:
                pass
    run_server(port=port, auto_open=auto_open)
