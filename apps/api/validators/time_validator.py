"""Time validation utilities"""
import re
from datetime import datetime, time
from fastapi import HTTPException, status


def validate_time_format(time_str: str) -> bool:
    """Validate time string is in HH:MM format"""
    pattern = r'^([0-1]?[0-9]|2[0-3]):[0-5][0-9]$'
    if not re.match(pattern, time_str):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid time format: {time_str}. Use HH:MM format (e.g., 09:30, 14:00)"
        )
    return True


def parse_time_string(time_str: str) -> time:
    """Parse time string to time object"""
    validate_time_format(time_str)
    return datetime.strptime(time_str, "%H:%M").time()


def validate_time_range(start_time_str: str, end_time_str: str) -> bool:
    """Validate that end time is after start time"""
    validate_time_format(start_time_str)
    validate_time_format(end_time_str)
    
    start = parse_time_string(start_time_str)
    end = parse_time_string(end_time_str)
    
    if end <= start:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"End time ({end_time_str}) must be after start time ({start_time_str})"
        )
    return True


def get_duration_hours(start_time_str: str, end_time_str: str) -> float:
    """Get duration in hours between two time strings"""
    start = parse_time_string(start_time_str)
    end = parse_time_string(end_time_str)
    
    start_seconds = start.hour * 3600 + start.minute * 60
    end_seconds = end.hour * 3600 + end.minute * 60
    
    return (end_seconds - start_seconds) / 3600


def validate_datetime_range(start_dt: datetime, end_dt: datetime) -> bool:
    """Validate datetime range"""
    if end_dt <= start_dt:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="End time must be after start time"
        )
    return True


def validate_not_in_past(dt: datetime) -> bool:
    """Validate datetime is not in the past"""
    if dt < datetime.utcnow():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot schedule appointments in the past"
        )
    return True


def get_duration_minutes(start_dt: datetime, end_dt: datetime) -> float:
    """Get duration in minutes between two datetimes"""
    return (end_dt - start_dt).total_seconds() / 60
