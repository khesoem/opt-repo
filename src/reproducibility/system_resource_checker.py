import time
import re
from typing import Dict


class SystemResourcePressureError(Exception):
    """Exception raised when system resource pressure is detected."""
    pass


def parse_pressure_line(line: str) -> Dict[str, float]:
    """
    Parse a pressure line and extract avg10, avg60, avg300 values.
    
    Example line:
    some avg10=0.00 avg60=0.00 avg300=0.00 total=48940356567
    
    Returns:
        Dict with keys 'avg10', 'avg60', 'avg300' and their float values
    """
    values = {}
    # Extract avg10, avg60, avg300 values
    for metric in ['avg10', 'avg60', 'avg300']:
        pattern = rf'{metric}=([\d.]+)'
        match = re.search(pattern, line)
        if match:
            values[metric] = float(match.group(1))
    return values


def check_pressure_file(filepath: str) -> None:
    """
    Check a pressure file for stalled processes.
    
    Args:
        filepath: Path to the pressure file (e.g., /proc/pressure/cpu)
    
    Raises:
        SystemResourcePressureError: If any processes are stalled (avg > 0)
    """
    try:
        with open(filepath, 'r') as f:
            lines = f.readlines()
        
        if not lines:
            return
        
        # Get the first line that starts with "some"
        some_line = None
        for line in lines:
            if line.strip().startswith('some'):
                some_line = line.strip()
                break
        
        if not some_line:
            return
        
        # Parse the values
        values = parse_pressure_line(some_line)
        
        # Check if any processes are stalled (any avg > 0)
        for metric, value in values.items():
            print(metric, value)
            if value > 0:
                raise SystemResourcePressureError(
                    f"Resource pressure detected in {filepath}: "
                    f"{metric}={value} (avg10={values.get('avg10', 0)}, "
                    f"avg60={values.get('avg60', 0)}, "
                    f"avg300={values.get('avg300', 0)})"
                )
    
    except FileNotFoundError:
        # Pressure files might not exist on all systems
        pass
    except SystemResourcePressureError:
        # Re-raise our custom exception
        raise


def check_system_resource_usage():
    """
    Monitor system resource pressure every 5 seconds.
    
    Checks /proc/pressure/cpu and /proc/pressure/memory for stalled processes.
    Raises SystemResourcePressureError if pressure is detected.
    
    This function runs indefinitely until an exception is raised or interrupted.
    """
    pressure_files = [
        '/proc/pressure/cpu',
        '/proc/pressure/memory'
    ]
    
    while True:
        for filepath in pressure_files:
            check_pressure_file(filepath)
        
        # Wait 5 seconds before next check
        time.sleep(5)