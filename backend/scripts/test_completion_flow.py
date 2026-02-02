"""Test completion flow verification."""
import asyncio
import json
import httpx
from uuid import UUID

API_URL = "http://localhost:8000/api/v1"

async def test_completion():
    async with httpx.AsyncClient() as client:
        # 1. Login
        login_res = await client.post(
            f"{API_URL}/auth/login",
            json={"email": "test@example.com", "password": "password123"}
        )
        token = login_res.json()["access_token"]
        headers = {"Authorization": f"Bearer {token}"}

        # 2. Get Schedule
        schedule_res = await client.get(f"{API_URL}/schedule", headers=headers)
        schedule_data = schedule_res.json()
        print(f"Schedule success: {schedule_data['success']}")
        
        if not schedule_data["data"]["scheduledBehaviors"]:
            print("No scheduled behaviors found. Please run optimization first.")
            return

        sb = schedule_data["data"]["scheduledBehaviors"][0]
        sb_id = sb["id"]
        print(f"Testing with ScheduledBehavior ID: {sb_id}")

        # 3. Mark Complete
        complete_res = await client.post(
            f"{API_URL}/schedule/{sb_id}/complete", headers=headers
        )
        print(f"Mark complete response: {complete_res.json()['message']}")

        # 4. Verify in Schedule
        verify_res = await client.get(f"{API_URL}/schedule", headers=headers)
        sb_verified = next(
            item for item in verify_res.json()["data"]["scheduledBehaviors"]
            if item["id"] == sb_id
        )
        print(f"Is completed (should be True): {sb_verified['isCompleted']}")

        # 5. Mark Incomplete
        incomplete_res = await client.post(
            f"{API_URL}/schedule/{sb_id}/incomplete", headers=headers
        )
        print(f"Mark incomplete response: {incomplete_res.json()['message']}")

        # 6. Verify in Schedule
        verify_res2 = await client.get(f"{API_URL}/schedule", headers=headers)
        sb_verified2 = next(
            item for item in verify_res2.json()["data"]["scheduledBehaviors"]
            if item["id"] == sb_id
        )
        print(f"Is completed (should be False): {sb_verified2['isCompleted']}")

if __name__ == "__main__":
    asyncio.run(test_completion())
