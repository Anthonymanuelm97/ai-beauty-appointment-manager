from __future__ import annotations

import json
import os
import re
from typing import Any, Dict, List, Optional

from dotenv import load_dotenv
from groq import Groq

from ai_beauty_appointment_manager.system_prompts import SYSTEM_PROMPT
from ai_beauty_appointment_manager.tool_dispatcher import dispatch_tool
from ai_beauty_appointment_manager.tool_schemas import TOOLS


class Agent:
    def __init__(
        self,
        model: str = "openai/gpt-oss-120b",
        system_prompt: Optional[str] = None,
        diagnostic: bool = False,
        api_key: Optional[str] = None,
    ):
        load_dotenv()

        self.model = model
        self.diagnostic = diagnostic
        self.pending_booking: Optional[Dict[str, str]] = None
        self.max_tool_rounds = 5

        key = api_key or os.getenv("GROQ_API_KEY")
        if not key:
            raise RuntimeError(
                "Missing GROQ_API_KEY. Set the environment variable before running the agent."
            )

        self.client = Groq(api_key=key)
        self.messages: List[Dict[str, Any]] = [
            {"role": "system", "content": system_prompt or SYSTEM_PROMPT}
        ]

    def role_sequence(self) -> List[str]:
        return [
            item.get("role")
            for item in self.messages
            if isinstance(item, dict) and "role" in item
        ]

    def get_final_state(self):
        from ai_beauty_appointment_manager.tools import SCHEDULE

        return {
            "schedule": dict(SCHEDULE),
            "pending_booking": self.pending_booking,
            "roles": self.role_sequence(),
        }

    def _message_to_dict(self, message: Any) -> Dict[str, Any]:
        if isinstance(message, dict):
            return dict(message)

        payload: Dict[str, Any] = {"role": getattr(message, "role", "assistant")}

        content = getattr(message, "content", None)
        if content is not None:
            payload["content"] = content

        tool_calls = getattr(message, "tool_calls", None)
        if tool_calls:
            payload["tool_calls"] = []
            for tool_call in tool_calls:
                payload["tool_calls"].append(
                    {
                        "id": tool_call.id,
                        "type": "function",
                        "function": {
                            "name": tool_call.function.name,
                            "arguments": tool_call.function.arguments,
                        },
                    }
                )

        return payload

    def _normalize_confirmation_text(self, text: str) -> str:
        cleaned = text.casefold()
        return " ".join(re.findall(r"[a-záéíóúüñ]+", cleaned))

    def _is_affirmative(self, text: str) -> bool:
        normalized = self._normalize_confirmation_text(text)
        affirmative_values = {
            "si",
            "sí",
            "confirmo",
            "confirmado",
            "ok",
            "vale",
            "listo",
            "adelante",
            "acepto",
        }
        if not normalized:
            return False
        first_word = normalized.split()[0]
        return normalized in affirmative_values or first_word in affirmative_values

    def _is_negative(self, text: str) -> bool:
        normalized = self._normalize_confirmation_text(text)
        negative_values = {"no", "cancelar", "cancelado", "nunca"}
        if not normalized:
            return False
        first_word = normalized.split()[0]
        return normalized in negative_values or first_word in negative_values

    def _format_time_for_customer(self, slot: str) -> str:
        try:
            hour_text, minute_text = slot.split(":", 1)
            hour = int(hour_text)
            minute = minute_text.zfill(2)
            period = "a. m." if hour < 12 else "p. m."
            display_hour = 12 if hour % 12 == 0 else hour % 12
            return f"{display_hour}:{minute} {period}"
        except (TypeError, ValueError):
            return slot

    def _build_confirmation_prompt(self, pending_booking: Dict[str, str]) -> str:
        customer = pending_booking.get("customer_name", "Cliente").strip() or "Cliente"
        service = pending_booking.get("service_name", "servicio").strip() or "servicio"
        slot = pending_booking.get("appointment_slot", "ese horario").strip() or "ese horario"
        time_text = self._format_time_for_customer(slot)
        return f"{customer}, ¿quieres confirmar tu solicitud de {service.lower()} para las {time_text}?"

    def _build_success_message(self, pending_booking: Dict[str, str]) -> str:
        customer = pending_booking.get("customer_name", "Cliente").strip() or "Cliente"
        service = pending_booking.get("service_name", "servicio").strip() or "servicio"
        slot = pending_booking.get("appointment_slot", "ese horario").strip() or "ese horario"
        time_text = self._format_time_for_customer(slot)
        return f"{customer}, tu solicitud de {service.lower()} para las {time_text} quedó registrada y está pendiente de aprobación."

    def _format_tool_error_for_customer(self, payload: Dict[str, Any]) -> str:
        message = str(payload.get("error", "No pude completar la solicitud de cita."))
        lowered = message.lower()

        if "already booked" in lowered or "ocupado" in lowered or "available" in lowered:
            return "Ese horario ya está ocupado. Puedo ayudarte con otros horarios disponibles."
        if "does not exist" in lowered or "no existe" in lowered:
            return "Ese servicio o horario no está disponible en este momento."
        if "confirm" in lowered:
            return "Necesito tu confirmación para registrar la cita."
        if "customer name" in lowered or "name" in lowered:
            return "Necesito el nombre del cliente para registrar la solicitud."
        return message

    def _prepare_pending_booking_from_message(self, message: str) -> Optional[Dict[str, str]]:
        from ai_beauty_appointment_manager.data_access import load_service_prices
        from ai_beauty_appointment_manager.tools import SCHEDULE

        if not message:
            return None

        normalized_message = " ".join(message.casefold().split())
        service_catalog = load_service_prices()
        service_name = None
        for candidate in service_catalog:
            normalized_candidate = " ".join(candidate.casefold().split())
            if normalized_candidate in normalized_message:
                service_name = candidate
                break

        if service_name is None:
            return None

        slot_match = None
        time_match = re.search(r"\b(\d{1,2}):(\d{2})\b", message)
        if time_match:
            hour = int(time_match.group(1))
            minute = time_match.group(2)
            normalized_slot = f"{hour:02d}:{minute}"
            if normalized_slot in SCHEDULE and SCHEDULE.get(normalized_slot) is None:
                slot_match = normalized_slot

        if slot_match is None:
            return None

        customer_name = None
        for pattern in ("a nombre de ", "para ", "por "):
            if pattern in message.casefold():
                remainder = message.split(pattern, 1)[1].strip()
                customer_name = remainder.strip(".,;:!? ")
                if customer_name:
                    break

        if not customer_name:
            return None

        return {
            "service_name": service_name,
            "appointment_slot": slot_match,
            "customer_name": customer_name,
        }

    def _call_model(self):
        response = self.client.chat.completions.create(
            model=self.model,
            messages=self.messages,
            tools=TOOLS,
            tool_choice="auto",
        )

        if self.diagnostic and getattr(response, "usage", None):
            usage = response.usage
            print(
                "[tokens] input={0} output={1}".format(
                    getattr(usage, "prompt_tokens", "unknown"),
                    getattr(usage, "completion_tokens", "unknown"),
                )
            )

        return response

    def _matches_pending_booking(self, booking_details: Dict[str, Any]) -> bool:
        if self.pending_booking is None:
            return False

        for field in ("service_name", "appointment_slot", "customer_name"):
            if str(self.pending_booking.get(field, "")).strip() != str(booking_details.get(field, "")).strip():
                return False

        return bool(booking_details.get("confirmed", False)) is True

    def _execute_tool_call(self, tool_call: Any) -> str:
        tool_name = tool_call.function.name
        arguments_json = tool_call.function.arguments or "{}"

        if tool_name == "book_appointment":
            try:
                arguments = json.loads(arguments_json)
            except json.JSONDecodeError:
                arguments = {}

            if not isinstance(arguments, dict):
                arguments = {}

            service_name = arguments.get("service_name")
            appointment_slot = arguments.get("appointment_slot")
            customer_name = arguments.get("customer_name")
            confirmed = arguments.get("confirmed", False)

            if bool(confirmed) is True:
                if not self._matches_pending_booking(arguments):
                    return json.dumps(
                        {
                            "error": "Booking requires explicit customer confirmation for the exact pending details.",
                            "requires_confirmation": True,
                            "service_name": str(service_name or ""),
                            "appointment_slot": str(appointment_slot or ""),
                            "customer_name": str(customer_name or ""),
                        },
                        ensure_ascii=False,
                    )

            if bool(confirmed) is not True:
                self.pending_booking = {
                    "service_name": str(service_name or ""),
                    "appointment_slot": str(appointment_slot or ""),
                    "customer_name": str(customer_name or ""),
                }
                return json.dumps(
                    {
                        "requires_confirmation": True,
                        "service_name": str(service_name or ""),
                        "appointment_slot": str(appointment_slot or ""),
                        "customer_name": str(customer_name or ""),
                    },
                    ensure_ascii=False,
                )

        return dispatch_tool(tool_name, arguments_json)

    def respond(self, message: str) -> str:
        if message is None:
            return ""

        cleaned = str(message).strip()
        if not cleaned:
            return ""

        if self.pending_booking is not None:
            if self._is_affirmative(cleaned):
                booking = dict(self.pending_booking)
                self.pending_booking = None
                self.messages.append({"role": "user", "content": cleaned})

                arguments = json.dumps(
                    {
                        "service_name": booking.get("service_name", ""),
                        "appointment_slot": booking.get("appointment_slot", ""),
                        "customer_name": booking.get("customer_name", ""),
                        "confirmed": True,
                    },
                    ensure_ascii=False,
                )
                if self.diagnostic:
                    print("[application] book_appointment", arguments)

                result = dispatch_tool("book_appointment", arguments)

                try:
                    payload = json.loads(result)
                except json.JSONDecodeError:
                    payload = {"error": "No pude procesar la solicitud de cita."}

                if isinstance(payload, dict) and payload.get("status") == "pending":
                    answer = self._build_success_message(booking)
                    self.messages.append({"role": "assistant", "content": answer})
                    return answer

                if isinstance(payload, dict) and payload.get("error"):
                    answer = self._format_tool_error_for_customer(payload)
                    self.messages.append({"role": "assistant", "content": answer})
                    return answer

                answer = "No pude completar la solicitud de cita."
                self.messages.append({"role": "assistant", "content": answer})
                return answer

            if self._is_negative(cleaned):
                self.pending_booking = None
                self.messages.append({"role": "user", "content": cleaned})
                answer = "Entendido. No se ha registrado ninguna cita."
                self.messages.append({"role": "assistant", "content": answer})
                return answer

        prepared_booking = self._prepare_pending_booking_from_message(cleaned)
        if prepared_booking is not None:
            self.pending_booking = prepared_booking
            self.messages.append({"role": "user", "content": cleaned})
            confirmation_prompt = self._build_confirmation_prompt(self.pending_booking)
            self.messages.append({"role": "assistant", "content": confirmation_prompt})
            if self.diagnostic:
                print("[history]", self.role_sequence())
            return confirmation_prompt

        self.messages.append({"role": "user", "content": cleaned})

        response = self._call_model()
        rounds = 0

        while getattr(response.choices[0].message, "tool_calls", None) and rounds < self.max_tool_rounds:
            rounds += 1
            assistant_message = self._message_to_dict(response.choices[0].message)
            self.messages.append(assistant_message)

            if self.diagnostic:
                print("[tool]", assistant_message.get("tool_calls"))

            for tool_call in response.choices[0].message.tool_calls:
                result = self._execute_tool_call(tool_call)
                if self.diagnostic:
                    print(
                        "[tool]",
                        tool_call.function.name,
                        tool_call.function.arguments,
                        result,
                    )

                self.messages.append(
                    {
                        "role": "tool",
                        "tool_call_id": tool_call.id,
                        "name": tool_call.function.name,
                        "content": result,
                    }
                )

                try:
                    payload = json.loads(result)
                except json.JSONDecodeError:
                    payload = {}

                if isinstance(payload, dict) and payload.get("requires_confirmation"):
                    self.pending_booking = {
                        "service_name": str(payload.get("service_name", "")),
                        "appointment_slot": str(payload.get("appointment_slot", "")),
                        "customer_name": str(payload.get("customer_name", "")),
                    }

            response = self._call_model()

        final_message = response.choices[0].message
        if final_message.tool_calls:
            self.messages.append(self._message_to_dict(final_message))
            if self.diagnostic:
                print("[tool] model exceeded the tool-call limit")
            return "No pude completar esta consulta. Inténtalo de nuevo."

        self.messages.append(self._message_to_dict(final_message))

        answer = final_message.content or "No pude generar una respuesta."
        cleaned_answer = answer.replace("**", "").strip()

        if self.pending_booking and "sí" not in cleaned_answer.casefold():
            confirmation_prompt = self._build_confirmation_prompt(self.pending_booking)
            if self.diagnostic:
                print("[history]", self.role_sequence())
            return confirmation_prompt

        if self.diagnostic:
            print("[final state]", json.dumps(self.get_final_state(), ensure_ascii=False))
            print("[history]", self.role_sequence())

        return cleaned_answer
