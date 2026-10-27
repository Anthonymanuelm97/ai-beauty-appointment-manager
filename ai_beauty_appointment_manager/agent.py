from __future__ import annotations

import json
import os
import re
import unicodedata
from typing import Any, Dict, List, Optional

from dotenv import load_dotenv
from groq import Groq

from ai_beauty_appointment_manager.system_prompts import SYSTEM_PROMPT
from ai_beauty_appointment_manager.tool_dispatcher import dispatch_tool
from ai_beauty_appointment_manager.tool_schemas import TOOLS
from ai_beauty_appointment_manager.tools import _validate_booking_proposal


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
        normalized = unicodedata.normalize("NFKD", text.casefold())
        normalized = "".join(
            character
            for character in normalized
            if not unicodedata.combining(character)
        )
        return " ".join(re.findall(r"[a-záéíóúüñ]+", normalized))

    def _is_affirmative(self, text: str) -> bool:
        normalized = self._normalize_confirmation_text(text)
        affirmative_values = {
            "si",
            "confirmo",
            "confirmado",
            "correcto",
            "ok",
            "vale",
            "listo",
            "adelante",
            "acepto",
            "si confirmo",
            "si confirmo la solicitud",
            "si acepto",
            "correcto confirmo",
            "de acuerdo",
            "claro",
        }
        return normalized in affirmative_values

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

        if not message:
            return None

        normalized_message = self._normalize_confirmation_text(message)
        service_catalog = load_service_prices()
        service_name = None
        for candidate in service_catalog:
            normalized_candidate = self._normalize_confirmation_text(candidate)
            if re.search(
                rf"(?<!\w){re.escape(normalized_candidate)}(?!\w)",
                normalized_message,
            ):
                service_name = candidate
                break

        if service_name is None:
            return None

        time_match = re.search(r"\b(\d{1,2}):(\d{2})\b", message)
        if time_match is None:
            return None

        hour = int(time_match.group(1))
        appointment_slot = f"{hour:02d}:{time_match.group(2)}"
        name_match = re.search(
            r"\b(?:a nombre de|para)\s+([^,.;!?]+)",
            message,
            flags=re.IGNORECASE,
        )
        if name_match is None:
            return None

        customer_name = name_match.group(1).strip()
        if re.fullmatch(r"(?:las?\s+)?\d{1,2}(?::\d{2})?", customer_name, re.IGNORECASE):
            return None

        proposal, error = _validate_booking_proposal(
            service_name,
            appointment_slot,
            customer_name,
        )
        return proposal if error is None else None

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
        if self.diagnostic and getattr(response, "choices", None):
            print("[finish_reason]", getattr(response.choices[0], "finish_reason", None))

        return response

    def _execute_tool_call(self, tool_call: Any) -> str:
        tool_name = tool_call.function.name
        arguments_json = tool_call.function.arguments or "{}"

        if tool_name == "book_appointment":
            try:
                arguments = json.loads(arguments_json)
            except json.JSONDecodeError:
                return json.dumps({"error": "Invalid JSON arguments."}, ensure_ascii=False)

            if not isinstance(arguments, dict):
                return json.dumps(
                    {"error": "Tool arguments must be a JSON object."},
                    ensure_ascii=False,
                )

            confirmed = arguments.get("confirmed", False)
            if confirmed is True:
                return json.dumps(
                    {
                        "error": "Booking requires explicit customer confirmation for the exact pending details.",
                        "requires_confirmation": True,
                    },
                    ensure_ascii=False,
                )

            if confirmed is not False:
                return json.dumps(
                    {"error": "Booking proposal must use confirmed=false."},
                    ensure_ascii=False,
                )

            proposal, error = _validate_booking_proposal(
                arguments.get("service_name"),
                arguments.get("appointment_slot"),
                arguments.get("customer_name"),
            )
            if error is not None:
                return json.dumps(error, ensure_ascii=False)

            self.pending_booking = proposal
            return json.dumps(
                {"requires_confirmation": True, **proposal},
                ensure_ascii=False,
            )

        return dispatch_tool(tool_name, arguments_json)

    def _is_unusable_response(self, content: Any) -> bool:
        if not isinstance(content, str) or not content.strip():
            return True

        return bool(
            re.search(
                r"\b([^\W\d_]+)\s+\1\s+[^\W\d_]{1,2}(?:…|\.{3})",
                content,
                flags=re.IGNORECASE,
            )
        )

    def _looks_like_confirmation_request(self, content: str) -> bool:
        normalized = self._normalize_confirmation_text(content)
        return "confirm" in normalized and (
            "si" in normalized or "solicitud" in normalized
        )

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

            self.pending_booking = None

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

        while True:
            choices = getattr(response, "choices", None)
            if not choices:
                answer = "No pude generar una respuesta clara en este momento. Inténtalo de nuevo."
                self.messages.append({"role": "assistant", "content": answer})
                return answer

            choice = choices[0]
            model_message = choice.message
            tool_calls = getattr(model_message, "tool_calls", None)
            if not tool_calls:
                break

            if rounds >= self.max_tool_rounds:
                if self.diagnostic:
                    print("[tool] model exceeded the tool-call limit")
                answer = "No pude completar esta consulta. Inténtalo de nuevo."
                self.messages.append({"role": "assistant", "content": answer})
                return answer

            rounds += 1
            assistant_message = self._message_to_dict(model_message)
            self.messages.append(assistant_message)

            if self.diagnostic:
                print("[tool]", assistant_message.get("tool_calls"))

            for tool_call in tool_calls:
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

            response = self._call_model()

        final_message = choice.message
        if self.pending_booking is not None:
            answer = self._build_confirmation_prompt(self.pending_booking)
        else:
            finish_reason = getattr(choice, "finish_reason", None)
            content = getattr(final_message, "content", None)
            if (
                finish_reason == "length"
                or self._is_unusable_response(content)
                or self._looks_like_confirmation_request(content)
            ):
                answer = "No pude generar una respuesta clara en este momento. Inténtalo de nuevo."
            else:
                answer = content.replace("**", "").strip()

        self.messages.append({"role": "assistant", "content": answer})

        if self.diagnostic:
            print("[final state]", json.dumps(self.get_final_state(), ensure_ascii=False))
            print("[history]", self.role_sequence())

        return answer
