"""
Zero-dependency HTTP server and REST API for the Second Brain application.
Powered by Python standard library (http.server).
"""

from __future__ import annotations
import json
import os
import sys
from http import HTTPStatus
from http.server import HTTPServer, BaseHTTPRequestHandler
from pathlib import Path
from urllib.parse import urlparse, parse_qs
from src.second_brain import SecondBrainService


class SecondBrainHandler(BaseHTTPRequestHandler):
    service: SecondBrainService
    static_dir: Path

    def _set_headers(self, status: int = 200, content_type: str = "application/json"):
        self.send_response(status)
        self.send_header("Content-Type", f"{content_type}; charset=utf-8")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, PUT, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.end_headers()

    def do_OPTIONS(self):
        self._set_headers(200, "text/plain")
        self.wfile.write(b"OK")

    def do_GET(self):
        parsed = urlparse(self.path)
        path = parsed.path
        query = parse_qs(parsed.query)

        # Health check
        if path == "/api/health":
            self._set_headers(200)
            self.wfile.write(json.dumps({"status": "ok", "app": "Second Brain", "version": "1.0.0"}).encode("utf-8"))
            return

        # API: list or search notes
        if path == "/api/notes":
            q = query.get("q", [""])[0]
            cat = query.get("category", [""])[0]
            tag = query.get("tag", [""])[0]
            notes = self.service.search_notes(query=q, category=cat, tag=tag)
            self._set_headers(200)
            self.wfile.write(json.dumps(notes, ensure_ascii=False).encode("utf-8"))
            return

        # API: single note details
        if path == "/api/note":
            note_id = query.get("id", [""])[0]
            if not note_id:
                self._set_headers(400)
                self.wfile.write(json.dumps({"error": "Missing note id"}).encode("utf-8"))
                return
            note = self.service.get_note(note_id)
            if note:
                self._set_headers(200)
                self.wfile.write(json.dumps(note, ensure_ascii=False).encode("utf-8"))
            else:
                self._set_headers(404)
                self.wfile.write(json.dumps({"error": "Note not found"}).encode("utf-8"))
            return

        # API: categories statistics
        if path == "/api/categories":
            stats = self.service.get_categories_stats()
            self._set_headers(200)
            self.wfile.write(json.dumps(stats, ensure_ascii=False).encode("utf-8"))
            return

        # API: tags
        if path == "/api/tags":
            tags = self.service.get_all_tags()
            self._set_headers(200)
            self.wfile.write(json.dumps(tags, ensure_ascii=False).encode("utf-8"))
            return

        # API: knowledge graph
        if path == "/api/graph":
            graph = self.service.get_graph_data()
            self._set_headers(200)
            self.wfile.write(json.dumps(graph, ensure_ascii=False).encode("utf-8"))
            return

        # Serve static files
        if path in ("/", "/index.html"):
            self._serve_file(self.static_dir / "index.html", "text/html")
            return
        elif path == "/warmup":
            self._serve_file(self.static_dir / "warmup.html", "text/html")
            return
        elif path == "/style.css":
            self._serve_file(self.static_dir / "style.css", "text/css")
            return
        elif path == "/app.js":
            self._serve_file(self.static_dir / "app.js", "application/javascript")
            return
        else:
            # Fallback static lookup
            file_candidate = self.static_dir / path.lstrip("/")
            if file_candidate.is_file():
                content_type = "text/plain"
                if file_candidate.suffix == ".html": content_type = "text/html"
                elif file_candidate.suffix == ".css": content_type = "text/css"
                elif file_candidate.suffix == ".js": content_type = "application/javascript"
                self._serve_file(file_candidate, content_type)
            else:
                self._set_headers(404, "text/plain")
                self.wfile.write(b"404 Not Found")

    def do_POST(self):
        parsed = urlparse(self.path)
        if parsed.path == "/api/notes":
            try:
                length = int(self.headers.get("Content-Length", 0))
                body_data = self.rfile.read(length).decode("utf-8")
                payload = json.loads(body_data)

                category = payload.get("category", "Inbox")
                title = payload.get("title", "Нова нотатка").strip()
                content = payload.get("content", "").strip()
                tags = payload.get("tags", [])
                source = payload.get("source", "власний запис")

                if not title:
                    self._set_headers(400)
                    self.wfile.write(json.dumps({"error": "Title cannot be empty"}).encode("utf-8"))
                    return

                new_note = self.service.create_note(category, title, content, tags, source)
                self._set_headers(201)
                self.wfile.write(json.dumps(new_note, ensure_ascii=False).encode("utf-8"))
            except Exception as e:
                self._set_headers(500)
                self.wfile.write(json.dumps({"error": str(e)}).encode("utf-8"))
            return

        self._set_headers(404)
        self.wfile.write(json.dumps({"error": "Endpoint not found"}).encode("utf-8"))

    def do_PUT(self):
        parsed = urlparse(self.path)
        if parsed.path == "/api/note":
            try:
                length = int(self.headers.get("Content-Length", 0))
                body_data = self.rfile.read(length).decode("utf-8")
                payload = json.loads(body_data)

                note_id = payload.get("id", "").strip()
                content = payload.get("content", "")

                if not note_id:
                    self._set_headers(400)
                    self.wfile.write(json.dumps({"error": "Missing note id"}).encode("utf-8"))
                    return

                updated = self.service.update_note(note_id, content)
                if updated:
                    self._set_headers(200)
                    self.wfile.write(json.dumps(updated, ensure_ascii=False).encode("utf-8"))
                else:
                    self._set_headers(404)
                    self.wfile.write(json.dumps({"error": "Note not found to update"}).encode("utf-8"))
            except Exception as e:
                self._set_headers(500)
                self.wfile.write(json.dumps({"error": str(e)}).encode("utf-8"))
            return

        self._set_headers(404)
        self.wfile.write(json.dumps({"error": "Endpoint not found"}).encode("utf-8"))

    def _serve_file(self, file_path: Path, content_type: str):
        if not file_path.exists():
            self._set_headers(404, "text/plain")
            self.wfile.write(b"File not found")
            return
        content = file_path.read_bytes()
        self._set_headers(200, content_type)
        self.wfile.write(content)

    def log_message(self, format, *args):
        # Override to keep server output clean
        pass


def run_server(port: int = 8080, base_dir: Path | str = "."):
    base_path = Path(base_dir).resolve()
    service = SecondBrainService(base_path)
    static_dir = base_path / "src" / "static"

    SecondBrainHandler.service = service
    SecondBrainHandler.static_dir = static_dir

    server_address = ("127.0.0.1", port)
    httpd = HTTPServer(server_address, SecondBrainHandler)
    print(f"🚀 Second Brain Server running locally at http://127.0.0.1:{port}")
    print(f"📁 Notes directory: {service.notes_dir}")
    print(f"🌐 Warmup page: http://127.0.0.1:{port}/warmup")
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("\n🛑 Shutting down server...")
        httpd.server_close()


if __name__ == "__main__":
    port = 8080
    if len(sys.argv) > 1 and sys.argv[1].isdigit():
        port = int(sys.argv[1])
    # Assume script is run from project root or src
    proj_root = Path(__file__).resolve().parent.parent
    run_server(port=port, base_dir=proj_root)
