import json
from ai_beauty_appointment_manager.data_access import (
    load_schedule,
    load_service_prices
)

SCHEDULE = load_schedule()

def get_available_slots():
    available_slots = []

    for slot, booked_by in SCHEDULE.items():
        if booked_by is None:
            available_slots.append(slot)
            
    return json.dumps(
    {"available_slots": available_slots},
    ensure_ascii=False
)

def calculate_total(items, frequent_customer=False):
    prices = load_service_prices()
    subtotal = 0
    details = []

    for item in items:
        service = item["service"]
        quantity = item["quantity"]
            
        if service in prices:
            line_total = prices[service] * quantity
            subtotal += line_total
            details.append({"service": service, "quantity": quantity, "total": line_total})

    discount = 0
    if frequent_customer:
        discount = round(subtotal * 0.10)

    total = subtotal - discount

    return json.dumps(
    {
        "details": details,
        "subtotal": subtotal,
        "discount": discount,
        "total": total
    },
    ensure_ascii=False
)

def book_appointment(service_name, appointment_slot, customer_name, confirmed = False):

    SCHEDULE[appointment_slot] = customer_name
    
    return json.dumps(
    {
            "status": "pending",
            "service": service_name,
            "appointment_slot": appointment_slot,
            "customer_name": customer_name
        },
    ensure_ascii=False
)

if __name__ == "__main__":

    print("Available slots BEFORE booking:")
    print(get_available_slots())

    print("Booking appointment:")
    print(book_appointment("Corte clásico", "12:00", "Miguel", True))

    print("Available slots AFTER booking:")
    print(get_available_slots())