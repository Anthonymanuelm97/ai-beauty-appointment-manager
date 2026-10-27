from ai_beauty_appointment_manager.data_access import load_service_prices

SERVICE_NAMES = list(load_service_prices().keys())

TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "get_available_slots",
            "description": "Get available appointment slots without modifying the schedule.",
            "parameters": {
                "type": "object",
                "properties": {},
                "required": [],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "calculate_total",
            "description": "Calculate service prices and optional frequent customer discount.",
            "parameters": {
                "type": "object",
                "properties": {
                    "items": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "properties": {
                                "service": {
                                    "type": "string",
                                    "description": "Official service name from the business catalog.",
                                    "enum": SERVICE_NAMES,
                                },
                                "quantity": {
                                    "type": "integer",
                                    "minimum": 1,
                                },
                            },
                            "required": ["service", "quantity"],
                        },
                    },
                    "frequent_customer": {"type": "boolean"},
                },
                "required": ["items"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "book_appointment",
            "description": "Validate a proposed appointment without changing the schedule. Python registers it only after explicit customer confirmation.",
            "parameters": {
                "type": "object",
                "properties": {
                    "service_name": {
                        "type": "string",
                        "description": "Official service name from the business catalog.",
                        "enum": SERVICE_NAMES,
                    },
                    "appointment_slot": {"type": "string"},
                    "customer_name": {"type": "string"},
                    "confirmed": {"type": "boolean"},
                },
                "required": ["service_name", "appointment_slot", "customer_name", "confirmed"],
            },
        },
    },
]

if __name__ == "__main__":
    for tool in TOOLS:
        function = tool["function"]
        print(function["name"])
        print("Required:", function["parameters"]["required"])
        print()