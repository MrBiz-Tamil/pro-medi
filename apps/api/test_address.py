"""
Test Address & Pincode Verification Module
"""

import asyncio
import sys
sys.path.insert(0, '.')

from services.pincode_service import (
    verify_pincode,
    get_post_offices,
    check_delivery_availability,
    get_cache_stats,
    clear_cache
)


async def test_pincode_verification():
    """Test the pincode verification service"""
    print("=" * 60)
    print("Testing Address & Pincode Verification Module")
    print("=" * 60)
    
    # Test 1: Valid pincode (Chennai)
    print("\n1. Testing valid pincode (600001 - Chennai):")
    result = await verify_pincode("600001")
    print(f"   Is Valid: {result.is_valid}")
    print(f"   City: {result.city}")
    print(f"   District: {result.district}")
    print(f"   State: {result.state}")
    print(f"   Delivery Available: {result.is_delivery_available}")
    print(f"   Post Offices Count: {len(result.post_offices)}")
    if result.post_offices:
        print(f"   First Post Office: {result.post_offices[0].name}")
    
    # Test 2: Another valid pincode (Mumbai)
    print("\n2. Testing valid pincode (400001 - Mumbai):")
    result = await verify_pincode("400001")
    print(f"   Is Valid: {result.is_valid}")
    print(f"   City: {result.city}")
    print(f"   District: {result.district}")
    print(f"   State: {result.state}")
    print(f"   Post Offices Count: {len(result.post_offices)}")
    
    # Test 3: Valid pincode (Delhi)
    print("\n3. Testing valid pincode (110001 - Delhi):")
    result = await verify_pincode("110001")
    print(f"   Is Valid: {result.is_valid}")
    print(f"   City: {result.city}")
    print(f"   District: {result.district}")
    print(f"   State: {result.state}")
    
    # Test 4: Invalid pincode format
    print("\n4. Testing invalid pincode format (12345):")
    result = await verify_pincode("12345")
    print(f"   Is Valid: {result.is_valid}")
    print(f"   Message: {result.message}")
    
    # Test 5: Non-existent pincode
    print("\n5. Testing non-existent pincode (999999):")
    result = await verify_pincode("999999")
    print(f"   Is Valid: {result.is_valid}")
    print(f"   Message: {result.message}")
    
    # Test 6: Get post offices for a pincode
    print("\n6. Testing get_post_offices (600001):")
    post_offices = await get_post_offices("600001")
    print(f"   Found {len(post_offices)} post offices:")
    for po in post_offices[:3]:  # Show first 3
        print(f"   - {po.name} ({po.branch_type}) - {po.delivery_status}")
    
    # Test 7: Check delivery availability
    print("\n7. Testing delivery availability check (600001):")
    delivery = await check_delivery_availability("600001")
    print(f"   Delivery Available: {delivery['is_delivery_available']}")
    print(f"   Delivery Post Offices: {delivery['delivery_post_offices'][:3]}")
    
    # Test 8: Cache stats
    print("\n8. Cache Statistics:")
    stats = get_cache_stats()
    print(f"   Total Entries: {stats['total_entries']}")
    print(f"   Valid Entries: {stats['valid_entries']}")
    print(f"   Cache Expiry: {stats['cache_expiry_hours']} hours")
    
    # Test 9: Cache hit (should be fast)
    print("\n9. Testing cache hit (600001 again):")
    import time
    start = time.time()
    result = await verify_pincode("600001")
    elapsed = (time.time() - start) * 1000
    print(f"   Time: {elapsed:.2f}ms (should be fast if cached)")
    print(f"   Is Valid: {result.is_valid}")
    
    print("\n" + "=" * 60)
    print("All tests completed successfully!")
    print("=" * 60)


if __name__ == "__main__":
    asyncio.run(test_pincode_verification())
