"""
Database index definitions for optimized queries.
These indexes should be created during initial database setup.
"""

from sqlalchemy import Index


# User table indexes
# Index for fast user lookup by email (common in auth)
USER_EMAIL_INDEX = Index('idx_user_email', 'email', unique=True)

# Index for department filtering
USER_DEPARTMENT_INDEX = Index('idx_user_department', 'department')

# Index for status filtering
USER_STATUS_INDEX = Index('idx_user_status', 'is_active')

# Composite index for user role-based queries
USER_ROLE_STATUS_INDEX = Index('idx_user_role_status', 'role', 'is_active')


# Scenario table indexes
# Index for scenario status filtering
SCENARIO_STATUS_INDEX = Index('idx_scenario_status', 'status')

# Index for created_at (sorting by date)
SCENARIO_CREATED_INDEX = Index('idx_scenario_created', 'created_at')

# Index for filtering by template type
SCENARIO_TEMPLATE_INDEX = Index('idx_scenario_template', 'template_type')

# Composite index for active scenarios
SCENARIO_ACTIVE_INDEX = Index('idx_scenario_active', 'status', 'created_at')


# Event table indexes
# Index for event type filtering
EVENT_TYPE_INDEX = Index('idx_event_type', 'event_type')

# Index for user events (user_id lookups)
EVENT_USER_INDEX = Index('idx_event_user', 'user_id')

# Index for scenario events
EVENT_SCENARIO_INDEX = Index('idx_event_scenario', 'scenario_id')

# Index for timestamp-based queries (recent events)
EVENT_TIMESTAMP_INDEX = Index('idx_event_timestamp', 'timestamp')

# Composite index for scenario user events
EVENT_SCENARIO_USER_INDEX = Index('idx_event_scenario_user', 'scenario_id', 'user_id')

# Composite index for type and timestamp
EVENT_TYPE_TIMESTAMP_INDEX = Index('idx_event_type_timestamp', 'event_type', 'timestamp')


# Analytics cache indexes
# Index for rapid analytics lookups
ANALYTICS_METRIC_INDEX = Index('idx_analytics_metric_type', 'metric_type')
ANALYTICS_CREATED_INDEX = Index('idx_analytics_created', 'created_at')


def get_all_indexes():
    """Return all index definitions for initialization"""
    return [
        # User indexes
        USER_EMAIL_INDEX,
        USER_DEPARTMENT_INDEX,
        USER_STATUS_INDEX,
        USER_ROLE_STATUS_INDEX,
        # Scenario indexes
        SCENARIO_STATUS_INDEX,
        SCENARIO_CREATED_INDEX,
        SCENARIO_TEMPLATE_INDEX,
        SCENARIO_ACTIVE_INDEX,
        # Event indexes
        EVENT_TYPE_INDEX,
        EVENT_USER_INDEX,
        EVENT_SCENARIO_INDEX,
        EVENT_TIMESTAMP_INDEX,
        EVENT_SCENARIO_USER_INDEX,
        EVENT_TYPE_TIMESTAMP_INDEX,
        # Analytics indexes
        ANALYTICS_METRIC_INDEX,
        ANALYTICS_CREATED_INDEX,
    ]


def create_indexes(engine):
    """Create all indexes on the database"""
    for index in get_all_indexes():
        try:
            index.create(engine)
            print(f"Created index: {index.name}")
        except Exception as e:
            print(f"Index {index.name} already exists or error occurred: {e}")
