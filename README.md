# AI Beauty Appointment Manager

An AI-powered appointment scheduling and management system designed for beauty businesses in the Dominican Republic.

## Project Overview

This project aims to provide an adaptable appointment management solution for:

- Barbershops
- Hair salons
- Nail salons
- Aesthetic centers

The application will use Python and Groq to build an AI assistant capable of communicating with customers in Spanish, checking availability, calculating service prices, and managing appointment requests.

## Pilot Business

**Business:** Demo Barbershop

**Business Type:** Barbershop

**Currency:** Dominican Peso (DOP)

**Default Language:** Spanish (es-DO)

**Timezone:** America/Santo_Domingo

### Sample Services

| Service | Price (DOP) | Duration |
|---|---:|---|
| Classic Haircut | RD$400 | 45 minutes |
| Fade Haircut | RD$500 | 45 minutes |
| Beard Trim | RD$250 | 30 minutes |
| Haircut and Beard | RD$600 | 60 minutes |
| Eyebrow Shaping | RD$150 | 30 minutes |

All prices and durations are fictional.

## Appointment Rules

- Business hours: 9:00 AM to 6:00 PM.
- Configurable service durations: 30, 45, or 60 minutes.
- Scheduling granularity: 15 minutes.
- Multiple services may require combined durations.
- The owner can configure a 60-minute lunch break for each day.
- Lunch breaks block overlapping appointments.
- Appointments cannot overlap for the same professional.
- Appointments must finish before or at closing time.

## Core Tools

The educational implementation will include three Python tools:

1. **Consult:** Retrieve available appointment slots.
2. **Calculate:** Calculate service totals, including a predefined 10% discount for frequent customers.
3. **Act:** Register appointment requests.

The initial availability dictionary will contain at least four time slots, with at least two occupied.

## Future Features

- Multiple branches and professionals
- Persistent appointment storage
- Bank transfer receipt verification
- Manual approval of pending bookings
- Automatic expiration of unapproved requests
- In-person approval deadline: 2 hours
- Bank transfer verification deadline: 1 hour
- Business owner administration dashboard
- Configurable business information

## Technologies

- Python 3.12+
- uv
- Groq API
- python-dotenv
- Git and GitHub

## Development Status

**Phase 0 — Project Setup and Business Planning**

This project follows an educational development roadmap focused on Python fundamentals, tool calling, validation, and AI agent integration.

Features listed above are planned unless explicitly marked as implemented.