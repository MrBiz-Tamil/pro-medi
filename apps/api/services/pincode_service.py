"""
Pincode Verification Service
Uses India Post Pincode API: https://api.postalpincode.in/pincode/{PINCODE}
"""
from __future__ import annotations

import httpx
from typing import Optional, List, Dict, Any, Tuple
from datetime import datetime, timedelta
from pydantic import BaseModel
import logging

logger = logging.getLogger(__name__)

# Constants
INDIA_POST_API_BASE = "https://api.postalpincode.in/pincode"
CACHE_EXPIRY_HOURS = 24  # Cache pincode data for 24 hours


class PostOffice(BaseModel):
    """Post Office details from India Post API"""
    name: str
    branch_type: str
    delivery_status: str
    circle: str
    district: str
    division: str
    region: str
    block: Optional[str] = None
    state: str
    country: str = "India"
    pincode: str


class PincodeVerificationResult(BaseModel):
    """Result of pincode verification"""
    pincode: str
    is_valid: bool
    message: str
    post_offices: List[PostOffice] = []
    city: Optional[str] = None
    district: Optional[str] = None
    state: Optional[str] = None
    is_delivery_available: bool = False


# In-memory cache for pincode lookups (can be replaced with Redis in production)
_pincode_cache: Dict[str, Tuple[PincodeVerificationResult, datetime]] = {}


async def verify_pincode(pincode: str) -> PincodeVerificationResult:
    """
    Verify a pincode using India Post API
    Returns location details including city, district, state, and post offices
    """
    # Validate pincode format (6 digits)
    if not pincode or not pincode.isdigit() or len(pincode) != 6:
        return PincodeVerificationResult(
            pincode=pincode,
            is_valid=False,
            message="Invalid pincode format. Pincode must be 6 digits.",
            is_delivery_available=False
        )
    
    # Check cache first
    cached_result = _get_from_cache(pincode)
    if cached_result:
        logger.info(f"Pincode {pincode} found in cache")
        return cached_result
    
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.get(f"{INDIA_POST_API_BASE}/{pincode}")
            response.raise_for_status()
            data = response.json()
            
            if not data or len(data) == 0:
                return PincodeVerificationResult(
                    pincode=pincode,
                    is_valid=False,
                    message="No data received from postal service",
                    is_delivery_available=False
                )
            
            result_data = data[0]
            status = result_data.get("Status", "")
            message = result_data.get("Message", "")
            
            if status == "Success" and result_data.get("PostOffice"):
                post_offices_data = result_data["PostOffice"]
                post_offices = []
                
                for po in post_offices_data:
                    post_office = PostOffice(
                        name=po.get("Name", ""),
                        branch_type=po.get("BranchType", ""),
                        delivery_status=po.get("DeliveryStatus", "Non-Delivery"),
                        circle=po.get("Circle", ""),
                        district=po.get("District", ""),
                        division=po.get("Division", ""),
                        region=po.get("Region", ""),
                        block=po.get("Block") if po.get("Block") != "NA" else None,
                        state=po.get("State", ""),
                        country=po.get("Country", "India"),
                        pincode=po.get("Pincode", pincode)
                    )
                    post_offices.append(post_office)
                
                # Use first post office for city/state info
                first_po = post_offices[0] if post_offices else None
                
                # Check if any post office has delivery service
                is_delivery = any(
                    po.delivery_status.lower() == "delivery" 
                    for po in post_offices
                )
                
                result = PincodeVerificationResult(
                    pincode=pincode,
                    is_valid=True,
                    message=message,
                    post_offices=post_offices,
                    city=first_po.region if first_po else None,
                    district=first_po.district if first_po else None,
                    state=first_po.state if first_po else None,
                    is_delivery_available=is_delivery
                )
                
                # Cache the result
                _add_to_cache(pincode, result)
                
                return result
            else:
                # Pincode not found
                return PincodeVerificationResult(
                    pincode=pincode,
                    is_valid=False,
                    message=message or "Pincode not found",
                    is_delivery_available=False
                )
                
    except httpx.TimeoutException:
        logger.error(f"Timeout while verifying pincode {pincode}")
        return PincodeVerificationResult(
            pincode=pincode,
            is_valid=False,
            message="Service timeout. Please try again.",
            is_delivery_available=False
        )
    except httpx.HTTPStatusError as e:
        logger.error(f"HTTP error while verifying pincode {pincode}: {e}")
        return PincodeVerificationResult(
            pincode=pincode,
            is_valid=False,
            message="Unable to verify pincode. Service unavailable.",
            is_delivery_available=False
        )
    except Exception as e:
        logger.error(f"Error verifying pincode {pincode}: {e}")
        return PincodeVerificationResult(
            pincode=pincode,
            is_valid=False,
            message="An error occurred while verifying pincode",
            is_delivery_available=False
        )


async def get_post_offices(pincode: str) -> List[PostOffice]:
    """
    Get list of post offices for a given pincode
    """
    result = await verify_pincode(pincode)
    return result.post_offices if result.is_valid else []


async def check_delivery_availability(pincode: str) -> Dict[str, Any]:
    """
    Check if delivery is available for a given pincode
    """
    result = await verify_pincode(pincode)
    
    delivery_post_offices = [
        po for po in result.post_offices 
        if po.delivery_status.lower() == "delivery"
    ]
    
    return {
        "pincode": pincode,
        "is_valid": result.is_valid,
        "is_delivery_available": result.is_delivery_available,
        "delivery_post_offices": [po.name for po in delivery_post_offices],
        "total_post_offices": len(result.post_offices),
        "message": result.message
    }


def _get_from_cache(pincode: str) -> Optional[PincodeVerificationResult]:
    """Get cached pincode result if not expired"""
    if pincode in _pincode_cache:
        result, cached_at = _pincode_cache[pincode]
        if datetime.utcnow() - cached_at < timedelta(hours=CACHE_EXPIRY_HOURS):
            return result
        else:
            # Expired, remove from cache
            del _pincode_cache[pincode]
    return None


def _add_to_cache(pincode: str, result: PincodeVerificationResult):
    """Add pincode result to cache"""
    _pincode_cache[pincode] = (result, datetime.utcnow())


def clear_cache():
    """Clear the pincode cache"""
    _pincode_cache.clear()


def get_cache_stats() -> Dict[str, Any]:
    """Get cache statistics"""
    now = datetime.utcnow()
    valid_entries = sum(
        1 for _, (_, cached_at) in _pincode_cache.items()
        if now - cached_at < timedelta(hours=CACHE_EXPIRY_HOURS)
    )
    return {
        "total_entries": len(_pincode_cache),
        "valid_entries": valid_entries,
        "cache_expiry_hours": CACHE_EXPIRY_HOURS
    }
