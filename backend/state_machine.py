"""
PHASE 0: Room State Machine (FROZEN)

Finite State Machine for room occupancy and energy waste detection.
States and transitions are frozen as part of the PHASE 0 contract.

State Definitions:
- OCCUPIED: One or more people present in the room
- EMPTY_SAFE: No people present, all appliances OFF or minimal energy use
- EMPTY_WASTING: No people present, one or more appliances ON (energy waste condition)

Transition Rules:
1. people_count > 0 → OCCUPIED (regardless of appliances)
2. people_count == 0 AND all appliances OFF/UNKNOWN → EMPTY_SAFE
3. people_count == 0 AND any appliance ON → EMPTY_WASTING

Alert Conditions:
- EMPTY_WASTING state triggers an energy waste alert
- Alert includes duration_sec to indicate how long waste has occurred
"""

from typing import List, Tuple
from schemas import RoomState, ApplianceDetection


class RoomStateMachine:
    """
    Stateless FSM evaluator for room state transitions.

    FROZEN BEHAVIOR: This class implements the canonical state machine.
    Do not modify state logic without version migration.
    """

    # Threshold for "significant" appliance presence (confidence)
    APPLIANCE_CONFIDENCE_THRESHOLD = 0.7

    @staticmethod
    def evaluate_state(
        people_count: int,
        appliances: List[ApplianceDetection]
    ) -> Tuple[RoomState, bool]:
        """
        Evaluate current room state based on occupancy and appliance status.

        Args:
            people_count: Number of people detected in the room
            appliances: List of detected appliances with states

        Returns:
            Tuple of (room_state, energy_waste_detected)

        State Machine Logic (FROZEN):
            If people_count > 0:
                → state = OCCUPIED, no waste
            Else if people_count == 0:
                If any high-confidence appliance is ON:
                    → state = EMPTY_WASTING, waste detected
                Else:
                    → state = EMPTY_SAFE, no waste
        """
        # Rule 1: If people present, room is OCCUPIED (no waste)
        if people_count > 0:
            return ("OCCUPIED", False)

        # Rule 2 & 3: Room is empty, check appliances
        # Filter for high-confidence detections
        confident_appliances = [
            a for a in appliances
            if a.confidence >= RoomStateMachine.APPLIANCE_CONFIDENCE_THRESHOLD
        ]

        # Check if any confident appliance is ON
        any_on = any(a.state == "ON" for a in confident_appliances)

        if any_on:
            # Rule 3: Empty room with appliances ON = WASTING
            return ("EMPTY_WASTING", True)
        else:
            # Rule 2: Empty room with all appliances OFF/UNKNOWN = SAFE
            return ("EMPTY_SAFE", False)

    @staticmethod
    def should_alert(room_state: RoomState, duration_sec: int = 0) -> bool:
        """
        Determine if current state warrants an alert.

        Alert Conditions (FROZEN):
        - EMPTY_WASTING state always triggers alert
        - Optional: Can add duration threshold for persistent waste

        Args:
            room_state: Current room state
            duration_sec: Time spent in current state

        Returns:
            True if alert should be triggered
        """
        if room_state == "EMPTY_WASTING":
            return True
        return False

    @staticmethod
    def estimate_energy_savings(
        room_state: RoomState,
        appliances: List[ApplianceDetection],
        duration_sec: int = 0
    ) -> float:
        """
        Estimate potential energy savings if waste is eliminated.

        Args:
            room_state: Current room state
            appliances: List of detected appliances
            duration_sec: Duration in current state

        Returns:
            Estimated energy savings in kWh

        Calculation (FROZEN):
        - Only calculate for EMPTY_WASTING state
        - Sum power consumption of ON appliances
        - Multiply by duration to get energy (kWh)

        Assumed appliance power consumption:
        - Projector/TV: 150W
        - Laptop: 50W
        - Other: 100W (default)
        """
        if room_state != "EMPTY_WASTING":
            return 0.0

        # Power consumption lookup (Watts)
        POWER_CONSUMPTION = {
            "Projector/TV": 150.0,
            "TV": 150.0,
            "Projector": 150.0,
            "Laptop": 50.0,
            "Desktop": 100.0,
            "Monitor": 30.0,
        }
        DEFAULT_POWER = 100.0

        total_power_watts = 0.0

        for appliance in appliances:
            if appliance.state == "ON":
                # Get power consumption for this appliance type
                power = POWER_CONSUMPTION.get(appliance.name, DEFAULT_POWER)
                total_power_watts += power

        # Convert to kWh: (W * seconds) / (1000 * 3600)
        energy_kwh = (total_power_watts * duration_sec) / (1000.0 * 3600.0)

        return round(energy_kwh, 4)


class StateTracker:
    """
    Stateful tracker for maintaining room state across multiple frames.
    Tracks state duration for more accurate energy calculations.
    """

    def __init__(self):
        self.current_state: RoomState = "EMPTY_SAFE"
        self.state_start_time: float = 0.0
        self.transition_count: int = 0

    def update(
        self,
        people_count: int,
        appliances: List[ApplianceDetection],
        current_time: float
    ) -> Tuple[RoomState, int, bool]:
        """
        Update state tracker with new observations.

        Args:
            people_count: Current people count
            appliances: Current appliance detections
            current_time: Current timestamp (seconds since epoch)

        Returns:
            Tuple of (room_state, duration_sec, state_changed)
        """
        # Evaluate new state
        new_state, _ = RoomStateMachine.evaluate_state(people_count, appliances)

        # Check for state transition
        state_changed = (new_state != self.current_state)

        if state_changed:
            self.current_state = new_state
            self.state_start_time = current_time
            self.transition_count += 1
            duration_sec = 0
        else:
            duration_sec = int(current_time - self.state_start_time)

        return (self.current_state, duration_sec, state_changed)
