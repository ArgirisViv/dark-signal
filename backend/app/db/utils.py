"""
Database utilities for pagination, filtering, and optimization.
"""

from sqlalchemy.orm import Query
from sqlalchemy import Index
from typing import TypeVar, Generic, List, Optional, Tuple, Any
from pydantic import BaseModel

T = TypeVar('T')


class PaginationParams(BaseModel):
    """Parameters for pagination"""
    skip: int = 0
    limit: int = 50
    
    def validate(self):
        """Validate pagination parameters"""
        if self.skip < 0:
            self.skip = 0
        if self.limit < 1:
            self.limit = 1
        if self.limit > 100:
            self.limit = 100


class PaginatedResponse(BaseModel):
    """Generic paginated response"""
    total: int
    skip: int
    limit: int
    items: List[Any]
    has_more: bool


def paginate_query(
    query: Query,
    skip: int = 0,
    limit: int = 50
) -> Tuple[List[Any], int, bool]:
    """
    Apply pagination to a SQLAlchemy query.
    
    Args:
        query: SQLAlchemy query object
        skip: Number of items to skip
        limit: Maximum items to return
    
    Returns:
        Tuple of (items, total_count, has_more)
    """
    # Validate parameters
    skip = max(0, skip)
    limit = max(1, min(limit, 100))  # Max 100 items per page
    
    # Get total count
    total = query.count()
    
    # Apply pagination
    items = query.offset(skip).limit(limit).all()
    
    # Check if there are more items
    has_more = (skip + limit) < total
    
    return items, total, has_more


def apply_filters(query: Query, filters: dict) -> Query:
    """
    Apply filters to a query based on a dictionary.
    Filters should be in format: {"field_name": value, "field_name__gt": value, etc.}
    """
    for filter_key, filter_value in filters.items():
        if "__" in filter_key:
            field, operator = filter_key.rsplit("__", 1)
            # Handle different operators
            if operator == "gt":  # Greater than
                query = query.filter(getattr(Query, field) > filter_value)
            elif operator == "lt":  # Less than
                query = query.filter(getattr(Query, field) < filter_value)
            elif operator == "gte":  # Greater than or equal
                query = query.filter(getattr(Query, field) >= filter_value)
            elif operator == "lte":  # Less than or equal
                query = query.filter(getattr(Query, field) <= filter_value)
            elif operator == "in":  # In list
                query = query.filter(getattr(Query, field).in_(filter_value))
            elif operator == "contains":  # String contains
                query = query.filter(getattr(Query, field).like(f"%{filter_value}%"))
        else:
            # Direct equality filter
            query = query.filter(getattr(Query, field) == filter_value)
    
    return query


def create_indexes(model_class):
    """
    Define indexes for a model class.
    This should be called in database initialization.
    """
    # Example indexes that should be created for common queries
    # These would be model-specific
    pass


class QueryBuilder:
    """Helper class for building complex database queries"""
    
    def __init__(self, query: Query):
        self.query = query
    
    def filter_by_date_range(self, date_field, start_date, end_date):
        """Filter by date range"""
        self.query = self.query.filter(
            date_field >= start_date,
            date_field <= end_date
        )
        return self
    
    def order_by(self, *args):
        """Add ordering to query"""
        self.query = self.query.order_by(*args)
        return self
    
    def limit(self, limit_value: int):
        """Limit number of results"""
        limit_value = min(limit_value, 100)
        self.query = self.query.limit(limit_value)
        return self
    
    def offset(self, offset_value: int):
        """Offset results"""
        self.query = self.query.offset(max(0, offset_value))
        return self
    
    def build(self):
        """Build and return the query"""
        return self.query
    
    def all(self):
        """Execute query and return all results"""
        return self.query.all()
    
    def first(self):
        """Execute query and return first result"""
        return self.query.first()
    
    def count(self):
        """Count query results"""
        return self.query.count()
