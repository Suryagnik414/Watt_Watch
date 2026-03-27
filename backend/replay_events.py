#!/usr/bin/env python3
"""
PHASE 3: Event Replay Script

Standalone script for replaying logged events from JSONL files.
Useful for testing, debugging, and simulating different room scenarios.

Usage:
    python replay_events.py --help
    python replay_events.py event_logs/events_20260327_143000.jsonl
    python replay_events.py event_logs/ --room-id room_101 --waste-only
    python replay_events.py event_logs/ --simulate-cloud --endpoint http://cloud.example.com/events
"""

import argparse
import sys
import time
import json
import requests
from pathlib import Path
from datetime import datetime, timedelta
from typing import Optional, List, Dict, Any
import os

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from event_logger import EventReplayer, EventLogger
from schemas import RoomEvent


class EventReplaySimulator:
    """
    Simulates event replay with various modes and outputs.
    """

    def __init__(self,
                 cloud_endpoint: Optional[str] = None,
                 output_file: Optional[str] = None,
                 real_time: bool = False,
                 speed_multiplier: float = 1.0):
        """
        Initialize replay simulator.

        Args:
            cloud_endpoint: URL for simulated cloud event posting
            output_file: File to write replay results
            real_time: If True, replay events at original timing
            speed_multiplier: Speed up/slow down replay (1.0 = normal)
        """
        self.cloud_endpoint = cloud_endpoint
        self.output_file = output_file
        self.real_time = real_time
        self.speed_multiplier = speed_multiplier

        self.events_processed = 0
        self.alerts_generated = 0
        self.cloud_posts_success = 0
        self.cloud_posts_failed = 0

        # Output file handle
        self.output_fp = None
        if output_file:
            self.output_fp = open(output_file, 'w', encoding='utf-8')
            self._log_output(f"# Event Replay Started: {datetime.utcnow().isoformat()}")

    def __del__(self):
        if self.output_fp:
            self.output_fp.close()

    def _log_output(self, message: str):
        """Log message to output file and/or console."""
        print(message)
        if self.output_fp:
            self.output_fp.write(message + '\n')
            self.output_fp.flush()

    def replay_event(self, event: RoomEvent) -> bool:
        """
        Replay a single event with all configured outputs.

        Returns:
            True if replay successful, False otherwise
        """
        try:
            self.events_processed += 1

            # Format event for display
            timestamp_str = event.timestamp.strftime("%Y-%m-%d %H:%M:%S")
            alert_str = "🚨 ALERT" if event.energy_waste_detected else "✅ OK"

            self._log_output(
                f"[{timestamp_str}] {event.room_id}: {event.room_state} "
                f"(people={event.people_count}, appliances={len(event.appliances)}) {alert_str}"
            )

            # Count alerts
            if event.energy_waste_detected:
                self.alerts_generated += 1
                self._log_output(
                    f"  └─ Energy waste: {event.energy_saved_kwh:.3f} kWh potential savings "
                    f"(duration: {event.duration_sec}s)"
                )

            # Simulate cloud posting
            if self.cloud_endpoint:
                self._post_to_cloud(event)

            return True

        except Exception as e:
            self._log_output(f"[ERROR] Failed to replay event: {e}")
            return False

    def _post_to_cloud(self, event: RoomEvent):
        """Simulate posting event to cloud endpoint."""
        try:
            # Convert event to JSON
            event_data = event.model_dump(mode='json')
            if 'timestamp' in event_data:
                event_data['timestamp'] = event_data['timestamp'].isoformat()

            # Post to cloud (with timeout)
            response = requests.post(
                self.cloud_endpoint,
                json=event_data,
                timeout=5.0,
                headers={'Content-Type': 'application/json'}
            )

            if response.status_code == 200:
                self.cloud_posts_success += 1
                self._log_output(f"  └─ Cloud POST: ✅ SUCCESS (200)")
            else:
                self.cloud_posts_failed += 1
                self._log_output(f"  └─ Cloud POST: ❌ FAILED ({response.status_code})")

        except requests.RequestException as e:
            self.cloud_posts_failed += 1
            self._log_output(f"  └─ Cloud POST: ❌ ERROR ({e})")

    def get_stats(self) -> Dict[str, Any]:
        """Get replay statistics."""
        return {
            "events_processed": self.events_processed,
            "alerts_generated": self.alerts_generated,
            "cloud_posts_success": self.cloud_posts_success,
            "cloud_posts_failed": self.cloud_posts_failed,
            "cloud_success_rate": (
                self.cloud_posts_success / (self.cloud_posts_success + self.cloud_posts_failed)
                if (self.cloud_posts_success + self.cloud_posts_failed) > 0 else 0.0
            )
        }


def find_log_files(path: str) -> List[Path]:
    """Find all JSONL event log files in a path."""
    path_obj = Path(path)

    if path_obj.is_file():
        return [path_obj]
    elif path_obj.is_dir():
        # Find all .jsonl files in directory
        jsonl_files = list(path_obj.glob("*.jsonl"))
        jsonl_files.extend(path_obj.glob("events_*.jsonl"))
        return sorted(set(jsonl_files))  # Remove duplicates and sort
    else:
        raise FileNotFoundError(f"Path not found: {path}")


def main():
    parser = argparse.ArgumentParser(
        description="PHASE 3: Event Replay Script",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
    # Replay single log file
    python replay_events.py event_logs/events_20260327_143000.jsonl

    # Replay all logs in directory, filter by room
    python replay_events.py event_logs/ --room-id room_101

    # Show only energy waste alerts
    python replay_events.py event_logs/ --waste-only

    # Simulate cloud posting
    python replay_events.py event_logs/ --simulate-cloud --endpoint http://localhost:9000/events

    # Real-time replay with speed control
    python replay_events.py event_logs/ --real-time --speed 2.0

    # Generate report file
    python replay_events.py event_logs/ --output replay_report.txt

    # Statistics only
    python replay_events.py event_logs/ --stats-only
        """
    )

    parser.add_argument(
        "path",
        help="Path to JSONL log file or directory containing log files"
    )

    # Filtering options
    parser.add_argument(
        "--room-id",
        help="Filter events by room ID"
    )
    parser.add_argument(
        "--state",
        choices=["OCCUPIED", "EMPTY_SAFE", "EMPTY_WASTING"],
        help="Filter events by room state"
    )
    parser.add_argument(
        "--waste-only",
        action="store_true",
        help="Show only energy waste events"
    )
    parser.add_argument(
        "--max-events",
        type=int,
        help="Maximum number of events to replay"
    )

    # Timing options
    parser.add_argument(
        "--real-time",
        action="store_true",
        help="Replay events at original timing intervals"
    )
    parser.add_argument(
        "--speed",
        type=float,
        default=1.0,
        help="Speed multiplier for real-time replay (default: 1.0)"
    )

    # Output options
    parser.add_argument(
        "--output",
        help="Write replay results to file"
    )
    parser.add_argument(
        "--stats-only",
        action="store_true",
        help="Show statistics summary only (no event details)"
    )

    # Cloud simulation
    parser.add_argument(
        "--simulate-cloud",
        action="store_true",
        help="Simulate posting events to cloud endpoint"
    )
    parser.add_argument(
        "--endpoint",
        default="http://localhost:9000/events",
        help="Cloud endpoint URL for simulation (default: http://localhost:9000/events)"
    )

    args = parser.parse_args()

    try:
        # Find log files
        log_files = find_log_files(args.path)
        if not log_files:
            print(f"[ERROR] No log files found in: {args.path}")
            return 1

        print(f"[INFO] Found {len(log_files)} log file(s)")

        # Initialize simulator
        simulator = EventReplaySimulator(
            cloud_endpoint=args.endpoint if args.simulate_cloud else None,
            output_file=args.output,
            real_time=args.real_time,
            speed_multiplier=args.speed
        )

        # Replay all files
        total_events = 0
        previous_timestamp = None

        for log_file in log_files:
            print(f"\n[INFO] Replaying: {log_file}")

            try:
                replayer = EventReplayer(str(log_file))
                file_events = 0

                for event in replayer.filter_events(
                    room_id=args.room_id,
                    state=args.state,
                    waste_only=args.waste_only
                ):
                    total_events += 1
                    file_events += 1

                    # Check max events limit
                    if args.max_events and total_events > args.max_events:
                        print(f"[INFO] Reached max events limit ({args.max_events})")
                        break

                    # Real-time timing simulation
                    if args.real_time and previous_timestamp:
                        time_delta = event.timestamp - previous_timestamp
                        sleep_time = time_delta.total_seconds() / args.speed
                        if sleep_time > 0:
                            time.sleep(min(sleep_time, 10.0))  # Cap at 10s max

                    previous_timestamp = event.timestamp

                    # Process event
                    if not args.stats_only:
                        simulator.replay_event(event)

                print(f"  └─ Processed {file_events} events")

            except Exception as e:
                print(f"[ERROR] Failed to replay {log_file}: {e}")
                continue

        # Final statistics
        stats = simulator.get_stats()
        print("\n" + "="*60)
        print("REPLAY SUMMARY")
        print("="*60)
        print(f"Total files processed: {len(log_files)}")
        print(f"Total events replayed: {stats['events_processed']}")
        print(f"Energy waste alerts: {stats['alerts_generated']}")

        if args.simulate_cloud:
            print(f"Cloud POST success: {stats['cloud_posts_success']}")
            print(f"Cloud POST failed: {stats['cloud_posts_failed']}")
            print(f"Cloud success rate: {stats['cloud_success_rate']:.1%}")

        if args.output:
            print(f"Results written to: {args.output}")

        print("="*60)
        return 0

    except Exception as e:
        print(f"[ERROR] Replay failed: {e}")
        return 1


if __name__ == "__main__":
    sys.exit(main())