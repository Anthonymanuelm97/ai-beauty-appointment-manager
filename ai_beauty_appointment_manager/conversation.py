from __future__ import annotations

from typing import Optional

from ai_beauty_appointment_manager.agent import Agent


def run_conversation(agent: Optional[Agent] = None, *, diagnostic: bool = False):
    if agent is None:
        agent = Agent(diagnostic=diagnostic)

    print("Asistente: ¡Bienvenido! ¿En qué puedo ayudarte?")
    print("Escribe 'salir' para terminar la conversación.")

    while True:
        try:
            user_message = input("\nCliente: ").strip()
        except EOFError:
            print("\nAsistente: No recibí más entrada. ¡Hasta luego!")
            break
        except KeyboardInterrupt:
            print("\nAsistente: Se interrumpió la conversación. ¡Hasta luego!")
            break

        if user_message.casefold() == "salir":
            print("Asistente: ¡Hasta luego!")
            if agent.diagnostic:
                print("[final state]", agent.get_final_state())
                print("[history]", agent.role_sequence())
            break

        if not user_message:
            print("Asistente: Necesito que me escribas tu consulta.")
            continue

        response = agent.respond(user_message)
        if response:
            print(f"\nAsistente: {response}")
