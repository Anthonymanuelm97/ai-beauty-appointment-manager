import io
import json
import unittest
from contextlib import redirect_stdout
from types import SimpleNamespace
from unittest.mock import patch

from ai_beauty_appointment_manager import tools as tools_module
from ai_beauty_appointment_manager.agent import Agent
from ai_beauty_appointment_manager.data_access import load_schedule


def reset_schedule():
    tools_module.SCHEDULE = load_schedule()


def make_tool_call(function_name, arguments):
    return SimpleNamespace(
        function=SimpleNamespace(
            name=function_name,
            arguments=json.dumps(arguments, ensure_ascii=False),
        )
    )


class AgentBookingSafetyTests(unittest.TestCase):
    def setUp(self):
        reset_schedule()

    def test_full_two_turn_booking_flow_registers_pending_proposal_before_confirmation(self):
        agent = Agent(api_key="test-key")
        first_response = agent.respond("Quiero un corte clásico a las 9:00, a nombre de Ana.")

        self.assertIn("Ana", first_response)
        self.assertIn("corte clásico", first_response.lower())
        self.assertIn("9:00", first_response)
        self.assertNotIn("servicio", first_response.lower())
        self.assertNotIn("horario", first_response.lower())
        self.assertEqual(agent.pending_booking["service_name"], "Corte clásico")
        self.assertEqual(agent.pending_booking["appointment_slot"], "09:00")
        self.assertEqual(agent.pending_booking["customer_name"], "Ana")
        self.assertIsNone(tools_module.SCHEDULE["09:00"])
        self.assertEqual(agent.role_sequence()[-3:], ["system", "user", "assistant"])

        from ai_beauty_appointment_manager.tool_dispatcher import dispatch_tool as real_dispatch_tool

        with patch(
            "ai_beauty_appointment_manager.agent.dispatch_tool",
            side_effect=real_dispatch_tool,
        ) as mock_dispatch:
            second_response = agent.respond("Sí, confirmo la solicitud.")

        self.assertIn("pendiente", second_response.lower())
        self.assertEqual(tools_module.SCHEDULE["09:00"], "Ana")
        self.assertIsNone(agent.pending_booking)
        self.assertEqual(agent.role_sequence()[-5:], ["system", "user", "assistant", "user", "assistant"])
        mock_dispatch.assert_called_once()
        self.assertNotIn("confirmar", second_response.lower())

    def test_diagnostic_logs_distinguish_application_execution(self):
        agent = Agent(api_key="test-key", diagnostic=True)
        agent.pending_booking = {
            "service_name": "Corte clásico",
            "appointment_slot": "09:00",
            "customer_name": "Ana",
        }

        with patch(
            "ai_beauty_appointment_manager.agent.dispatch_tool",
            side_effect=lambda tool_name, arguments_json: json.dumps(
                {
                    "status": "pending",
                    "service": "Corte clásico",
                    "appointment_slot": "09:00",
                    "customer_name": "Ana",
                },
                ensure_ascii=False,
            ),
        ):
            buffer = io.StringIO()
            with redirect_stdout(buffer):
                response = agent.respond("sí")

        self.assertIn("pendiente", response.lower())
        self.assertIn("[application] book_appointment", buffer.getvalue())

    def test_unauthorized_confirmed_booking_is_blocked(self):
        agent = Agent(api_key="test-key")
        tool_call = make_tool_call(
            "book_appointment",
            {
                "service_name": "Corte clásico",
                "appointment_slot": "09:00",
                "customer_name": "Ana",
                "confirmed": True,
            },
        )

        result = json.loads(agent._execute_tool_call(tool_call))

        self.assertIn("error", result)
        self.assertIn("explicit customer confirmation", result["error"].lower())
        self.assertIsNone(agent.pending_booking)

    def test_mismatched_booking_details_are_rejected(self):
        agent = Agent(api_key="test-key")
        agent.pending_booking = {
            "service_name": "Corte clásico",
            "appointment_slot": "11:00",
            "customer_name": "Ana",
        }

        tool_call = make_tool_call(
            "book_appointment",
            {
                "service_name": "Corte clásico",
                "appointment_slot": "09:00",
                "customer_name": "Ana",
                "confirmed": True,
            },
        )

        result = json.loads(agent._execute_tool_call(tool_call))

        self.assertIn("error", result)
        self.assertIn("exact pending details", result["error"].lower())

    def test_cancellation_clears_pending_booking(self):
        agent = Agent(api_key="test-key")
        agent.pending_booking = {
            "service_name": "Corte clásico",
            "appointment_slot": "09:00",
            "customer_name": "Ana",
        }

        response = agent.respond("no")

        self.assertEqual(response, "Entendido. No se ha registrado ninguna cita.")
        self.assertIsNone(agent.pending_booking)
        self.assertEqual(agent.messages[-1]["role"], "assistant")

    def test_authorized_confirmation_executes_booking_once(self):
        agent = Agent(api_key="test-key")
        agent.pending_booking = {
            "service_name": "Corte clásico",
            "appointment_slot": "09:00",
            "customer_name": "Ana",
        }

        from ai_beauty_appointment_manager.tool_dispatcher import dispatch_tool as real_dispatch_tool

        with patch(
            "ai_beauty_appointment_manager.agent.dispatch_tool",
            side_effect=real_dispatch_tool,
        ) as mock_dispatch:
            response = agent.respond("sí")

        self.assertIn("pendiente", response.lower())
        self.assertIsNone(agent.pending_booking)
        mock_dispatch.assert_called_once()


if __name__ == "__main__":
    unittest.main()
