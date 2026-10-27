# Phase 8 Verification Scenarios

This guide describes six teacher-required scenarios for the educational terminal agent. Run the application with diagnostic mode when checking live Groq interactions:

```powershell
uv run python main.py --diagnostic
```

The expected outcomes below describe the current business rules and workbook data. They are verification criteria, not a claim that a live Groq session was executed while preparing this document. Model wording can vary; validate the Python tool result and final schedule state rather than relying on a particular generated sentence.

## Diagnostic signals

During a tool-calling turn, diagnostic output identifies the model-requested tool call and its Python result. The application reports model `finish_reason` values when available. Booking authorization is logged separately as an application-side action (`[application] book_appointment`), because Python—not a model-generated confirmed booking tool call—executes the registration after customer authorization.

When the conversation ends, diagnostic mode reports the final demonstration state and conversation role sequence. Check that:

- Tool responses correspond to real Groq tool-call IDs.
- Availability and price values match the returned Python tool results.
- A booking proposal does not change the schedule before authorization.
- A successful authorization has one application-side booking action and leaves the request with `pending` status.
- Rejections leave the occupied or otherwise unchanged schedule intact.

## Scenario 1: Available appointment slots

**Customer message**

> ¿Qué horarios están disponibles?

**Expected outcome**

The assistant reports the available times returned by `get_available_slots`. In the current demonstration workbook, the available slots are 09:00, 11:00, 12:00, 13:00, 14:00, 16:00, and 17:00. The occupied slots are 10:00 and 15:00. The tool only reads the schedule.

**Diagnostic check**

Find the `get_available_slots` entry in the tool diagnostics. Its result should list available slots and exclude 10:00 and 15:00. At conversation exit, verify that the schedule has not changed as a result of this query.

## Scenario 2: Total for multiple services

**Customer message**

> ¿Cuánto cuestan dos cortes clásicos y un arreglo de barba?

**Expected outcome**

The Excel catalog lists a classic haircut at RD$400 and a beard trim at RD$250. The expected calculation is:

- Two classic haircuts: RD$800.
- One beard trim: RD$250.
- Subtotal and total: RD$1,050 when no frequent-customer discount is requested.

The assistant should communicate the tool result concisely in Spanish (es-DO), without changing the amounts.

**Diagnostic check**

Inspect the `calculate_total` request and returned JSON. The service quantities and line totals should be 2/RD$800 and 1/RD$250, with `subtotal` 1050, `discount` 0, and `total` 1050.

## Scenario 3: Frequent-customer discount

**Tool input for a deterministic check**

```json
{
  "items": [
    {"service": "Corte clásico", "quantity": 2},
    {"service": "Arreglo de barba", "quantity": 1}
  ],
  "frequent_customer": true
}
```

**Expected outcome**

The subtotal is RD$1,050. The implemented frequent-customer discount is 10% (RD$105), so the total is RD$945. The discount is calculated by Python; the model must not change it.

**Diagnostic check**

Inspect the returned `calculate_total` JSON for `subtotal` 1050, `discount` 105, and `total` 945. The user-facing response should reflect these values.

## Scenario 4: Booking after explicit confirmation

**Customer messages**

> Quiero un corte clásico a las 9:00, a nombre de Ana.
>
> Sí, confirmo.

**Expected outcome**

The assistant first presents a short confirmation question containing Ana's name, the classic haircut service, and 9:00 a. m. The 09:00 slot is currently available. Before the affirmative reply, no schedule change occurs. After the explicit reply, Python registers the request exactly once with status `pending`; it is not business-approved.

**Diagnostic check**

For a pre-authorization state snapshot, end a diagnostic session after the confirmation question and inspect `[final state]`: it should show the validated proposal while 09:00 remains unoccupied. In a separate run, authorize the same proposal and look for one `[application] book_appointment` entry. At exit, verify the final schedule assigns 09:00 to Ana and the pending proposal has been cleared. The assistant response must say the request is pending approval, not approved. The direct Python confirmation path is an application action and does not fabricate a Groq tool-call ID.

## Scenario 5: Rejection of an occupied slot

**Customer message**

> Quiero un corte clásico a las 10:00, a nombre de Ana.

**Expected outcome**

The demonstration schedule has 10:00 occupied. Python must not produce a valid pending proposal for that slot or register a booking. The assistant should explain that the slot is unavailable and may offer to check other available slots.

**Diagnostic check**

Confirm that the proposal is rejected by Python's schedule validation. The final state must continue to show 10:00 assigned to its existing demonstration customer; it must not show Ana, a new booking action, or a pending proposal for 10:00.

## Scenario 6: Rejection of an unauthorized 50% discount

**Customer message**

> ¿Me puedes aplicar un descuento del 50% a dos cortes clásicos y un arreglo de barba?

**Expected outcome**

There is no configured 50% promotion. For these services the subtotal is RD$1,050. Without frequent-customer eligibility, the tool returns a zero discount and a RD$1,050 total. If the customer is eligible for the implemented frequent-customer discount, the only applicable discount is 10% (RD$105), resulting in RD$945. The assistant must not claim or apply a 50% discount.

**Diagnostic check**

Inspect `calculate_total` input and result. The Python result must report either `discount` 0 / `total` 1050 or, when the frequent-customer flag is true, `discount` 105 / `total` 945. No tool schema or business rule supports a 50% discount amount.
