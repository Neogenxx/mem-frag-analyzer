"""
MEMSIM Backend — zero dependencies, pure stdlib HTTP server
Works on Python 3.8+ including 3.14
"""
import json
import csv
import io
import os
import sys
from http.server import HTTPServer, BaseHTTPRequestHandler
from urllib.parse import urlparse

# Add backend dir to path so simulator.py is importable
sys.path.insert(0, os.path.dirname(__file__))
from simulator import MemorySimulator

sim = MemorySimulator(total_size=1024, allocation_unit=32)
FRONTEND_DIR = os.path.join(os.path.dirname(__file__), "..", "frontend")


class Handler(BaseHTTPRequestHandler):

    def log_message(self, fmt, *args):
        print(f"  {self.address_string()} {fmt % args}")

    # ── CORS + JSON helpers ──────────────────────────────────────────────

    def _cors(self):
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")

    def _send_json(self, data, status=200):
        body = json.dumps(data).encode()
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", len(body))
        self._cors()
        self.end_headers()
        self.wfile.write(body)

    def _send_download(self, body: bytes, mime: str, filename: str):
        self.send_response(200)
        self.send_header("Content-Type", mime)
        self.send_header("Content-Disposition", f'attachment; filename="{filename}"')
        self.send_header("Content-Length", len(body))
        self._cors()
        self.end_headers()
        self.wfile.write(body)

    def _send_file(self, path: str):
        ext = os.path.splitext(path)[1].lower()
        mime = {
            ".html": "text/html; charset=utf-8",
            ".js":   "application/javascript",
            ".css":  "text/css",
            ".ico":  "image/x-icon",
        }.get(ext, "application/octet-stream")
        try:
            with open(path, "rb") as f:
                body = f.read()
            self.send_response(200)
            self.send_header("Content-Type", mime)
            self.send_header("Content-Length", len(body))
            self.end_headers()
            self.wfile.write(body)
        except FileNotFoundError:
            self.send_response(404)
            self.end_headers()

    def _read_json(self):
        length = int(self.headers.get("Content-Length", 0))
        if length == 0:
            return {}
        return json.loads(self.rfile.read(length))

    def _error(self, msg, status=400):
        self._send_json({"error": msg}, status)

    # ── OPTIONS (preflight) ──────────────────────────────────────────────

    def do_OPTIONS(self):
        self.send_response(204)
        self._cors()
        self.end_headers()

    # ── GET ──────────────────────────────────────────────────────────────

    def do_GET(self):
        path = urlparse(self.path).path

        if path == "/" or path == "":
            self._send_file(os.path.join(FRONTEND_DIR, "index.html"))

        elif path == "/api/state":
            self._send_json(sim.get_state())

        elif path == "/api/log":
            self._send_json({"log": sim.event_log})

        elif path == "/api/metrics":
            self._send_json(sim.get_metrics().to_dict())

        elif path == "/api/export/json":
            payload = {
                "config": {"total_size": sim.total_size, "allocation_unit": sim.allocation_unit},
                "events": sim.event_log,
                "final_state": sim.get_state(),
            }
            body = json.dumps(payload, indent=2).encode()
            self._send_download(body, "application/json", "memsim_trace.json")

        elif path == "/api/export/csv":
            buf = io.StringIO()
            w = csv.writer(buf)
            w.writerow(["step","timestamp","action","message",
                        "total_memory_kb","total_allocated_kb","total_free_kb",
                        "internal_frag_kb","external_frag_kb",
                        "largest_free_block_kb","num_free_blocks",
                        "num_allocated_blocks","utilization_pct"])
            for e in sim.event_log:
                m = e.get("metrics", {})
                w.writerow([e.get("step",""), e.get("timestamp",""),
                             e.get("action",""), e.get("message",""),
                             m.get("total_memory",""), m.get("total_allocated",""),
                             m.get("total_free",""), m.get("internal_fragmentation",""),
                             m.get("external_fragmentation",""),
                             m.get("largest_free_block",""), m.get("num_free_blocks",""),
                             m.get("num_allocated_blocks",""), m.get("utilization_pct","")])
            body = buf.getvalue().encode()
            self._send_download(body, "text/csv", "memsim_trace.csv")

        elif path.startswith("/static/"):
            self._send_file(os.path.join(FRONTEND_DIR, path.lstrip("/")))

        else:
            self._error("Not found", 404)

    # ── POST ─────────────────────────────────────────────────────────────

    def do_POST(self):
        path = urlparse(self.path).path

        if path == "/api/allocate":
            data = self._read_json()
            pid      = str(data.get("pid", "")).strip()
            size     = data.get("size")
            strategy = str(data.get("strategy", "first_fit")).lower()
            if not pid or not isinstance(size, (int, float)) or int(size) <= 0:
                return self._error("pid (str) and size (int > 0) required")
            size = int(size)
            if strategy == "first_fit":
                result = sim.allocate_first_fit(pid, size)
            elif strategy == "best_fit":
                result = sim.allocate_best_fit(pid, size)
            elif strategy == "worst_fit":
                result = sim.allocate_worst_fit(pid, size)
            else:
                return self._error(f"Unknown strategy: {strategy}")
            self._send_json({"result": result.to_dict(), "state": sim.get_state()})

        elif path == "/api/free":
            data = self._read_json()
            pid = str(data.get("pid", "")).strip()
            if not pid:
                return self._error("pid required")
            success, message = sim.free(pid)
            self._send_json({"success": success, "message": message, "state": sim.get_state()})

        elif path == "/api/compact":
            message = sim.compact()
            self._send_json({"message": message, "state": sim.get_state()})

        elif path == "/api/reset":
            data = self._read_json()
            total = data.get("total_size")
            unit  = data.get("allocation_unit")
            total = int(total) if total and int(total) > 0 else None
            unit  = int(unit)  if unit  and int(unit)  > 0 else None
            sim.reset(total, unit)
            self._send_json({"message": "Memory reset", "state": sim.get_state()})

        else:
            self._error("Not found", 404)


def run(host="0.0.0.0", port=8000):
    server = HTTPServer((host, port), Handler)
    print("━" * 44)
    print("  MEMSIM — Memory Allocation Simulator")
    print("━" * 44)
    print(f"  Server : http://localhost:{port}")
    print(f"  Python : {sys.version.split()[0]}")
    print(f"  Deps   : none (stdlib only)")
    print("━" * 44)
    print("  Open http://localhost:8000 in your browser")
    print("  Ctrl+C to stop\n")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\n  Server stopped.")


if __name__ == "__main__":
    port = int(sys.argv[1]) if len(sys.argv) > 1 else 8000
    run(port=port)

# ─── Comparison Mode ──────────────────────────────────────────────────────────

from comparison import run_comparison, generate_comparison_csv
from typing import List

class ProcessInput(BaseModel):
    pid: str
    size: int = Field(gt=0)

class ComparisonRequest(BaseModel):
    total_size: int = Field(default=1024, gt=0)
    allocation_unit: int = Field(default=32, gt=0)
    processes: List[ProcessInput]

@app.post("/api/compare")
def compare_strategies(req: ComparisonRequest):
    """Run all three strategies on the same process list and compare"""
    processes = [(p.pid, p.size) for p in req.processes]
    results = run_comparison(req.total_size, req.allocation_unit, processes)
    
    return {
        "comparison": {
            strategy: result.to_dict() 
            for strategy, result in results.items()
        }
    }

@app.post("/api/compare/export/csv")
def export_comparison_csv(req: ComparisonRequest):
    """Export comparison results as CSV"""
    processes = [(p.pid, p.size) for p in req.processes]
    results = run_comparison(req.total_size, req.allocation_unit, processes)
    csv_content = generate_comparison_csv(results)
    
    return StreamingResponse(
        io.BytesIO(csv_content.encode()),
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=memsim_comparison.csv"}
    )

@app.post("/api/compare/export/json")
def export_comparison_json(req: ComparisonRequest):
    """Export comparison results as JSON"""
    processes = [(p.pid, p.size) for p in req.processes]
    results = run_comparison(req.total_size, req.allocation_unit, processes)
    
    payload = {
        "config": {
            "total_size": req.total_size,
            "allocation_unit": req.allocation_unit,
            "processes": [{"pid": p, "size": s} for p, s in processes]
        },
        "results": {
            strategy: {
                **result.to_dict(),
                "blocks": result.final_state["blocks"],
                "events": result.event_log
            }
            for strategy, result in results.items()
        }
    }
    
    content = json.dumps(payload, indent=2)
    return StreamingResponse(
        io.BytesIO(content.encode()),
        media_type="application/json",
        headers={"Content-Disposition": "attachment; filename=memsim_comparison.json"}
    )

@app.get("/compare", response_class=HTMLResponse)
def compare_page():
    html_path = os.path.join(os.path.dirname(__file__), "..", "frontend", "compare.html")
    with open(html_path, "r") as f:
        return HTMLResponse(content=f.read())

# ─── Random Block Generator ───────────────────────────────────────────────────

from random_generator import generate_random_blocks, generate_fragmented_scenario

class RandomBlockRequest(BaseModel):
    total_size: int = Field(default=1024, gt=0)
    allocation_unit: int = Field(default=32, gt=0)
    num_blocks: int = Field(default=5, ge=1, le=20)
    fill_ratio: float = Field(default=0.6, ge=0.1, le=0.9)
    strategy: str = Field(default="first_fit")

@app.post("/api/random/generate")
def generate_random_memory(req: RandomBlockRequest):
    """Generate random allocated blocks in memory"""
    # Reset with new config
    sim.reset(req.total_size, req.allocation_unit)
    
    # Generate random blocks
    blocks = generate_random_blocks(
        req.total_size,
        req.allocation_unit,
        req.num_blocks,
        req.fill_ratio
    )
    
    # Allocate them
    for pid, size in blocks:
        if req.strategy == "first_fit":
            sim.allocate_first_fit(pid, size)
        elif req.strategy == "best_fit":
            sim.allocate_best_fit(pid, size)
        else:
            sim.allocate_worst_fit(pid, size)
    
    return {
        "message": f"Generated {len(blocks)} random blocks",
        "state": sim.get_state()
    }

@app.post("/api/random/fragmented")
def generate_fragmented():
    """Generate a pre-fragmented memory scenario"""
    allocations, to_free = generate_fragmented_scenario(sim.total_size, sim.allocation_unit)
    
    # Reset
    sim.reset()
    
    # Allocate all
    for pid, size in allocations:
        sim.allocate_first_fit(pid, size)
    
    # Free every other one
    for pid in to_free:
        sim.free(pid)
    
    return {
        "message": "Generated fragmented scenario",
        "state": sim.get_state()
    }

# ─── Batch Allocation ─────────────────────────────────────────────────────────

class BatchAllocation(BaseModel):
    processes: List[ProcessInput]
    strategy: str = Field(default="first_fit")

@app.post("/api/allocate/batch")
def allocate_batch(req: BatchAllocation):
    """Allocate multiple processes at once"""
    results = []
    for proc in req.processes:
        if req.strategy == "first_fit":
            result = sim.allocate_first_fit(proc.pid, proc.size)
        elif req.strategy == "best_fit":
            result = sim.allocate_best_fit(proc.pid, proc.size)
        else:
            result = sim.allocate_worst_fit(proc.pid, proc.size)
        results.append(result.to_dict())
    
    return {
        "results": results,
        "state": sim.get_state()
    }

# ─── Download Current State Report ───────────────────────────────────────────

@app.get("/api/download/report")
def download_report():
    """Download current memory state as detailed report"""
    import csv
    import io
    
    output = io.StringIO()
    writer = csv.writer(output)
    
    # Header
    writer.writerow(["MEMSIM Memory State Report"])
    writer.writerow([f"Generated: {datetime.now().isoformat()}"])
    writer.writerow([])
    
    # Config
    writer.writerow(["Configuration"])
    writer.writerow(["Total Memory (KB)", sim.total_size])
    writer.writerow(["Allocation Unit (KB)", sim.allocation_unit])
    writer.writerow([])
    
    # Metrics
    m = sim.get_metrics()
    writer.writerow(["Fragmentation Metrics"])
    writer.writerow(["Total Allocated (KB)", m.total_allocated])
    writer.writerow(["Total Free (KB)", m.total_free])
    writer.writerow(["Internal Fragmentation (KB)", m.internal_fragmentation])
    writer.writerow(["External Fragmentation (KB)", m.external_fragmentation])
    writer.writerow(["Largest Free Block (KB)", m.largest_free_block])
    writer.writerow(["Free Regions", m.num_free_blocks])
    writer.writerow(["Allocated Blocks", m.num_allocated_blocks])
    writer.writerow(["Utilization (%)", m.utilization_pct])
    writer.writerow([])
    
    # Block table
    writer.writerow(["Memory Blocks"])
    writer.writerow(["PID", "Start (KB)", "End (KB)", "Physical (KB)", "Logical (KB)", "Int Frag (KB)", "Type"])
    for b in sim.blocks:
        writer.writerow([
            b.pid or "—",
            b.start,
            b.end,
            b.size,
            b.logical_size or "—",
            b.internal_fragmentation or "—",
            "FREE" if b.is_free else "ALLOC"
        ])
    
    output.seek(0)
    return StreamingResponse(
        io.BytesIO(output.getvalue().encode()),
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=memsim_report.csv"}
    )