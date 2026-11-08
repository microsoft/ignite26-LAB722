"""Only runtime code supplies the declared OpenAPI authorization parameters."""
import json

FIELDS = ("run_id", "user_id", "customer_id", "conversation_id", "run_grant")
GRANT_HEADER = "X-Reactor-Run-Grant"


def binding_from_metadata(metadata):
    if not isinstance(metadata, dict):
        raise PermissionError("Authenticated request metadata is required.")
    encoded = metadata.get("reactor_binding")
    if not isinstance(encoded, str) or len(encoded) > 512:
        raise PermissionError("A bounded backend-issued binding is required.")
    value = json.loads(encoded)
    if not isinstance(value, dict) or any(not isinstance(value.get(name), str) for name in FIELDS):
        raise PermissionError("The backend-issued binding is invalid.")
    return {name: value[name] for name in FIELDS}


async def invoke_bound(toolbox, operation: str, binding: dict, model_tasks: list):
    if not isinstance(model_tasks, list) or not 1 <= len(model_tasks) <= 2:
        raise ValueError("The model must propose one or two tasks.")
    tasks = []
    for task in model_tasks:
        if not isinstance(task, dict) or not isinstance(task.get("code"), str) or not isinstance(task.get("step"), str):
            raise ValueError("The model task is invalid.")
        # No model-provided identity, grant, URL, method or header survives.
        tasks.append({"step": task["step"], "code": task["code"]})
    return await toolbox.call_tool(operation, **{
        GRANT_HEADER: binding["run_grant"],
        "body": {**{name: binding[name] for name in FIELDS if name != "run_grant"}, "tasks": tasks},
    })


async def invoke_specialist(toolbox, role, binding, *, attempt=1, instruction=""):
    if role not in {"clinical_trials", "drug_specialist", "quality_assurance"}:
        raise ValueError("Unknown specialist capability.")
    if type(attempt) is not int or attempt not in {1, 2} or not isinstance(instruction, str) or len(instruction) > 2000:
        raise ValueError("Invalid bounded specialist delegation.")
    return await toolbox.call_tool("reactor___" + role, **{
        GRANT_HEADER: binding["run_grant"],
        "body": {**{name: binding[name] for name in FIELDS if name != "run_grant"},
                 "attempt": attempt, "instruction": instruction},
    })
