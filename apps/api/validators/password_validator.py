"""
Password validation utilities
Enforces strong password requirements
"""

import re
from typing import Tuple

class PasswordValidator:
    """Validates password strength and requirements"""
    
    MIN_LENGTH = 8
    MAX_LENGTH = 128
    
    @staticmethod
    def validate(password: str) -> Tuple[bool, str]:
        """
        Validate password against security requirements
        
        Returns:
            (is_valid, error_message)
        """
        if not password:
            return False, "Password is required"
        
        if len(password) < PasswordValidator.MIN_LENGTH:
            return False, f"Password must be at least {PasswordValidator.MIN_LENGTH} characters long"
        
        if len(password) > PasswordValidator.MAX_LENGTH:
            return False, f"Password must not exceed {PasswordValidator.MAX_LENGTH} characters"
        
        # Check for uppercase letter
        if not re.search(r'[A-Z]', password):
            return False, "Password must contain at least one uppercase letter"
        
        # Check for lowercase letter
        if not re.search(r'[a-z]', password):
            return False, "Password must contain at least one lowercase letter"
        
        # Check for digit
        if not re.search(r'\d', password):
            return False, "Password must contain at least one number"
        
        # Check for special character
        if not re.search(r'[!@#$%^&*(),.?":{}|<>]', password):
            return False, "Password must contain at least one special character (!@#$%^&*(),.?\":{}|<>)"
        
        return True, ""
    
    @staticmethod
    def get_strength(password: str) -> str:
        """
        Calculate password strength
        
        Returns:
            "weak", "medium", "strong", or "very_strong"
        """
        if not password:
            return "weak"
        
        score = 0
        
        # Length score
        if len(password) >= 8:
            score += 1
        if len(password) >= 12:
            score += 1
        if len(password) >= 16:
            score += 1
        
        # Character variety score
        if re.search(r'[a-z]', password):
            score += 1
        if re.search(r'[A-Z]', password):
            score += 1
        if re.search(r'\d', password):
            score += 1
        if re.search(r'[!@#$%^&*(),.?":{}|<>]', password):
            score += 1
        
        # Multiple of each type
        if len(re.findall(r'[A-Z]', password)) >= 2:
            score += 1
        if len(re.findall(r'\d', password)) >= 2:
            score += 1
        
        if score <= 3:
            return "weak"
        elif score <= 5:
            return "medium"
        elif score <= 7:
            return "strong"
        else:
            return "very_strong"

def validate_password(password: str) -> None:
    """
    Validate password and raise exception if invalid
    
    Raises:
        ValueError: If password doesn't meet requirements
    """
    is_valid, error_message = PasswordValidator.validate(password)
    if not is_valid:
        raise ValueError(error_message)
