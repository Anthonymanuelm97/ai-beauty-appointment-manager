import json
import unicodedata

from ai_beauty_appointment_manager.data_access import load_schedule, load_service_prices

SCHEDULE = load_schedule()


def _normalize_service_name(service_name):
    if not isinstance(service_name, str):
        return ""

    normalized = unicodedata.normalize("NFKD", service_name.strip())
    normalized = "".join(
        character for character in normalized if not unicodedata.combining(character)
    )
    normalized = " ".join(normalized.split())
    return normalized.casefold()


def _resolve_service_name(service_name, prices):
    if not isinstance(service_name, str):
        return None

    candidate = _normalize_service_name(service_name)
    if not candidate:
        return None

    matches = []
    for official_name in prices:
        if _normalize_service_name(official_name) == candidate:
            matches.append(official_name)

    if len(matches) == 1:
        return matches[0]

    return None


def error_response(code, message):
    return json.dumps(
        {
            "error": message,
            "error_code": code,
        },
        ensure_ascii=False,
    )


def _validate_booking_proposal(service_name, appointment_slot, customer_name):
    prices = load_service_prices()

    if type(customer_name) is not str or not customer_name.strip():
        return None, {
            "error": "Customer name must be a non-empty string.",
            "error_code": "invalid_customer_name",
        }

    if type(service_name) is not str or not service_name.strip():
        return None, {
            "error": "Service name must be a non-empty string.",
            "error_code": "invalid_service_name",
        }

    service_name = _resolve_service_name(service_name, prices)
    if service_name is None:
        return None, {
            "error": "The selected service does not exist.",
            "error_code": "unknown_service",
        }

    if type(appointment_slot) is not str or not appointment_slot.strip():
        return None, {
            "error": "Appointment slot must be a non-empty string.",
            "error_code": "invalid_appointment_slot",
        }

    if appointment_slot not in SCHEDULE:
        return None, {
            "error": "The selected appointment slot does not exist.",
            "error_code": "unknown_appointment_slot",
        }

    if SCHEDULE[appointment_slot] is not None:
        return None, {
            "error": "The selected appointment slot is already booked.",
            "error_code": "occupied_appointment_slot",
        }

    return {
        "service_name": service_name,
        "appointment_slot": appointment_slot,
        "customer_name": customer_name.strip(),
    }, None


def get_available_slots():
    available_slots = []

    for slot, booked_by in SCHEDULE.items():
        if booked_by is None:
            available_slots.append(slot)

    return json.dumps({"available_slots": available_slots}, ensure_ascii=False)


def calculate_total(items, frequent_customer=False):

    if type(items) is not list or not items:
        return json.dumps(
            {"error": "Items must be a non-empty list."},
            ensure_ascii=False,
        )

    prices = load_service_prices()
    subtotal = 0
    details = []

    for item in items:

        if type(item) is not dict:
            return json.dumps(
                {"error": "Each item must be a dictionary."},
                ensure_ascii=False,
            )

        service = item.get("service")
        quantity = item.get("quantity")

        if type(service) is not str or not service.strip():
            return json.dumps(
                {"error": "Service name must be a non-empty string."},
                ensure_ascii=False,
            )

        service = _resolve_service_name(service, prices)
        if service is None:
            return json.dumps(
                {"error": "The selected service does not exist."},
                ensure_ascii=False,
            )

        if type(quantity) is not int or quantity <= 0:
            return json.dumps(
                {"error": "Quantity must be a positive integer."},
                ensure_ascii=False,
            )

        if service not in prices:
            return json.dumps(
                {"error": "The selected service does not exist."},
                ensure_ascii=False,
            )

        line_total = prices[service] * quantity
        subtotal += line_total
        details.append({"service": service, "quantity": quantity, "total": line_total})

    
    if type(frequent_customer) is not bool:
        return json.dumps(
            {"error": "Frequent customer flag must be a boolean."},
            ensure_ascii=False,
        )
    
    discount = 0

    if frequent_customer:
        discount = round(subtotal * 0.10)

    total = subtotal - discount


    return json.dumps(
        {
            "details": details,
            "subtotal": subtotal,
            "discount": discount,
            "total": total,
        },
        ensure_ascii=False,
    )


def book_appointment(service_name, appointment_slot, customer_name, confirmed=False):
    proposal, error = _validate_booking_proposal(
        service_name,
        appointment_slot,
        customer_name,
    )
    if error is not None:
        return json.dumps(error, ensure_ascii=False)

    if confirmed is not True:
        return json.dumps(
            {"error": "Client must confirm the appointment first."},
            ensure_ascii=False,
        )

    SCHEDULE[proposal["appointment_slot"]] = proposal["customer_name"]

    return json.dumps(
        {
            "status": "pending",
            "service": proposal["service_name"],
            "appointment_slot": proposal["appointment_slot"],
            "customer_name": proposal["customer_name"],
        },
        ensure_ascii=False,
    )


if __name__ == "__main__":

    items = [
        {"service": "Corte clásico", "quantity": 2}
    ]

    print("Normal customer:")
    print(calculate_total(items, False))

    print("Frequent customer:")
    print(calculate_total(items, True))

    print("Invalid frequent customer:")
    print(calculate_total(items, "False"))