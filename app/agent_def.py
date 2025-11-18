"""
Legacy agent_def module - re-exports from new modular structure
This file maintains backward compatibility while the codebase is migrated.
"""
# Re-export all agents from the new modular structure
from app.agents import (
    vision_analyzer,
    data_validator_agent,
    planner,
    sara,
    insight,
    sara_formatter_agent,
    planner_formatter_agent,
    data_formatter,
    insight_formatter_agent
)

# Re-export workflow functions
from app.workflows import (
    run_vision,
    run_workflow,
    run_chat_workflow,
    run_planner,
    WorkflowInput
)

# Re-export utility functions
from app.utils import to_data_url

# Re-export schemas for backward compatibility
from app.agents.vision_analyzer import VisionAnalyzerSchema
from app.agents.data_validator import DataValidatorSchema, DataValidatorSchema__Payload
from app.agents.planner import PlannerSchema, PlannerSchema__TasksItem, PlannerAgentSchema, PlannerAgentSchema__TasksItem
from app.agents.sara import SaraSchema, SaraSchema__Location, SaraSchema__PlannerPayload
from app.agents.insight import InsightSchema, InsightSchema__DroneLocationAtSnapshot
from app.agents.formatters import (
    DataFormatterSchema,
    DataFormatterSchema__Payload,
    DataFormatterSchema__DroneLocationAtSnapshot,
    DataFormatterSchema__DroneLocation,
    DataFormatterSchema__Waypoint
)
