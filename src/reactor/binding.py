"""Only runtime code supplies the declared OpenAPI authorization parameters."""
import json

FIELDS = ("run_id", "user_id", "customer_id", "conversation_id", "run_grant")


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
    return await toolbox.call_tool(operation, **{name: binding[name] for name in FIELDS}, tasks=tasks)
