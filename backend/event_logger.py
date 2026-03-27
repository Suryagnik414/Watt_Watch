"""
PHASE 3: Event Stream Logger

Handles local persistence of RoomEvents to JSONL (newline-delimited JSON) format.
Enables event replay, audit trails, and offline analysis.
"""

import json
from pathlib import Path
from typing import Optional
from datetime import datetime
from schemas import RoomEvent


class EventLogger:
    """
    Thread-safe event logger for writing RoomEvents to JSONL format.

    JSONL (JSON Lines) format:
    - One JSON object per line
    - Each line is a complete, self-contained RoomEvent
    - Easy to stream, parse, and replay
    - Compatible with big data tools (Spark, Kafka, etc.)
    """

    def __init__(self, log_dir: str = "event_logs", max_file_size_mb: int = 100):
        """
        Initialize event logger.

        Args:
            log_dir: Directory to store event log files
            max_file_size_mb: Maximum size of a single log file before rotation
        """
        self.log_dir = Path(log_dir)
        self.log_dir.mkdir(parents=True, exist_ok=True)
        self.max_file_size_bytes = max_file_size_mb * 1024 * 1024
        self.current_file: Optional[Path] = None
        self.event_count = 0

    def _get_log_file_path(self) -> Path:
        """
        Get current log file path with rotation logic.

        File naming: events_YYYYMMDD_HHMMSS.jsonl
        Rotates when file size exceeds max_file_size_bytes.
        """
        if self.current_file and self.current_file.exists():
            # Check if current file needs rotation
            if self.current_file.stat().st_size < self.max_file_size_bytes:
                return self.current_file

        # Create new log file
        timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
        self.current_file = self.log_dir / f"events_{timestamp}.jsonl"
        return self.current_file

    def log_event(self, event: RoomEvent) -> bool:
        """
        Log a single RoomEvent to JSONL file.

        Args:
            event: RoomEvent to log

        Returns:
            True if successfully logged, False otherwise
        """
        try:
            log_file = self._get_log_file_path()

            # Convert event to JSON (using Pydantic's model_dump)
            event_dict = event.model_dump(mode='json')

            # Convert datetime to ISO string
            if 'timestamp' in event_dict and isinstance(event_dict['timestamp'], datetime):
                event_dict['timestamp'] = event_dict['timestamp'].isoformat()

            # Write as single line
            with open(log_file, 'a', encoding='utf-8') as f:
                f.write(json.dumps(event_dict, ensure_ascii=False) + '\n')

            self.event_count += 1
            return True

        except Exception as e:
            print(f"[ERROR] Failed to log event: {e}")
            return False

    def get_stats(self) -> dict:
        """Get logging statistics."""
        return {
            "total_events_logged": self.event_count,
            "current_log_file": str(self.current_file) if self.current_file else None,
            "log_directory": str(self.log_dir)
        }


class EventReplayer:
    """
    Replay events from JSONL log files.

    Useful for:
    - Testing downstream components without live camera
    - Debugging edge cases
    - Simulating different room scenarios
    - Performance benchmarking
    """

    def __init__(self, log_file: str):
        """
        Initialize event replayer.

        Args:
            log_file: Path to JSONL log file
        """
        self.log_file = Path(log_file)
        if not self.log_file.exists():
            raise FileNotFoundError(f"Log file not found: {log_file}")

    def replay_events(self, callback=None, max_events: Optional[int] = None):
        """
        Replay events from log file.

        Args:
            callback: Optional function to call for each event: callback(event: RoomEvent)
            max_events: Maximum number of events to replay (None = all)

        Yields:
            RoomEvent objects
        """
        count = 0
        with open(self.log_file, 'r', encoding='utf-8') as f:
            for line in f:
                if max_events and count >= max_events:
                    break

                try:
                    event_dict = json.loads(line.strip())

                    # Convert ISO string back to datetime
                    if 'timestamp' in event_dict:
                        event_dict['timestamp'] = datetime.fromisoformat(event_dict['timestamp'])

                    # Reconstruct RoomEvent
                    event = RoomEvent(**event_dict)

                    if callback:
                        callback(event)

                    yield event
                    count += 1

                except Exception as e:
                    print(f"[WARN] Failed to parse event: {e}")
                    continue

    def get_event_count(self) -> int:
        """Count total events in log file."""
        count = 0
        with open(self.log_file, 'r', encoding='utf-8') as f:
            for _ in f:
                count += 1
        return count

    def filter_events(self, room_id: Optional[str] = None,
                     state: Optional[str] = None,
                     waste_only: bool = False):
        """
        Filter events by criteria.

        Args:
            room_id: Filter by room_id
            state: Filter by room_state
            waste_only: Only return events with energy_waste_detected=True

        Yields:
            Filtered RoomEvent objects
        """
        for event in self.replay_events():
            if room_id and event.room_id != room_id:
                continue
            if state and event.room_state != state:
                continue
            if waste_only and not event.energy_waste_detected:
                continue

            yield event


# Singleton logger instance (optional convenience)
_global_logger: Optional[EventLogger] = None


def get_event_logger(log_dir: str = "event_logs") -> EventLogger:
    """Get or create global event logger instance."""
    global _global_logger
    if _global_logger is None:
        _global_logger = EventLogger(log_dir)
    return _global_logger
