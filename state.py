from collections import deque
from datetime import datetime
import threading
from typing import Any, Dict, List, Optional


MAX_LOG_ENTRIES = 200


class SearchState:
    """Thread-safe state container for background scraping tasks."""

    def __init__(self, total_key: str = "total_items", collected_key: str = "collected_items") -> None:
        self._lock = threading.Lock()
        self._total_key = total_key
        self._collected_key = collected_key
        self._run_id: int = 0
        self._is_searching = False
        self._status = "idle"
        self._progress: float = 0
        self._status_message = "Pronto para iniciar"
        self._log_messages: deque[str] = deque(maxlen=MAX_LOG_ENTRIES)
        self._results: List[Dict[str, Any]] = []
        self._total = 0
        self._collected = 0

    @property
    def is_searching(self) -> bool:
        with self._lock:
            return self._is_searching

    @property
    def run_id(self) -> int:
        with self._lock:
            return self._run_id

    def is_run_active(self, run_id: Optional[int] = None) -> bool:
        with self._lock:
            return self._is_searching and (run_id is None or run_id == self._run_id)

    def start(self) -> bool:
        """Atomically transition to searching state. Returns False if already running."""
        with self._lock:
            if self._is_searching:
                return False
            self._run_id += 1
            self._is_searching = True
            self._status = "running"
            self._progress = 0
            self._status_message = "Iniciando busca..."
            self._log_messages.clear()
            self._results = []
            self._total = 0
            self._collected = 0
            return True

    def stop(self, run_id: Optional[int] = None) -> None:
        with self._lock:
            if run_id is not None and run_id != self._run_id:
                return
            self._is_searching = False
            if self._status == "running":
                self._status = "stopped"
                self._status_message = "Busca interrompida"

    def finish(self, message: str, run_id: Optional[int] = None) -> None:
        with self._lock:
            if run_id is not None and (run_id != self._run_id or not self._is_searching):
                return
            self._is_searching = False
            self._status = "complete"
            self._progress = 100
            self._status_message = message
            self._append_log_locked(message)

    def fail(self, message: str, run_id: Optional[int] = None) -> None:
        with self._lock:
            if run_id is not None and run_id != self._run_id:
                return
            self._is_searching = False
            self._status = "error"
            self._status_message = message
            self._append_log_locked(message)

    def log(self, message: str, run_id: Optional[int] = None) -> None:
        with self._lock:
            if run_id is not None and run_id != self._run_id:
                return
            self._append_log_locked(message)

    def _append_log_locked(self, message: str) -> None:
        timestamp = datetime.now().strftime("%H:%M:%S")
        entry = f"{timestamp} - {message}"
        self._log_messages.append(entry)
        print(entry)

    def update_progress(self, progress: float, message: str, run_id: Optional[int] = None) -> None:
        with self._lock:
            if run_id is not None and run_id != self._run_id:
                return
            self._progress = max(0, min(100, round(progress, 1)))
            self._status_message = message
            self._append_log_locked(message)

    def set_total(self, total: int, run_id: Optional[int] = None) -> None:
        with self._lock:
            if run_id is not None and run_id != self._run_id:
                return
            self._total = total

    def set_results(self, results: List[Dict[str, Any]], run_id: Optional[int] = None) -> None:
        with self._lock:
            if run_id is not None and run_id != self._run_id:
                return
            self._results = list(results)
            self._collected = len(self._results)

    def get_results(self) -> List[Dict[str, Any]]:
        with self._lock:
            return list(self._results)

    def snapshot(self, include_results: bool = True) -> Dict[str, Any]:
        with self._lock:
            payload: Dict[str, Any] = {
                "is_searching": self._is_searching,
                "status": self._status,
                "progress": self._progress,
                "status_message": self._status_message,
                "log_messages": list(self._log_messages),
                self._total_key: self._total,
                self._collected_key: self._collected,
            }
            if include_results:
                payload["results"] = list(self._results)
            return payload
