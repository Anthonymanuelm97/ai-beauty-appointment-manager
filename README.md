# AI Beauty Appointment Manager

An educational Python terminal assistant for a fictional Dominican Republic barbershop. It uses Groq tool calling to look up demonstration availability, calculate service prices from an Excel workbook, and prepare appointment requests for customer confirmation.

## Implemented

- Terminal conversation in Spanish (es-DO), using Dominican pesos (RD$) and customer-friendly 12-hour times.
- Excel-based service catalog and demonstration schedule in `data/business_data.xlsx`.
- Availability lookup that does not change the schedule.
- Price calculation for multiple services, with a fixed 10% discount for eligible frequent customers.
- Appointment proposals validated against the official service catalog and currently available demonstration slots.
- Explicit customer authorization before Python registers a request. Registered requests have `pending` status and still require business approval.
- Diagnostic output for tool calls, model completion status, application-side booking actions, conversation roles, and final demonstration state.
- Automated regression tests using mocked Groq responses.

## Requirements

- Python 3.14 or newer. The required version matches `requires-python` in `pyproject.toml`.
- [uv](https://docs.astral.sh/uv/) for dependency and environment management.
- A Groq API key for live terminal conversations. Automated tests mock model responses and do not require a live API key.

## Setup

From the repository root, synchronize the project environment and dependencies:

```powershell
uv sync
```

Create a `.env` file in the repository root. Add your own Groq API key locally; do not commit the file or share the key:

```dotenv
GROQ_API_KEY=your_groq_api_key
```

The application loads this value through `python-dotenv`. Keep real credentials out of source code, screenshots, logs, and version control.

## Run the terminal agent

Start a normal interactive session:

```powershell
uv run python main.py
```

Enable diagnostic mode with the command-line option:

```powershell
uv run python main.py --diagnostic
```

Diagnostic mode can also be enabled with `DIAGNOSTIC_MODE=true` in `.env`. Enter `salir` to end the conversation. Diagnostics may include customer conversation content; handle terminal output accordingly.

## Business tools and Groq tool calling

The model can request one of three Python business tools. Python validates and executes each tool call, then returns its result to the model as a correlated tool response:

1. `get_available_slots` reads the demonstration schedule and returns unoccupied time slots.
2. `calculate_total` checks service names against the Excel catalog and calculates line totals, subtotal, any eligible fixed 10% frequent-customer discount, and total.
3. `book_appointment` validates the booking details and registers a pending appointment request. The Agent prepares and validates the proposal without modifying the schedule. Only after explicit customer authorization does Python execute the booking operation.

Model-generated booking calls cannot authorize a booking by setting `confirmed=true`. A successful customer authorization registers the request as `pending`, not as business-approved. The Python application generates the confirmation question and the pending-status response.

## Customer interaction

The assistant is intended to communicate in natural, professional Spanish (es-DO). Prices are shown in Dominican pesos (RD$), and appointment times use familiar 12-hour formatting.

Example:

> Customer: Quiero un corte clásico a las 9:00, a nombre de Ana.
>
> Assistant: Ana, ¿quieres confirmar tu solicitud de corte clásico para las 9:00 a. m.?
>
> Customer: Sí, confirmo.
>
> Assistant: Ana, tu solicitud de corte clásico para las 9:00 a. m. quedó registrada y está pendiente de aprobación.

The final message confirms that the request was recorded in the demonstration schedule; it does not mean the business approved the appointment.

## Automated tests

Run the complete unittest suite:

```powershell
uv run python -m unittest discover -s tests -p "test_*.py" -v
```

The suite includes booking authorization and schedule safety, mocked Groq tool-call flows, authoritative price results, and graceful handling of empty, truncated, or specifically detected malformed responses.

## Limitations

- The schedule is an in-memory demonstration loaded from Excel when the application starts. Changes are not persisted to the workbook and do not survive a restart.
- The demonstration schedule contains time slots, not date-specific calendars or real availability across dates.
- Payment processing and payment verification are not implemented.
- Appointment requests are pending until a person approves them; there is no owner administration dashboard or approval workflow in this project.
- Groq-generated wording cannot be guaranteed to be perfect for every input. The application uses deterministic Python text for booking confirmations and a safe fallback for known unusable response conditions.
- The project is an educational demonstration, not a production booking service.

## Planned roadmap

The following are future possibilities, not implemented features: persistent appointment storage, real date-based scheduling, payment or bank-transfer verification, an owner administration panel, multiple branches or professionals, automatic expiration of pending requests, and configurable business information. This documentation describes the current implementation only.

## MVP Validation

We validated the MVP through six realistic customer interaction scenarios, supported by diagnostic logs and automated regression tests.

These scenarios cover appointment availability, multi-service pricing, frequent-customer discounts, explicit booking confirmation, occupied-slot rejection, and unauthorized discount requests.

Detailed test scenarios, expected outcomes, and diagnostic checks are documented in [MVP Verification](docs/mvp_verification.md).
