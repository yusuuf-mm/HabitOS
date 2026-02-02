"""Test optimization detail verification."""
import asyncio
import httpx

API_URL = "http://localhost:8000/api/v1"

async def test_optimization_detail():
    async with httpx.AsyncClient() as client:
        # 1. Login
        login_res = await client.post(
            f"{API_URL}/auth/login",
            json={"email": "test@example.com", "password": "password123"}
        )
        token = login_res.json()["access_token"]
        headers = {"Authorization": f"Bearer {token}"}

        # 2. Get History
        history_res = await client.get(f"{API_URL}/optimization/history", headers=headers)
        history_data = history_res.json()
        
        if not history_data["data"]:
            print("No optimization runs found. Please run optimization first.")
            return

        run_id = history_data["data"][0]["id"]
        print(f"Testing with OptimizationRun ID: {run_id}")

        # 3. Get Detail
        detail_res = await client.get(
            f"{API_URL}/optimization/history/{run_id}", headers=headers
        )
        detail_data = detail_res.json()
        print(f"Detail success: {detail_data.get('status') is not None}")
        print(f"Scheduled behavior count: {detail_data.get('scheduled_behavior_count')}")
        print(f"Objective contributions count: {len(detail_data.get('objective_contributions', {}))}")

if __name__ == "__main__":
    asyncio.run(test_optimization_detail())
