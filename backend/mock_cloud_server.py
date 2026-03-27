#!/usr/bin/env python3
"""
PHASE 3: Mock Cloud Server

Simulates cloud endpoints for testing edge→cloud event transmission.
Useful for testing network resilience, batching, and cloud integration.

Usage:
    python mock_cloud_server.py --port 9000
    python mock_cloud_server.py --port 9000 --latency 500 --failure-rate 0.1
    curl -X POST http://localhost:9000/events -H "Content-Type: application/json" -d '{"test": "data"}'
"""

import argparse
import json
import time
import random
import threading
from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional
from pathlib import Path
import sqlite3

from fastapi import FastAPI, HTTPException, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel
import uvicorn


class CloudEventBatch(BaseModel):
    """Batch of events from edge devices."""
    edge_device_id: str
    events: List[Dict[str, Any]]
    batch_timestamp: str


class MockCloudConfig:
    """Configuration for mock cloud behavior."""
    def __init__(self,
                 latency_ms: int = 100,
                 failure_rate: float = 0.05,
                 batch_size: int = 10,
                 storage_path: str = "mock_cloud_storage.db"):
        self.latency_ms = latency_ms
        self.failure_rate = failure_rate
        self.batch_size = batch_size
        self.storage_path = storage_path


class MockCloudStorage:
    """Simulated cloud storage with SQLite."""

    def __init__(self, db_path: str):
        self.db_path = db_path
        self._init_database()

    def _init_database(self):
        """Initialize database schema."""
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS events (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    edge_device_id TEXT,
                    room_id TEXT,
                    timestamp TEXT,
                    room_state TEXT,
                    people_count INTEGER,
                    energy_waste_detected BOOLEAN,
                    energy_saved_kwh REAL,
                    confidence REAL,
                    received_at TEXT,
                    raw_json TEXT
                )
            """)

            conn.execute("""
                CREATE TABLE IF NOT EXISTS device_status (
                    device_id TEXT PRIMARY KEY,
                    last_seen TEXT,
                    event_count INTEGER,
                    last_event_time TEXT
                )
            """)

            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_room_timestamp
                ON events(room_id, timestamp)
            """)

            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_waste_events
                ON events(energy_waste_detected, timestamp)
            """)

    def store_event(self, edge_device_id: str, event_data: Dict[str, Any]):
        """Store a single event."""
        received_at = datetime.utcnow().isoformat()

        with sqlite3.connect(self.db_path) as conn:
            # Store event
            conn.execute("""
                INSERT INTO events (
                    edge_device_id, room_id, timestamp, room_state,
                    people_count, energy_waste_detected, energy_saved_kwh,
                    confidence, received_at, raw_json
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                edge_device_id,
                event_data.get('room_id'),
                event_data.get('timestamp'),
                event_data.get('room_state'),
                event_data.get('people_count'),
                event_data.get('energy_waste_detected'),
                event_data.get('energy_saved_kwh'),
                event_data.get('confidence'),
                received_at,
                json.dumps(event_data)
            ))

            # Update device status
            conn.execute("""
                INSERT OR REPLACE INTO device_status (
                    device_id, last_seen, event_count, last_event_time
                ) VALUES (
                    ?, ?,
                    COALESCE((SELECT event_count FROM device_status WHERE device_id = ?), 0) + 1,
                    ?
                )
            """, (edge_device_id, received_at, edge_device_id, event_data.get('timestamp')))

    def get_stats(self) -> Dict[str, Any]:
        """Get storage statistics."""
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row

            # Total events
            total_events = conn.execute("SELECT COUNT(*) FROM events").fetchone()[0]

            # Events by state
            state_counts = dict(conn.execute("""
                SELECT room_state, COUNT(*)
                FROM events
                GROUP BY room_state
            """).fetchall())

            # Waste events
            waste_events = conn.execute("""
                SELECT COUNT(*) FROM events WHERE energy_waste_detected = 1
            """).fetchone()[0]

            # Active devices
            active_devices = conn.execute("""
                SELECT COUNT(*) FROM device_status
                WHERE last_seen > datetime('now', '-1 hour')
            """).fetchone()[0]

            # Recent events (last hour)
            recent_events = conn.execute("""
                SELECT COUNT(*) FROM events
                WHERE received_at > datetime('now', '-1 hour')
            """).fetchone()[0]

            return {
                "total_events": total_events,
                "waste_events": waste_events,
                "waste_percentage": (waste_events / total_events * 100) if total_events > 0 else 0,
                "state_distribution": state_counts,
                "active_devices": active_devices,
                "recent_events_1h": recent_events,
                "storage_path": self.db_path
            }

    def query_events(self,
                     room_id: Optional[str] = None,
                     device_id: Optional[str] = None,
                     waste_only: bool = False,
                     limit: int = 100) -> List[Dict[str, Any]]:
        """Query stored events."""
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row

            query = "SELECT * FROM events WHERE 1=1"
            params = []

            if room_id:
                query += " AND room_id = ?"
                params.append(room_id)

            if device_id:
                query += " AND edge_device_id = ?"
                params.append(device_id)

            if waste_only:
                query += " AND energy_waste_detected = 1"

            query += " ORDER BY timestamp DESC LIMIT ?"
            params.append(limit)

            return [dict(row) for row in conn.execute(query, params).fetchall()]


class MockCloudServer:
    """Mock cloud server simulation."""

    def __init__(self, config: MockCloudConfig):
        self.config = config
        self.storage = MockCloudStorage(config.storage_path)
        self.app = FastAPI(title="Mock Cloud Server", version="1.0.0")
        self.setup_routes()

        # Statistics
        self.requests_received = 0
        self.requests_failed = 0
        self.start_time = datetime.utcnow()

    def setup_routes(self):
        """Setup FastAPI routes."""

        # CORS middleware
        self.app.add_middleware(
            CORSMiddleware,
            allow_origins=["*"],
            allow_credentials=True,
            allow_methods=["*"],
            allow_headers=["*"],
        )

        @self.app.post("/events")
        async def receive_single_event(event: Dict[str, Any], background_tasks: BackgroundTasks):
            """Receive single event from edge device."""
            return await self._process_request(
                lambda: self._store_single_event("unknown_device", event),
                background_tasks
            )

        @self.app.post("/events/batch")
        async def receive_event_batch(batch: CloudEventBatch, background_tasks: BackgroundTasks):
            """Receive batch of events from edge device."""
            return await self._process_request(
                lambda: self._store_event_batch(batch),
                background_tasks
            )

        @self.app.post("/devices/{device_id}/events")
        async def receive_device_event(device_id: str, event: Dict[str, Any], background_tasks: BackgroundTasks):
            """Receive event from specific device."""
            return await self._process_request(
                lambda: self._store_single_event(device_id, event),
                background_tasks
            )

        @self.app.get("/stats")
        async def get_cloud_stats():
            """Get cloud storage statistics."""
            storage_stats = self.storage.get_stats()
            uptime = datetime.utcnow() - self.start_time

            return {
                "server_stats": {
                    "uptime_seconds": uptime.total_seconds(),
                    "requests_received": self.requests_received,
                    "requests_failed": self.requests_failed,
                    "success_rate": (
                        (self.requests_received - self.requests_failed) / self.requests_received
                        if self.requests_received > 0 else 0
                    ),
                    "config": {
                        "latency_ms": self.config.latency_ms,
                        "failure_rate": self.config.failure_rate,
                        "batch_size": self.config.batch_size
                    }
                },
                "storage_stats": storage_stats
            }

        @self.app.get("/events")
        async def query_events(
            room_id: Optional[str] = None,
            device_id: Optional[str] = None,
            waste_only: bool = False,
            limit: int = 100
        ):
            """Query stored events."""
            events = self.storage.query_events(
                room_id=room_id,
                device_id=device_id,
                waste_only=waste_only,
                limit=limit
            )
            return {"events": events, "count": len(events)}

        @self.app.delete("/reset")
        async def reset_storage():
            """Reset all stored data (for testing)."""
            import os
            if os.path.exists(self.config.storage_path):
                os.remove(self.config.storage_path)
            self.storage = MockCloudStorage(self.config.storage_path)
            self.requests_received = 0
            self.requests_failed = 0
            self.start_time = datetime.utcnow()
            return {"message": "Storage reset successfully"}

    async def _process_request(self, operation, background_tasks: BackgroundTasks):
        """Process request with simulated latency and failures."""
        self.requests_received += 1
        request_id = self.requests_received

        # Simulate network latency
        if self.config.latency_ms > 0:
            await self._simulate_latency()

        # Simulate random failures
        if random.random() < self.config.failure_rate:
            self.requests_failed += 1
            print(f"[CLOUD] Request {request_id}: Simulated failure")
            raise HTTPException(
                status_code=500,
                detail="Simulated cloud failure"
            )

        # Process in background to simulate async cloud processing
        background_tasks.add_task(operation)

        print(f"[CLOUD] Request {request_id}: Accepted")
        return {
            "status": "accepted",
            "request_id": request_id,
            "message": "Event(s) received and processing"
        }

    async def _simulate_latency(self):
        """Simulate network latency."""
        import asyncio
        latency_seconds = self.config.latency_ms / 1000.0
        # Add some random variation (±25%)
        actual_latency = latency_seconds * (0.75 + 0.5 * random.random())
        await asyncio.sleep(actual_latency)

    def _store_single_event(self, device_id: str, event_data: Dict[str, Any]):
        """Store single event (background task)."""
        try:
            self.storage.store_event(device_id, event_data)
            print(f"[CLOUD] Stored event from {device_id}: {event_data.get('room_state', 'unknown')}")
        except Exception as e:
            print(f"[CLOUD] Failed to store event: {e}")

    def _store_event_batch(self, batch: CloudEventBatch):
        """Store event batch (background task)."""
        try:
            for event_data in batch.events:
                self.storage.store_event(batch.edge_device_id, event_data)
            print(f"[CLOUD] Stored {len(batch.events)} events from {batch.edge_device_id}")
        except Exception as e:
            print(f"[CLOUD] Failed to store batch: {e}")


def main():
    parser = argparse.ArgumentParser(
        description="PHASE 3: Mock Cloud Server for Edge→Cloud Testing",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
    # Start basic cloud server
    python mock_cloud_server.py --port 9000

    # Simulate high latency and failures
    python mock_cloud_server.py --port 9000 --latency 1000 --failure-rate 0.2

    # Test with curl
    curl -X POST http://localhost:9000/events \\
         -H "Content-Type: application/json" \\
         -d '{"room_id": "test", "room_state": "EMPTY_WASTING"}'

    # View statistics
    curl http://localhost:9000/stats

    # Query stored events
    curl http://localhost:9000/events?waste_only=true&limit=10
        """
    )

    parser.add_argument(
        "--port",
        type=int,
        default=9000,
        help="Server port (default: 9000)"
    )
    parser.add_argument(
        "--host",
        default="127.0.0.1",
        help="Server host (default: 127.0.0.1)"
    )
    parser.add_argument(
        "--latency",
        type=int,
        default=100,
        help="Simulated network latency in milliseconds (default: 100)"
    )
    parser.add_argument(
        "--failure-rate",
        type=float,
        default=0.05,
        help="Simulated failure rate (0.0-1.0, default: 0.05)"
    )
    parser.add_argument(
        "--storage",
        default="mock_cloud_storage.db",
        help="SQLite storage file (default: mock_cloud_storage.db)"
    )

    args = parser.parse_args()

    # Validate arguments
    if not 0 <= args.failure_rate <= 1:
        print("[ERROR] Failure rate must be between 0.0 and 1.0")
        return 1

    if args.port < 1 or args.port > 65535:
        print("[ERROR] Port must be between 1 and 65535")
        return 1

    # Create mock cloud server
    config = MockCloudConfig(
        latency_ms=args.latency,
        failure_rate=args.failure_rate,
        storage_path=args.storage
    )

    server = MockCloudServer(config)

    print("="*60)
    print("MOCK CLOUD SERVER")
    print("="*60)
    print(f"Host: {args.host}")
    print(f"Port: {args.port}")
    print(f"Latency: {args.latency}ms")
    print(f"Failure Rate: {args.failure_rate:.1%}")
    print(f"Storage: {args.storage}")
    print("="*60)
    print("\nEndpoints:")
    print(f"  POST http://{args.host}:{args.port}/events")
    print(f"  POST http://{args.host}:{args.port}/events/batch")
    print(f"  POST http://{args.host}:{args.port}/devices/{{device_id}}/events")
    print(f"  GET  http://{args.host}:{args.port}/stats")
    print(f"  GET  http://{args.host}:{args.port}/events")
    print(f"  DELETE http://{args.host}:{args.port}/reset")
    print("\nStarting server...\n")

    # Run server
    try:
        uvicorn.run(
            server.app,
            host=args.host,
            port=args.port,
            log_level="info"
        )
    except KeyboardInterrupt:
        print("\n[INFO] Server stopped by user")
        return 0
    except Exception as e:
        print(f"[ERROR] Server failed: {e}")
        return 1


if __name__ == "__main__":
    import sys
    sys.exit(main())