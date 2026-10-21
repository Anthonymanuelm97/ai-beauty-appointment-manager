import json
from ai_beauty_appointment_manager.data_access import load_schedule

def get_available_slots():
    schedule = load_schedule()
    available_slots = []

    for slot, booked_by in schedule.items():
        if booked_by is None:
            available_slots.append(slot)
            
    return json.dumps(
    {"available_slots": available_slots},
    ensure_ascii=False
)