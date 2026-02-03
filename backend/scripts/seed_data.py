"""Seed database with sample data."""
import asyncio
import logging
import sys
import random
from datetime import date, datetime, timedelta, timezone
from uuid import uuid4, UUID

# Add parent directory to path to allow importing app
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy import text
from app.db.database import async_session_maker, init_db
from app.core.security import hash_password
from app.models import (
    User,
    Behavior,
    BehaviorCategory,
    TimeSlot,
    Objective,
    ObjectiveType,
    OptimizationRun,
    OptimizationStatus,
    SolverType,
    ScheduledBehavior,
    CompletionLog,
    Constraint,
    ConstraintType
)

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

async def seed_data():
    """Seed data."""
    logger.info("Initializing database connection...")
    await init_db()
    
    async with async_session_maker() as session:
        logger.info("Cleaning up existing data...")
        tables = [
            "completion_logs",
            "scheduled_behaviors",
            "optimization_runs",
            "constraints",
            "behaviors",
            "objectives",
            "users"
        ]
        for table in tables:
            await session.execute(text(f"DELETE FROM {table}"))
        await session.commit()

        # 1. Create Test User
        logger.info("Creating test user...")
        # Use a fixed UUID for consistency across reseeds
        test_user_id = UUID("0c795feb-936e-46cd-9068-d6c6c139ef2e")
        test_user = User(
            id=test_user_id,
            email="test@example.com",
            username="testuser",
            password_hash=hash_password("password123"),
            first_name="Test",
            last_name="User",
            status="active"
        )
        session.add(test_user)
        await session.flush()

        # 2. Create Objectives
        logger.info("Creating objectives...")
        objective_weights = {
            ObjectiveType.PRODUCTIVITY: 0.20,
            ObjectiveType.HEALTH: 0.20,
            ObjectiveType.WELLNESS: 0.15,
            ObjectiveType.LEARNING: 0.15,
            ObjectiveType.MINDFULNESS: 0.10,
            ObjectiveType.SOCIAL: 0.10,
            ObjectiveType.FINANCIAL: 0.05,
            ObjectiveType.CREATIVITY: 0.05,
        }
        
        objectives = []
        for obj_type, weight in objective_weights.items():
            objectives.append(Objective(
                id=uuid4(),
                user_id=test_user.id,
                type=obj_type,
                weight=weight,
                description=f"Improve {obj_type.value}"
            ))
        session.add_all(objectives)

        # 3. Create Behaviors
        logger.info("Creating behaviors...")
        behavior_configs = [
            ("Morning Jog", "30 min run in the park", BehaviorCategory.HEALTH, 20, 30, 45, 6.0, [TimeSlot.EARLY_MORNING, TimeSlot.MORNING], {"health": 0.9, "wellness": 0.4}),
            ("Gym Session", "Strength training at gym", BehaviorCategory.HEALTH, 45, 60, 90, 8.0, [TimeSlot.MORNING, TimeSlot.AFTERNOON, TimeSlot.EVENING], {"health": 1.0, "productivity": 0.3}),
            ("Quick Yoga", "Stretching and flexibility", BehaviorCategory.HEALTH, 10, 15, 20, 2.0, [TimeSlot.EARLY_MORNING, TimeSlot.NIGHT, TimeSlot.FLEXIBLE], {"health": 0.6, "wellness": 0.7, "mindfulness": 0.8}),
            ("Deep Work", "High-focus cognitive work", BehaviorCategory.PRODUCTIVITY, 60, 90, 120, 8.0, [TimeSlot.MORNING, TimeSlot.AFTERNOON], {"productivity": 1.0, "learning": 0.4}),
            ("Email/Admin", "Clear inbox and paperwork", BehaviorCategory.PRODUCTIVITY, 15, 30, 45, 4.0, [TimeSlot.AFTERNOON, TimeSlot.EVENING], {"productivity": 0.6}),
            ("Planning", "Weekly and daily planning", BehaviorCategory.PRODUCTIVITY, 15, 20, 30, 3.0, [TimeSlot.EVENING, TimeSlot.NIGHT], {"productivity": 0.8, "financial": 0.4}),
            ("Read Technical Book", "Learn new technologies", BehaviorCategory.LEARNING, 20, 45, 60, 4.0, [TimeSlot.EVENING, TimeSlot.NIGHT, TimeSlot.FLEXIBLE], {"learning": 1.0, "productivity": 0.3}),
            ("Coding Course", "Online tutorial", BehaviorCategory.LEARNING, 45, 60, 120, 7.0, [TimeSlot.AFTERNOON, TimeSlot.EVENING], {"learning": 0.9, "creativity": 0.5}),
            ("Meditation", "Focused breathing", BehaviorCategory.MINDFULNESS, 5, 15, 20, 1.0, [TimeSlot.EARLY_MORNING, TimeSlot.NIGHT, TimeSlot.FLEXIBLE], {"mindfulness": 1.0, "wellness": 0.9, "productivity": 0.4}),
            ("Journaling", "Reflect on the day", BehaviorCategory.WELLNESS, 5, 10, 15, 2.0, [TimeSlot.EVENING, TimeSlot.NIGHT], {"wellness": 0.8, "mindfulness": 0.6, "creativity": 0.4}),
            ("Healthy Cooking", "Prepare nutritious meal", BehaviorCategory.HEALTH, 30, 45, 60, 3.0, [TimeSlot.EVENING, TimeSlot.MIDDAY], {"health": 0.8, "wellness": 0.5, "financial": 0.4}),
            ("Call Family", "Stay connected", BehaviorCategory.SOCIAL, 15, 30, 45, 3.0, [TimeSlot.EVENING, TimeSlot.FLEXIBLE], {"social": 1.0, "wellness": 0.6}),
            ("Team Sync", "Coordination with colleagues", BehaviorCategory.SOCIAL, 15, 30, 30, 4.0, [TimeSlot.MORNING, TimeSlot.AFTERNOON], {"social": 0.7, "productivity": 0.5}),
            ("Review Budget", "Check expenses", BehaviorCategory.FINANCIAL, 10, 15, 30, 2.0, [TimeSlot.FLEXIBLE], {"financial": 1.0, "wellness": 0.3}),
            ("Music Practice", "Play instrument", BehaviorCategory.CREATIVITY, 15, 30, 60, 4.0, [TimeSlot.EVENING, TimeSlot.FLEXIBLE], {"creativity": 1.0, "wellness": 0.7}),
            ("Sketching", "Creative drawing", BehaviorCategory.CREATIVITY, 15, 20, 45, 2.0, [TimeSlot.EVENING, TimeSlot.FLEXIBLE], {"creativity": 0.9, "mindfulness": 0.5}),
        ]

        behaviors = []
        for name, desc, cat, min_d, typ_d, max_d, energy, slots, impacts in behavior_configs:
            behaviors.append(Behavior(
                id=uuid4(),
                user_id=test_user.id,
                name=name,
                description=desc,
                category=cat,
                min_duration=min_d,
                typical_duration=typ_d,
                max_duration=max_d,
                energy_cost=energy,
                is_active=True,
                preferred_time_slots=slots,
                impact_on_health=impacts.get("health", 0.0),
                impact_on_productivity=impacts.get("productivity", 0.0),
                impact_on_learning=impacts.get("learning", 0.0),
                impact_on_wellness=impacts.get("wellness", 0.0),
                impact_on_social=impacts.get("social", 0.0),
                impact_on_financial=impacts.get("financial", 0.0),
                impact_on_creativity=impacts.get("creativity", 0.0),
                impact_on_mindfulness=impacts.get("mindfulness", 0.0),
            ))
        session.add_all(behaviors)
        await session.flush()

        # 4. Create Historical Data (7 days)
        logger.info("Creating historical data (7 days)...")
        now = datetime.now(timezone.utc)
        for i in range(7, 0, -1):
            target_date = (now - timedelta(days=i)).date()
            run_id = uuid4()
            run = OptimizationRun(
                id=run_id,
                user_id=test_user.id,
                status=OptimizationStatus.COMPLETED,
                solver=SolverType.LINEAR,
                start_date=target_date,
                end_date=target_date,
                time_periods=96,
                total_objective_value=random.uniform(70, 95),
                execution_time_seconds=random.uniform(0.1, 0.5),
                results={"status": "optimal"}
            )
            session.add(run)
            
            # Schedule 4 behaviors per day
            daily_behaviors = random.sample(behaviors, k=4)
            for b_idx, b in enumerate(daily_behaviors):
                session.add(ScheduledBehavior(
                    id=uuid4(),
                    optimization_run_id=run_id,
                    behavior_id=b.id,
                    time_period=24 + (b_idx * 16),
                    scheduled_duration=b.typical_duration,
                    is_scheduled=True
                ))
                # Add log for all historical items
                session.add(CompletionLog(
                    id=uuid4(),
                    user_id=test_user.id,
                    behavior_id=b.id,
                    optimization_run_id=run_id,
                    actual_duration=b.typical_duration + random.randint(-5, 10),
                    completed_at=datetime.combine(target_date, datetime.min.time(), tzinfo=timezone.utc) + timedelta(hours=6 + (b_idx * 4)),
                    satisfaction_score=random.randint(3, 5)
                ))

        # 5. Create Today's Schedule
        logger.info("Creating today's schedule...")
        today = date.today()
        today_run_id = uuid4()
        run = OptimizationRun(
            id=today_run_id,
            user_id=test_user.id,
            status=OptimizationStatus.COMPLETED,
            solver=SolverType.LINEAR,
            start_date=today,
            end_date=today,
            time_periods=96,
            total_objective_value=115.0,
            execution_time_seconds=0.4,
            results={"status": "optimal"}
        )
        session.add(run)
        
        # Schedule specifically: Jog (8:00), Deep Work (10:00), Cooking (13:00), Email (15:00), Reading (20:00)
        today_schedule = [
            (behaviors[0], 32), # Jog 8:00
            (behaviors[3], 40), # Deep Work 10:00
            (behaviors[10], 52), # Cooking 13:00
            (behaviors[4], 60), # Email 15:00
            (behaviors[6], 80), # Reading 20:00
        ]
        for b, slot in today_schedule:
            session.add(ScheduledBehavior(
                id=uuid4(),
                optimization_run_id=today_run_id,
                behavior_id=b.id,
                time_period=slot,
                scheduled_duration=b.typical_duration,
                is_scheduled=True
            ))

        # 6. Create sample constraints
        logger.info("Creating constraints...")
        constraints = [
            Constraint(
                id=uuid4(),
                user_id=test_user.id,
                type=ConstraintType.TIME_BUDGET,
                parameters={"max_hours_per_day": 8, "category": "productivity"},
                is_active=True
            ),
            Constraint(
                id=uuid4(),
                user_id=test_user.id,
                type=ConstraintType.FREQUENCY,
                parameters={"min_times_per_week": 3, "behavior_name": "Morning Jog"},
                is_active=True
            )
        ]
        session.add_all(constraints)

        await session.commit()
        logger.info("Seeding complete! User: test@example.com / password123")

if __name__ == "__main__":
    asyncio.run(seed_data())
