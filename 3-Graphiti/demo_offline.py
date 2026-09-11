import asyncio
import json
import logging
import os
import sys
from datetime import datetime, timedelta, timezone

# Force UTF-8 output on Windows
if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")

# ============================
# Offline Demo: Personal Fitness Tracker
# Simulates Neo4j operations in-memory
# ============================

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger(__name__)


def iso_timestamp_days_ago(days: int) -> str:
    """Return ISO timestamp N days ago"""
    return (datetime.now(timezone.utc) - timedelta(days=days)).isoformat()


class InMemoryStore:
    """Simulates Neo4j graph database operations in-memory"""

    def __init__(self):
        self.activities = {}  # activity_id -> activity_data
        self.constraints = set()
        self.indices = set()

    async def create_constraint(self, name):
        self.constraints.add(name)

    async def create_index(self, name):
        self.indices.add(name)

    async def merge_activity(self, activity_data):
        self.activities[activity_data["activity_id"]] = {
            **activity_data,
            "created_at": datetime.now(timezone.utc).isoformat(),
        }

    async def query(self, user=None, activity_type=None, min_distance=None, since_time=None):
        results = []
        for act in self.activities.values():
            if user and act["user"] != user:
                continue
            if activity_type and act["activity_type"] != activity_type:
                continue
            if min_distance is not None and act["distance_km"] < min_distance:
                continue
            if since_time and act["timestamp"] < since_time:
                continue
            results.append(act)
        # Sort by timestamp descending
        results.sort(key=lambda x: x["timestamp"], reverse=True)
        return results


class FitnessTracker:
    def __init__(self):
        self.store = None

    async def connect(self):
        """Initialize in-memory store (simulates Neo4j connection)"""
        try:
            self.store = InMemoryStore()

            # Create constraints and indices (simulated)
            await self.store.create_constraint("activity_id_unique")
            await self.store.create_index("user_index")
            await self.store.create_index("activity_type_index")
            await self.store.create_index("timestamp_index")

            logger.info("✅ Connected to In-Memory Store (Neo4j simulation)")
        except Exception as e:
            logger.error(f"❌ Failed to initialize store: {e}")
            raise

    async def close(self):
        """Close connection"""
        if self.store:
            self.store = None
            logger.info("✅ Connection closed")

    async def add_activity(self, activity_data):
        """Add a fitness activity"""
        try:
            await self.store.merge_activity(activity_data)
            logger.info(
                f"✅ Added activity: {activity_data['activity_type']} - {activity_data['distance_km']}km"
            )
        except Exception as e:
            logger.error(f"❌ Failed to add activity: {e}")
            raise

    async def query_recent_activities(self, user: str, days: int):
        """Query activities in the last N days"""
        try:
            since_time = iso_timestamp_days_ago(days)
            return await self.store.query(user=user, since_time=since_time)
        except Exception as e:
            logger.error(f"❌ Query failed: {e}")
            return []

    async def query_running_over_distance(self, user: str, min_distance: float, days: int):
        """Query running activities over certain distance"""
        try:
            since_time = iso_timestamp_days_ago(days)
            return await self.store.query(
                user=user,
                activity_type="running",
                min_distance=min_distance,
                since_time=since_time,
            )
        except Exception as e:
            logger.error(f"❌ Query failed: {e}")
            return []

    async def query_by_activity_type(self, user: str, activity_type: str, days: int):
        """Query activities of specific type"""
        try:
            since_time = iso_timestamp_days_ago(days)
            return await self.store.query(
                user=user, activity_type=activity_type, since_time=since_time
            )
        except Exception as e:
            logger.error(f"❌ Query failed: {e}")
            return []


def create_sample_activities():
    """Create sample fitness activities"""
    return [
        {
            "user": "ahmed_hassan",
            "activity_id": "activity_a1",
            "activity_type": "running",
            "distance_km": 6.0,
            "duration_min": 35,
            "timestamp": iso_timestamp_days_ago(7),
        },
        {
            "user": "fatima_ali",
            "activity_id": "activity_a2",
            "activity_type": "cycling",
            "distance_km": 20.0,
            "duration_min": 60,
            "timestamp": iso_timestamp_days_ago(3),
        },
        {
            "user": "omar_mahmoud",
            "activity_id": "activity_a3",
            "activity_type": "running",
            "distance_km": 4.0,
            "duration_min": 25,
            "timestamp": iso_timestamp_days_ago(2),
        },
        {
            "user": "ahmed_hassan",
            "activity_id": "activity_a4",
            "activity_type": "running",
            "distance_km": 8.0,
            "duration_min": 45,
            "timestamp": iso_timestamp_days_ago(1),
        },
        {
            "user": "fatima_ali",
            "activity_id": "activity_a5",
            "activity_type": "strength_training",
            "distance_km": 0,
            "duration_min": 60,
            "timestamp": iso_timestamp_days_ago(1),
        },
    ]


def print_results(results, title: str):
    """Print query results"""
    print(f"\n--- {title} ---")
    if not results:
        print("No results found.")
        return

    for activity in results:
        print(f"  • User: {activity['user']}")
        print(f"    Activity: {activity['activity_type']}")
        print(f"    Distance: {activity['distance_km']} km")
        print(f"    Duration: {activity['duration_min']} minutes")
        print(f"    Timestamp: {activity['timestamp']}")
        print()


async def main():
    print("=" * 60)
    print("  Neo4j Fitness Tracker — OFFLINE DEMO MODE")
    print("  (Using in-memory store to simulate Neo4j)")
    print("=" * 60)

    tracker = FitnessTracker()

    try:
        # Connect
        print("\n🔄 Connecting to in-memory store...")
        await tracker.connect()

        # Add sample activities
        print("\n1. Adding sample fitness activities...")
        activities = create_sample_activities()
        for activity in activities:
            await tracker.add_activity(activity)

        print("\n2. Running fitness queries...")

        # Query: Ahmed's activities in the last 5 days
        recent_results = await tracker.query_recent_activities("ahmed_hassan", days=5)
        print_results(recent_results, "Ahmed's Activities in the last 5 days")

        # Query: Ahmed's running activities > 5 km in the last 7 days
        running_results = await tracker.query_running_over_distance(
            "ahmed_hassan", min_distance=5, days=7
        )
        print_results(running_results, "Ahmed's Running > 5 km in the last 7 days")

        # Query: Fatima's cycling activities
        cycling_results = await tracker.query_by_activity_type("fatima_ali", "cycling", days=30)
        print_results(cycling_results, "Fatima's Cycling activities in the last 30 days")

        # Query: All users' activities
        all_users = ["ahmed_hassan", "fatima_ali", "omar_mahmoud"]
        for user in all_users:
            user_results = await tracker.query_recent_activities(user, days=30)
            print_results(user_results, f"{user}'s Activities in the last 30 days")

        print("\n✅ All queries completed successfully!")

    except KeyboardInterrupt:
        print("\n👋 Goodbye!")
    except Exception as e:
        print(f"❌ Error: {e}")
    finally:
        await tracker.close()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n👋 Goodbye!")
    except Exception as e:
        print(f"❌ Error: {e}")
