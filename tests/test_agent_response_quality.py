import json
import unittest
from types import SimpleNamespace
from unittest.mock import patch

from ai_beauty_appointment_manager import tools as tools_module
from ai_beauty_appointment_manager.agent import Agent
from ai_beauty_appointment_manager.data_access import load_schedule


def reset_schedule():
    tools_module.SCHEDULE = load_schedule()


def make_tool_call(function_name, arguments, call_id):
    return SimpleNamespace(
        id=call_id,
        type="function",
        function=SimpleNamespace(
            name=function_name,
            arguments=json.dumps(arguments, ensure_ascii=False),
        ),
    )


def make_response(content=None, *, tool_calls=None, finish_reason="stop"):
    message = SimpleNamespace(
        role="assistant",
        content=content,
        tool_calls=tool_calls,
    )
    return SimpleNamespace(
        choices=[SimpleNamespace(message=message, finish_reason=finish_reason)],
        usage=None,
    )


class AgentProposalFlowTests(unittest.TestCase):
    def setUp(self):
        reset_schedule()

    def test_tool_checked_proposal_is_validated_before_python_confirmation_is_shown(self):
        agent = Agent(api_key="test-key")
        calls = [
            make_tool_call("get_available_slots", {}, "slots-call"),
            make_tool_call(
                "calculate_total",
                {"items": [{"service": "Corte clásico", "quantity": 1}]},
                "price-call",
            ),
            make_tool_call(
                "book_appointment",
                {
                    "service_name": "Corte clásico",
                    "appointment_slot": "09:00",
                    "customer_name": "Ana",
                    "confirmed": False,
                },
                "proposal-call",
            ),
        ]
        tool_response = make_response(tool_calls=calls, finish_reason="tool_calls")
        final_response = make_response(
            "Por favor, confirma con un sí si deseas que registre la solicitud."
        )

        def model_response():
            if not agent.pending_booking:
                return tool_response

            self.assertEqual(
                agent.pending_booking,
                {
                    "service_name": "Corte clásico",
                    "appointment_slot": "09:00",
                    "customer_name": "Ana",
                },
            )
            self.assertIsNone(tools_module.SCHEDULE["09:00"])
            return final_response

        with patch.object(agent, "_call_model", side_effect=model_response) as model_call:
            answer = agent.respond("Quiero reservar una cita.")

        self.assertEqual(
            answer,
            "Ana, ¿quieres confirmar tu solicitud de corte clásico para las 9:00 a. m.?",
        )
        self.assertEqual(model_call.call_count, 2)
        tool_messages = [item for item in agent.messages if item["role"] == "tool"]
        self.assertEqual(
            {item["tool_call_id"] for item in tool_messages},
            {"slots-call", "price-call", "proposal-call"},
        )
        availability = json.loads(tool_messages[0]["content"])
        price = json.loads(tool_messages[1]["content"])
        self.assertIn("09:00", availability["available_slots"])
        self.assertEqual(price["total"], 400)
        self.assertEqual(tools_module.SCHEDULE["09:00"], None)
        self.assertEqual(agent.messages[-1]["content"], answer)
        self.assertEqual(
            agent.role_sequence(),
            ["system", "user", "assistant", "tool", "tool", "tool", "assistant"],
        )

    def test_one_explicit_affirmation_registers_exact_proposal_once(self):
        affirmations = (
            "Sí",
            "Si",
            "Sí.",
            "Si, confirmo.",
            "Sí, confirmo la solicitud.",
            "Correcto",
        )

        for affirmation in affirmations:
            with self.subTest(affirmation=affirmation):
                reset_schedule()
                agent = Agent(api_key="test-key")
                agent.pending_booking = {
                    "service_name": "Corte clásico",
                    "appointment_slot": "09:00",
                    "customer_name": "Ana",
                }

                from ai_beauty_appointment_manager.tool_dispatcher import (
                    dispatch_tool as real_dispatch_tool,
                )

                with patch(
                    "ai_beauty_appointment_manager.agent.dispatch_tool",
                    side_effect=real_dispatch_tool,
                ) as dispatch:
                    answer = agent.respond(affirmation)

                self.assertIn("pendiente de aprobación", answer)
                self.assertNotIn("confirmar", answer.lower())
                self.assertEqual(tools_module.SCHEDULE["09:00"], "Ana")
                self.assertIsNone(agent.pending_booking)
                dispatch.assert_called_once()
                self.assertEqual(agent.messages[-2]["content"], affirmation)
                self.assertEqual(agent.messages[-1]["content"], answer)

    def test_cancellation_and_changed_details_do_not_authorize_old_proposal(self):
        original_schedule = dict(tools_module.SCHEDULE)
        agent = Agent(api_key="test-key")
        agent.pending_booking = {
            "service_name": "Corte clásico",
            "appointment_slot": "09:00",
            "customer_name": "Ana",
        }

        self.assertEqual(
            agent.respond("No"),
            "Entendido. No se ha registrado ninguna cita.",
        )
        self.assertIsNone(agent.pending_booking)
        self.assertEqual(tools_module.SCHEDULE, original_schedule)

        agent.pending_booking = {
            "service_name": "Corte clásico",
            "appointment_slot": "09:00",
            "customer_name": "Ana",
        }
        with patch.object(agent, "_call_model", return_value=make_response("¿Qué servicio deseas?")):
            agent.respond("Cambia el horario a las 10:00, a nombre de Beatriz.")

        self.assertIsNone(agent.pending_booking)
        self.assertEqual(tools_module.SCHEDULE, original_schedule)

        agent.pending_booking = {
            "service_name": "Corte clásico",
            "appointment_slot": "09:00",
            "customer_name": "Ana",
        }
        with (
            patch.object(agent, "_call_model", return_value=make_response("¿Qué servicio deseas?")),
            patch("ai_beauty_appointment_manager.agent.dispatch_tool") as dispatch,
        ):
            agent.respond("Sí, pero cambia el horario a las 10:00.")

        self.assertIsNone(agent.pending_booking)
        self.assertEqual(tools_module.SCHEDULE, original_schedule)
        dispatch.assert_not_called()

        agent.pending_booking = {
            "service_name": "Corte clásico",
            "appointment_slot": "09:00",
            "customer_name": "Ana",
        }
        with (
            patch.object(agent, "_call_model", return_value=make_response("¿Qué servicio deseas?")),
            patch("ai_beauty_appointment_manager.agent.dispatch_tool") as dispatch,
        ):
            agent.respond(
                "Sí, soy Beatriz y prefiero un arreglo de barba a las 10:00."
            )

        self.assertIsNone(agent.pending_booking)
        self.assertEqual(tools_module.SCHEDULE, original_schedule)
        dispatch.assert_not_called()

    def test_model_confirmed_true_is_blocked_even_if_details_match_pending(self):
        agent = Agent(api_key="test-key")
        agent.pending_booking = {
            "service_name": "Corte clásico",
            "appointment_slot": "09:00",
            "customer_name": "Ana",
        }
        call = make_tool_call(
            "book_appointment",
            {
                "service_name": "Corte clásico",
                "appointment_slot": "09:00",
                "customer_name": "Ana",
                "confirmed": True,
            },
            "unauthorized-call",
        )

        result = json.loads(agent._execute_tool_call(call))

        self.assertIn("error", result)
        self.assertIsNone(tools_module.SCHEDULE["09:00"])
        self.assertEqual(agent.pending_booking["customer_name"], "Ana")

    def test_invalid_or_occupied_model_proposal_never_becomes_pending(self):
        agent = Agent(api_key="test-key")
        tools_module.SCHEDULE["09:00"] = "Existing customer"

        call = make_tool_call(
            "book_appointment",
            {
                "service_name": "Corte clásico",
                "appointment_slot": "09:00",
                "customer_name": "Ana",
                "confirmed": False,
            },
            "occupied-call",
        )

        result = json.loads(agent._execute_tool_call(call))

        self.assertIn("error", result)
        self.assertIsNone(agent.pending_booking)
        self.assertEqual(tools_module.SCHEDULE["09:00"], "Existing customer")


class AgentResponseQualityTests(unittest.TestCase):
    def setUp(self):
        reset_schedule()

    def test_price_response_preserves_authoritative_tool_result_and_plain_text(self):
        agent = Agent(api_key="test-key")
        calls = [
            make_tool_call(
                "calculate_total",
                {
                    "items": [
                        {"service": "Corte clásico", "quantity": 2},
                        {"service": "Arreglo de barba", "quantity": 1},
                    ]
                },
                "price-call",
            )
        ]
        responses = [
            make_response(tool_calls=calls, finish_reason="tool_calls"),
            make_response(
                "**Dos cortes clásicos cuestan RD$800 y un arreglo de barba RD$250. "
                "El total es RD$1,050.** ¿Te gustaría consultar los horarios disponibles?"
            ),
        ]

        with patch.object(agent, "_call_model", side_effect=responses):
            answer = agent.respond("¿Cuánto cuestan 2 cortes clásicos y 1 arreglo de barba?")

        result = json.loads(
            next(item for item in agent.messages if item["role"] == "tool")["content"]
        )
        self.assertEqual(result["subtotal"], 1050)
        self.assertEqual(result["total"], 1050)
        self.assertIn("RD$800", answer)
        self.assertIn("RD$250", answer)
        self.assertIn("RD$1,050", answer)
        self.assertNotIn("**", answer)

    def test_empty_truncated_and_malformed_outputs_use_safe_fallback(self):
        outputs = (
            make_response(""),
            make_response("El total es RD$1,050. ¿Deseas", finish_reason="length"),
            make_response("¿Te gustaría cargar cargar c…? (¡ ... )"),
        )
        fallback = "No pude generar una respuesta clara en este momento. Inténtalo de nuevo."

        for response in outputs:
            with self.subTest(response=response.choices[0].message.content):
                agent = Agent(api_key="test-key")
                with patch.object(agent, "_call_model", return_value=response):
                    self.assertEqual(agent.respond("¿Cuánto cuesta?"), fallback)

    def test_model_confirmation_without_validated_proposal_is_not_shown(self):
        agent = Agent(api_key="test-key")
        with patch.object(
            agent,
            "_call_model",
            return_value=make_response(
                "Por favor, confirma con un sí si deseas que registre la solicitud."
            ),
        ):
            answer = agent.respond("Quiero reservar.")

        self.assertIn("No pude generar una respuesta clara", answer)
        self.assertIsNone(agent.pending_booking)

    def test_python_booking_messages_are_concise_and_make_no_unsupported_promises(self):
        agent = Agent(api_key="test-key")
        proposal = {
            "service_name": "Corte clásico",
            "appointment_slot": "09:00",
            "customer_name": "Ana",
        }

        question = agent._build_confirmation_prompt(proposal)
        success = agent._build_success_message(proposal)

        self.assertEqual(
            question,
            "Ana, ¿quieres confirmar tu solicitud de corte clásico para las 9:00 a. m.?",
        )
        self.assertIn("pendiente de aprobación", success)
        self.assertNotIn("aprobada", success.lower())
        self.assertNotIn("notificación", success.lower())
        self.assertNotIn("persistente", success.lower())


if __name__ == "__main__":
    unittest.main()
