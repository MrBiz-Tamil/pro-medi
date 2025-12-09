#!/usr/bin/env python
"""Test the AI chat responses"""

from services.ai_chat_data import generate_ai_response

test_inputs = [
    "hello",
    "hi there",
    "I have a headache",
    "I have fever for 3 days",
    "my stomach hurts",
    "I am feeling anxious",
    "I want to book an appointment",
    "where is the pharmacy?",
    "heart attack symptoms",
    "I can't breathe",
    "thank you",
    "bye",
    "I have diabetes, what should I eat?",
    "my child has fever",
    "I have back pain for weeks",
    "how do I exercise safely?"
]

print("=" * 60)
print("AI HEALTH ASSISTANT - RESPONSE TEST")
print("=" * 60)

for test in test_inputs:
    result = generate_ai_response(test)
    print(f"\n📝 Input: {test}")
    print(f"🤖 Response: {result['response'][:200]}...")
    if result.get('urgency_detected'):
        print(f"⚠️  Urgency: {result['urgency_detected']}")
    if result.get('suggestions'):
        print(f"💡 Suggestions: {result['suggestions']}")
    print("-" * 60)

print("\n✅ All tests completed!")
