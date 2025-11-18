"""
Workflow functions - Orchestrate agent execution
"""
from typing import Dict, Any, Optional, List, Tuple
import json
import os
import logging
from pydantic import BaseModel
from pathlib import Path
import httpx

# Load environment variables
from dotenv import load_dotenv
env_path = Path(__file__).parent.parent / ".env"
if env_path.exists():
    load_dotenv(dotenv_path=env_path)
else:
    load_dotenv(override=False)

from agents import Runner, RunConfig, TResponseInputItem, trace

from app.agents import (
    vision_analyzer,
    data_validator_agent,
    planner,
    sara,
    sara_formatter_agent
)
from app.utils import to_data_url


class WorkflowInput(BaseModel):
    input_as_text: str


async def run_vision(
    prompt: str, 
    image_data_url: str, 
    mission_id: str
) -> Dict[str, Any]:
    """Run the vision analyzer agent with image and prompt data.
    
    The prompt should contain all necessary information including:
    - target_prompt: Description of the object to identify
    - lat, lon, alt_agl_ft: Drone location coordinates
    - priority: Mission priority (optional, defaults to 3)
    
    Args:
        prompt: Description of the object to identify and location/priority info
        image_data_url: Base64 data URL of the image
        mission_id: Mission ID (required)
    
    Returns:
        Dictionary with the vision analysis result
    """
    # Build input text - the prompt should contain all information
    # The agent will extract lat, lon, alt_agl_ft, and priority from the prompt
    input_parts = [
        f"target_prompt: {prompt}",
        f"mission_id: {mission_id}"
    ]
    
    input_text = "\n".join(input_parts)
    
    items: List[Dict[str, Any]] = [
        {
            "role": "user",
            "content": [
                {"type": "input_text", "text": input_text},
                {"type": "input_image", "image_url": image_data_url}
            ]
        }
    ]
    
    result = await Runner.run(
        vision_analyzer,
        input=items,
        run_config=RunConfig(trace_metadata={
            "__trace_source__": "api",
            "workflow_id": "wf_vision_api"
        })
    )
    
    if not result.final_output:
        raise RuntimeError("Agent result is undefined")
    
    # final_output is already a pydantic model from the schema → convert to clean dict
    output_dict = result.final_output.model_dump()
    
    # Ensure mission_id exists (use provided)
    if "mission_id" not in output_dict or not output_dict["mission_id"]:
        output_dict["mission_id"] = mission_id
    
    # Ensure priority exists (default to 3 if not extracted from prompt)
    if "priority" not in output_dict or output_dict["priority"] is None:
        output_dict["priority"] = 3
    
    # Ensure drone_location_at_snapshot is properly formatted as Location object
    # The agent should extract this from the prompt
    if "drone_location_at_snapshot" not in output_dict or not output_dict["drone_location_at_snapshot"]:
        # If agent didn't extract location, raise an error
        raise ValueError("Agent failed to extract drone location (lat, lon, alt_agl_ft) from prompt")
    
    loc_dict = output_dict["drone_location_at_snapshot"]
    if isinstance(loc_dict, dict):
        # Ensure all required fields are present
        if "lat" not in loc_dict or "lon" not in loc_dict or "alt_agl_ft" not in loc_dict:
            raise ValueError("Agent extracted incomplete location data. Required: lat, lon, alt_agl_ft")
        # Convert dict to Location format for response schema
        output_dict["drone_location_at_snapshot"] = {
            "lat": float(loc_dict["lat"]),
            "lon": float(loc_dict["lon"]),
            "alt_agl_ft": float(loc_dict["alt_agl_ft"])
        }
    else:
        raise ValueError("Agent returned invalid location data format")
    
    return output_dict


async def run_workflow(
    workflow_input: WorkflowInput, 
    image_data_url: Optional[str] = None,
    previous_history: Optional[List[Dict[str, Any]]] = None
) -> Dict[str, Any]:
    """Main workflow entrypoint for SARA chat workflow."""
    with trace("SARA"):
        state = {}
        workflow = workflow_input.model_dump()
        
        conversation_history: List[TResponseInputItem] = [
            {
                "role": "user",
                "content": [
                    {
                        "type": "input_text",
                        "text": workflow["input_as_text"]
                    }
                ]
            }
        ]
        
        # Add image if provided
        if image_data_url:
            conversation_history[0]["content"].append({
                "type": "input_image",
                "image_url": image_data_url
            })
        
        sara_result_temp = await Runner.run(
            sara,
            input=[
                *conversation_history
            ],
            run_config=RunConfig(trace_metadata={
                "__trace_source__": "agent-builder",
                "workflow_id": "wf_691793d924ec81908711804df04c5c8707e036ccde1385d1"
            })
        )
        
        conversation_history.extend([item.to_input_item() for item in sara_result_temp.new_items])
        
        sara_result = {
            "output_text": sara_result_temp.final_output.json(),
            "output_parsed": sara_result_temp.final_output.model_dump()
        }
        
        # Capture console message from SARA if available
        console_message = sara_result["output_parsed"].get("messageForConsole")
        
        if sara_result["output_parsed"]["status"] == "MISSION_READY":
            planner_result_temp = await Runner.run(
                planner,
                input=[
                    *conversation_history
                ],
                run_config=RunConfig(trace_metadata={
                    "__trace_source__": "agent-builder",
                    "workflow_id": "wf_691793d924ec81908711804df04c5c8707e036ccde1385d1"
                })
            )
            
            conversation_history.extend([item.to_input_item() for item in planner_result_temp.new_items])
            
            planner_result = {
                "output_text": planner_result_temp.final_output.json(),
                "output_parsed": planner_result_temp.final_output.model_dump()
            }
            
            # Create mission in Phalanx
            try:
                mission_id, error_detail = await create_mission_in_phalanx(planner_result["output_parsed"])
                if mission_id:
                    console_message = f"Mission created successfully. Mission ID: {mission_id}"
                else:
                    # If mission creation failed, include error details in console message
                    logging.warning(f"Mission creation returned None - {error_detail}")
                    if not console_message:
                        console_message = f"Mission plan generated, but failed to create in Phalanx: {error_detail}"
            except Exception as e:
                # Log error but don't fail the workflow
                logging.error(f"Failed to create mission in Phalanx: {str(e)}", exc_info=True)
                # Add error info to console message
                if not console_message:
                    console_message = f"Mission plan generated, but creation failed: {str(e)}"
            
            return {
                "response": planner_result["output_text"],
                "console_message": console_message
            }
        else:
            sara_formatter_agent_result_temp = await Runner.run(
                sara_formatter_agent,
                input=[
                    *conversation_history
                ],
                run_config=RunConfig(trace_metadata={
                    "__trace_source__": "agent-builder",
                    "workflow_id": "wf_691793d924ec81908711804df04c5c8707e036ccde1385d1"
                })
            )
            
            conversation_history.extend([item.to_input_item() for item in sara_formatter_agent_result_temp.new_items])
            
            sara_formatter_agent_result = {
                "output_text": sara_formatter_agent_result_temp.final_output_as(str)
            }
            
            return {
                "response": sara_formatter_agent_result["output_text"],
                "console_message": console_message
            }


async def run_chat_workflow(
    message: str, 
    conversation_history: Optional[List[Dict[str, Any]]] = None, 
    image_data_url: Optional[str] = None
) -> Dict[str, Any]:
    """Run the SARA chat workflow.
    
    Args:
        message: User's message
        conversation_history: Optional list of previous messages in the conversation
        image_data_url: Optional base64 data URL of an image to include with the message
    
    Returns:
        Dictionary with the chat response
    """
    # Build input text from message (don't add image info to text, it will be added separately)
    input_text = message
    
    workflow_input = WorkflowInput(input_as_text=input_text)
    
    # Call run_workflow and get the final result
    workflow_result = await run_workflow(
        workflow_input, 
        image_data_url=image_data_url,
        previous_history=conversation_history
    )
    
    return {
        "response": workflow_result.get("response", ""),
        "console_message": workflow_result.get("console_message"),
        "conversation_id": None
    }


async def run_planner(input_data: Dict[str, Any]) -> Dict[str, Any]:
    """Run the planner workflow with data validator and planner agents.
    
    Args:
        input_data: Dictionary containing the request data (ObjectConfirmedRequest or AppendTaskRequest)
    
    Returns:
        Dictionary with the mission response
    
    Raises:
        RuntimeError: If validation fails or agent result is undefined
        ValueError: If validation returns errors
    """
    # Convert input data to JSON string for the validator
    input_text = json.dumps(input_data, indent=2)
    
    conversation_history: List[Dict[str, Any]] = [
        {
            "role": "user",
            "content": [
                {"type": "input_text", "text": input_text}
            ]
        }
    ]
    
    run_config = RunConfig(trace_metadata={
        "__trace_source__": "api",
        "workflow_id": "wf_planner_api"
    })
    
    # Step 1: Run data validator
    validator_result = await Runner.run(
        data_validator_agent,
        input=conversation_history,
        run_config=run_config
    )
    
    if not validator_result.final_output:
        raise RuntimeError("Data validator result is undefined")
    
    validator_output = validator_result.final_output
    
    # Add validator result to conversation history
    # The new_items from Runner contain the agent's response items
    if hasattr(validator_result, 'new_items') and validator_result.new_items:
        for item in validator_result.new_items:
            # Access raw_item if available, otherwise use the item directly
            raw_item = getattr(item, 'raw_item', item)
            if isinstance(raw_item, dict):
                conversation_history.append(raw_item)
    
    # Step 2: Check validation status
    if validator_output.status == "ERROR":
        error_messages = ". ".join(validator_output.errors) if validator_output.errors else "Validation failed"
        raise ValueError(f"Data validation failed: {error_messages}")
    
    # Step 3: Run planner agent with validated data
    planner_result = await Runner.run(
        planner,
        input=conversation_history,
        run_config=run_config
    )
    
    if not planner_result.final_output:
        raise RuntimeError("Planner agent result is undefined")
    
    # final_output is already a pydantic model from the schema → convert to clean dict
    return planner_result.final_output.model_dump()


async def create_mission_in_phalanx(planner_output: Dict[str, Any]) -> Tuple[Optional[str], str]:
    """Create a mission in Phalanx API from planner output.
    
    Uses the same endpoint and method as Phalanx's publishMission function.
    
    Args:
        planner_output: Dictionary with planner result containing priority, tasks, and additionalData
    
    Returns:
        Tuple of (Mission ID if successful, None otherwise, error detail message)
    """
    # Use the same API URL configuration as Phalanx frontend uses
    # Phalanx frontend uses VITE_API_BASE_URL which can be:
    # - Development: http://localhost:3000 (no /api)
    # - Production: https://your-backend.railway.app/api (with /api)
    # Phalanx API backend (main.ts) uses:
    #   - app.setGlobalPrefix('api') - all routes need /api prefix
    #   - PORT from env (default 3000)
    # So the full URL is: {base_url}/api/notifications/missions/available
    phalanx_api_url = os.getenv("PHALANX_API_URL") or os.getenv("VITE_API_BASE_URL") or os.getenv("API_BASE_URL")
    logging.debug(f"PHALANX_API_URL from env: {os.getenv('PHALANX_API_URL')}")
    logging.debug(f"VITE_API_BASE_URL from env: {os.getenv('VITE_API_BASE_URL')}")
    logging.debug(f"API_BASE_URL from env: {os.getenv('API_BASE_URL')}")
    logging.debug(f"Resolved phalanx_api_url: {phalanx_api_url}")
    
    if not phalanx_api_url:
        # If not configured, log warning and skip mission creation
        error_msg = "PHALANX_API_URL, VITE_API_BASE_URL, or API_BASE_URL not configured - skipping mission creation"
        logging.warning(error_msg)
        return None, error_msg
    
    # Ensure URL doesn't end with /
    phalanx_api_url = phalanx_api_url.rstrip('/')
    
    # Check if URL already includes /api, if not, add it
    # Phalanx backend uses app.setGlobalPrefix('api') in main.ts, so all routes need /api prefix
    # In production, VITE_API_BASE_URL may already include /api (e.g., https://backend.railway.app/api)
    # In development, it's usually just http://localhost:3000
    if not phalanx_api_url.endswith('/api'):
        # Add /api prefix if not present
        phalanx_api_url = f"{phalanx_api_url}/api"
    
    logging.info(f"Final Phalanx API URL: {phalanx_api_url}")
    
    # Convert planner tasks to Phalanx format
    # Phalanx only accepts: LOITER, PATROL, ORBIT
    # Planner can generate: MOVE_TO, LOITER, VISION_WAYPOINT
    phalanx_tasks = []
    for task in planner_output.get("tasks", []):
        task_type = task.get("type", "").upper()
        # Map planner task types to Phalanx task types
        # MOVE_TO and VISION_WAYPOINT -> LOITER (closest match)
        if task_type in ["LOITER", "PATROL", "ORBIT"]:
            phalanx_task_type = task_type
        elif task_type in ["MOVE_TO", "VISION_WAYPOINT"]:
            phalanx_task_type = "LOITER"  # Default to LOITER for movement tasks
        else:
            phalanx_task_type = "LOITER"  # Default fallback
        
        phalanx_tasks.append({
            "type": phalanx_task_type,
            "alt_agl_ft": task.get("alt_agl_ft", 100),
            "duration_s": int(task.get("duration_s", 60))
        })
    
    # If no valid tasks, don't create mission
    if not phalanx_tasks:
        return None, "No valid tasks found in planner output"
    
    # Ensure priority is a valid integer (1-5)
    priority_value = planner_output.get("priority", 3)
    if isinstance(priority_value, float):
        priority_value = int(round(priority_value))
    elif not isinstance(priority_value, int):
        priority_value = int(priority_value) if priority_value else 3
    # Clamp priority to valid range (1-5)
    priority_value = max(1, min(5, priority_value))
    
    mission_data = {
        "priority": priority_value,
        "lease_ttl_s": 3600,  # Default 1 hour lease
        "tasks": phalanx_tasks
    }
    
    try:
        logging.debug(f"Mission data to send: {json.dumps(mission_data, indent=2)}")
        
        async with httpx.AsyncClient(timeout=10.0) as client:
            # phalanx_api_url already includes /api prefix, so just add the route
            url = f"{phalanx_api_url}/notifications/missions/available"
            logging.info(f"Creating mission in Phalanx: POST {url}")
            
            response = await client.post(
                url,
                json=mission_data,
                headers={"Content-Type": "application/json"}
            )
            
            logging.debug(f"Response status: {response.status_code}")
            logging.debug(f"Response body: {response.text}")
            
            response.raise_for_status()
            result = response.json()
            mission_id = result.get("data")
            logging.info(f"Mission created successfully with ID: {mission_id}")
            return mission_id, ""
    except httpx.HTTPStatusError as e:
        error_detail = f"HTTP {e.response.status_code}: {e.response.text}"
        logging.error(f"HTTP error creating mission in Phalanx: {error_detail}")
        return None, error_detail
    except httpx.RequestError as e:
        error_detail = f"Connection error: {str(e)}. Check if Phalanx API is running and accessible."
        logging.error(f"Request error creating mission in Phalanx: {error_detail}")
        return None, error_detail
    except Exception as e:
        error_detail = f"Unexpected error: {str(e)}"
        logging.error(f"Unexpected error creating mission in Phalanx: {error_detail}", exc_info=True)
        return None, error_detail


