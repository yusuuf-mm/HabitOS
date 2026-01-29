"""Seed database with sample data."""
import asyncio
import logging
import sys
from datetime import date, datetime, timedelta, timezone
from uuid import uuid4

# Add parent directory to path to allow importing app
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy import text
from app.db.database import async_session_maker, init_db
from app.core.security import hash_password
from app.models import (
    User,
    Behavior,
    Objective,
    ObjectiveType,
    OptimizationRun,
    ScheduledBehavior,
    OptimizationStatus,
    SolverType,
    TimeSlot
)

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

async def seed_data():
    """Seed data."""
    logger.info("Initializing database connection...")
    await init_db()
    
    async with async_session_maker() as session:
        logger.info("Cleaning up existing data...")
        # Clear tables in order
        await session.execute(text("TRUNCATE TABLE scheduled_behaviors CASCADE"))
        await session.execute(text("TRUNCATE TABLE optimization_runs CASCADE"))
        await session.execute(text("TRUNCATE TABLE behaviors CASCADE"))
        await session.execute(text("TRUNCATE TABLE objectives CASCADE"))
        await session.execute(text("TRUNCATE TABLE users CASCADE"))
        await session.commit()

        # 1. Create Test User
        logger.info("Creating test user...")
        test_user = User(
            id=uuid4(),
            email="test@example.com",
            username="testuser",
            password_hash=hash_password("password123"),
            first_name="Test",
            last_name="User",
            status="active"
        )
        session.add(test_user)
        # Calculate start of behaviors block...
        # Wait, I need to restore up to where the behavior creation starts.
        
        # ... (restoring user creation logic)
        await session.flush()

        # 2. Create Objectives
        logger.info("Creating objectives...")
        objectives = [
            Objective(id=uuid4(), user_id=test_user.id, type=ObjectiveType.HEALTH, weight=0.3, description="Improve physical health"),
            Objective(id=uuid4(), user_id=test_user.id, type=ObjectiveType.PRODUCTIVITY, weight=0.4, description="Maximize work output"),
            Objective(id=uuid4(), user_id=test_user.id, type=ObjectiveType.LEARNING, weight=0.1, description="Learn new skills"),
            Objective(id=uuid4(), user_id=test_user.id, type=ObjectiveType.WELLNESS, weight=0.1, description="Mental wellbeing"),
            Objective(id=uuid4(), user_id=test_user.id, type=ObjectiveType.SOCIAL, weight=0.1, description="Connect with friends"),
        ]
        session.add_all(objectives)

        # 3. Create Behaviors
        logger.info("Creating behaviors...")
        behaviors = [
            Behavior(
                id=uuid4(),
                user_id=test_user.id,
                name="Morning Jog",
                description="30 min run in the park",
                category="health",
                min_duration=20,
                typical_duration=30,
                max_duration=45,
                energy_cost=6,
                is_active=True,
                preferred_time_slots=[TimeSlot.MORNING],
                impact_on_health=0.9,
                impact_on_productivity=0.4,
                impact_on_wellness=0.7,
            ),
            Behavior(
                id=uuid4(),
                user_id=test_user.id,
                name="Deep Work Session",
                description="Focused coding block",
                category="productivity",
                min_duration=60,
                typical_duration=90,
                max_duration=120,
                energy_cost=8,
                is_active=True,
                preferred_time_slots=[TimeSlot.MORNING, TimeSlot.AFTERNOON],
                impact_on_productivity=1.0,
                impact_on_learning=0.5,
            ),
            Behavior(
                id=uuid4(),
                user_id=test_user.id,
                name="Reading",
                description="Read technical book",
                category="learning",
                min_duration=30,
                typical_duration=45,
                max_duration=60,
                energy_cost=3,
                is_active=True,
                preferred_time_slots=[TimeSlot.EVENING],
                impact_on_learning=0.9,
                impact_on_wellness=0.6,
            ),
            Behavior(
                id=uuid4(),
                user_id=test_user.id,
                name="Meditation",
                description="Mindfulness practice",
                category="wellness",
                min_duration=10,
                typical_duration=15,
                max_duration=30,
                energy_cost=1,
                is_active=True,
                preferred_time_slots=[TimeSlot.MORNING, TimeSlot.NIGHT], # early_morning mapped to MORNING if needed, or check if EARLY_MORNING exists. Model says MORNING, AFTERNOON, EVENING, NIGHT, FLEXIBLE. NO EARLY_MORNING.
                impact_on_wellness=1.0,
                impact_on_health=0.5,
            ),
             Behavior(
                id=uuid4(),
                user_id=test_user.id,
                name="Team Sync",
                description="Sync with colleagues",
                category="social",
                min_duration=15,
                typical_duration=30,
                max_duration=30,
                energy_cost=4,
                is_active=True,
                preferred_time_slots=[TimeSlot.AFTERNOON], # midday -> afternoon
                impact_on_social=0.9,
                impact_on_productivity=0.5,
            ),
        ]
        session.add_all(behaviors)
        await session.flush() # To get IDs

        # 4. Create Mock Optimization Run (History)
        logger.info("Creating mock optimization run...")
        run_id = uuid4()
        today = date.today()
        run = OptimizationRun(
            id=run_id,
            user_id=test_user.id,
            status=OptimizationStatus.COMPLETED,
            solver=SolverType.LINEAR,
            start_date=today,
            end_date=today, # One day run
            time_periods=96, # 15 min slots
            total_objective_value=85.5,
            execution_time_seconds=0.42,
            results={"status": "optimal"},
        )
        session.add(run)

        # 5. Schedule Behaviors for "Today"
        # Mock schedule: Jog at 8:00 (slot 32), Work at 10:00 (slot 40)
        scheduled_items = [
            ScheduledBehavior(
                id=uuid4(),
                optimization_run_id=run_id,
                behavior_id=behaviors[0].id,
                time_period=32, # 08:00 AM (32 * 15m)
                scheduled_duration=30,
                is_scheduled=True
            ),
            ScheduledBehavior(
                id=uuid4(),
                optimization_run_id=run_id,
                behavior_id=behaviors[1].id,
                time_period=40, # 10:00 AM (40 * 15m)
                scheduled_duration=90,
                is_scheduled=True
            ),
             ScheduledBehavior(
                id=uuid4(),
                optimization_run_id=run_id,
                behavior_id=behaviors[4].id,
                time_period=52, # 13:00 PM
                scheduled_duration=30,
                is_scheduled=True
            )
        ]
        session.add_all(scheduled_items)

        await session.commit()
        logger.info("Seeding complete! User: test@example.com / password123")

if __name__ == "__main__":
    asyncio.run(seed_data())
