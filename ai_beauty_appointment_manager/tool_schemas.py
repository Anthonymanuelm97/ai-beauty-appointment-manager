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
                                "service": {"type": "string"},
                                "quantity": {"type": "integer"},
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
        "description": "Create a pending appointment request after explicit customer confirmation.",
        "parameters": {
            "type": "object",
            "properties": {
                "service_name": {"type": "string"},
                "appointment_slot": {"type": "string"},
                "customer_name": {"type": "string"},
                "confirmed": {"type": "boolean"},
            },
            "required": ["service_name", "appointment_slot", "customer_name", "confirmed"],
        },
    },
}
]

if __name__ == "__main__":
    for tool in TOOLS:
        function = tool["function"]

        print(function["name"])
        print("Required:", function["parameters"]["required"])
        print()