from ai_beauty_appointment_manager.tools import (
    get_available_slots,
    calculate_total,
    book_appointment,
)
import json
import inspect

FUNCTIONS = {
    "get_available_slots": get_available_slots,
    "calculate_total": calculate_total,
    "book_appointment": book_appointment,
}


def dispatch_tool(tool_name, arguments_json="{}"):

    selected_function = FUNCTIONS.get(tool_name)

    if selected_function is None:
        return json.dumps(
            {"error": "Unknown tool."},
            ensure_ascii=False,
        )

    try:
        arguments = json.loads(arguments_json)

    except json.JSONDecodeError:
        return json.dumps(
            {"error": "Invalid JSON arguments."},
            ensure_ascii=False,
        )

    if type(arguments) is not dict:
        return json.dumps(
            {"error": "Tool arguments must be a JSON object."},
            ensure_ascii=False,
        )

    try:
        inspect.signature(selected_function).bind(**arguments)

    except TypeError:
        return json.dumps(
            {"error": "Invalid arguments for this tool."},
            ensure_ascii=False,
        )

    try:
        return selected_function(**arguments)

    except Exception:
        return json.dumps(
            {"error": "Tool execution failed."},
            ensure_ascii=False,
        )


