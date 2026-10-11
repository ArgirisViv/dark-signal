from enum import Enum
from typing import Optional


class Role(str, Enum):
    admin = "admin"
    trainee = "trainee"
    analyst = "analyst"
    viewer = "viewer"


ROLE_ALIASES = {
    "employee": Role.trainee.value,
    "manager": Role.analyst.value,
}


def normalize_role(value: Optional[str]) -> Optional[str]:
    if not value:
        return None
    lowered = value.lower()
    return ROLE_ALIASES.get(lowered, lowered)
