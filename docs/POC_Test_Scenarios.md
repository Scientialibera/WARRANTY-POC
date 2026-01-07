# Warranty Orchestrator POC - Test Scenarios

## Overview

This document describes the 6 test scenarios used to validate the Warranty Orchestrator POC. Each scenario tests a specific workflow path based on product type, warranty status, customer decisions, and territory serviceability.

**All tests run automatically** - no user input required. Simply run `python main.py` to execute all scenarios.

### Key Features Demonstrated
- **Real LLM Integration**: Uses Azure OpenAI (gpt-4o) for natural language understanding and decision making
- **Code Interpreter**: LLM uses `run_calculation` tool for all math operations (warranty days, cost differences)
- **Multi-turn Conversations**: HEAT path pauses for customer confirmation before proceeding
- **Tool Calling**: Orchestrator calls appropriate MCP tools based on context

---

## Scenario 1: HEAT + Active Warranty + Customer Agrees

### Input
| Field | Value |
|-------|-------|
| Product | HEAT-001 (ProLine XE Heat Pump Water Heater) |
| Warranty | Active until 2027-06-15 (parts, labor, controller) |
| Location | Houston, TX 77001 (Serviceable) |
| Customer Messages | 1. "My heat pump water heater is making strange noises" |
|                   | 2. "Yes, I'd like to proceed with the service" |

### Tool Call Sequence
```
TURN 1:
  Step 1: get_plan(user_message) ──────────────────────► Planner MCP returns workflow steps
  Step 2: calculate_charges(product_id, product_type) ─► Compute MCP returns charge breakdown
  Step 3: [LLM Response] ──────────────────────────────► Present charges, ASK: "Would you like to proceed?"

TURN 2:
  Step 4: check_territory(location) ───────────────────► Actions MCP returns serviceable=true
  Step 5: calculate_charges(product_id, product_type) ─► Compute MCP returns charge breakdown  
  Step 6: generate_paypal_link(amount=125.0) ──────────► Actions MCP returns PayPal URL
  Step 7: [LLM Response] ──────────────────────────────► Provide PayPal authorization link
```

### Expected Outcome
- Warranty covers $385 (labor + parts)
- Customer pays $125 service call fee
- PayPal link generated for payment authorization

---

## Scenario 2: HEAT + Active Warranty + Customer Declines

### Input
| Field | Value |
|-------|-------|
| Product | HEAT-001 (ProLine XE Heat Pump Water Heater) |
| Warranty | Active until 2027-06-15 (parts, labor, controller) |
| Location | Houston, TX 77001 (Serviceable) |
| Customer Messages | 1. "My water heater controller is broken" |
|                   | 2. "No, that's too expensive for me" |

### Tool Call Sequence
```
TURN 1:
  Step 1: get_plan(user_message) ──────────────────────► Planner MCP returns workflow steps
  Step 2: calculate_charges(product_id, product_type) ─► Compute MCP returns charge breakdown
  Step 3: [LLM Response] ──────────────────────────────► Present out-of-pocket costs, ASK: "Would you like to proceed?"

TURN 2:
  Step 4: log_decline_reason(reason="too expensive") ──► Actions MCP logs decline
  Step 5: [LLM Response] ──────────────────────────────► Acknowledge decline, end case
```

### Code Interpreter Usage
The LLM uses `run_calculation` to compute out-of-pocket costs:
```python
max_amount = 200.0  # Controller coverage limit
used_amount = 0.0
service_cost = 400.0  # Hypothetical controller repair
remaining_coverage = max_amount - used_amount
out_of_pocket = max(service_cost - remaining_coverage, 0)
# Result: "Remaining coverage: $200.00, Out-of-pocket cost: $200.00"
```

### Expected Outcome
- Decline reason logged: "too expensive"
- Case closed gracefully
- **NO service directory returned** (customer declined, not a territory issue)

---

## Scenario 3: HEAT + Active Warranty + Not Serviceable Territory

### Input
| Field | Value |
|-------|-------|
| Product | HEAT-001 (ProLine XE Heat Pump Water Heater) |
| Warranty | Active until 2027-06-15 (parts, labor, controller) |
| Location | Anchorage, AK 99501 (NOT Serviceable) |
| Customer Messages | 1. "My heat pump water heater stopped working" |
|                   | 2. "Yes, I'm willing to pay for service" |

### Tool Call Sequence
```
TURN 1:
  Step 1: get_plan(user_message) ──────────────────────► Planner MCP returns workflow steps
  Step 2: run_calculation(code="...warranty days...") ─► Code interpreter: "525 days remaining"
  Step 3: calculate_charges(product_id, product_type) ─► Compute MCP returns charge breakdown
  Step 4: [LLM Response] ──────────────────────────────► Present charges + warranty info, ASK: "Would you like to proceed?"

TURN 2:
  Step 5: check_territory(location) ───────────────────► Actions MCP returns serviceable=false
  Step 6: get_service_directory(product_type="HEAT") ──► Actions MCP returns 3 providers
  Step 7: [LLM Response] ──────────────────────────────► Return provider list
```

### Code Interpreter Usage
The LLM calculates remaining warranty days:
```python
from datetime import datetime
remaining_days = (datetime.strptime('2027-06-15', '%Y-%m-%d') - datetime.strptime('2026-01-06', '%Y-%m-%d')).days
# Result: "525 days remaining"
```

### Expected Outcome
- Customer agrees to pay
- Warranty has **525 days remaining** (calculated via code interpreter)
- Territory check fails (Anchorage not serviceable)
- **Service provider list returned** with 3 HEAT-certified providers

---

## Scenario 4: SALT + Active Warranty

### Input
| Field | Value |
|-------|-------|
| Product | SALT-001 (Water Softener Pro 5600) |
| Warranty | Active until 2028-03-20 (parts, labor) |
| Location | Houston, TX 77001 (Serviceable) |
| Customer Messages | 1. "My water softener isn't regenerating properly" |

### Tool Call Sequence
```
TURN 1:
  Step 1: get_plan(user_message) ──────────────────────► Planner MCP returns workflow steps
  Step 2: route_to_queue(queue="WarrantySalt") ────────► Actions MCP routes case, returns case_id
  Step 3: notify_next_steps(channel="chat") ───────────► Actions MCP sends notification
  Step 4: [LLM Response] ──────────────────────────────► Confirm case routed, provide case ID
```

### Expected Outcome
- Case routed to SALT warranty queue with High priority
- Customer notified via email: "A representative will contact you within 4-8 hours"
- **No charge calculation** (SALT warranty handled by queue)

---

## Scenario 5: SALT + No Warranty (Expired)

### Input
| Field | Value |
|-------|-------|
| Product | SALT-002 (EcoWater Systems Refiner) |
| Warranty | Expired 2024-01-15 (no coverage) |
| Location | Houston, TX 77001 (Serviceable) |
| Customer Messages | 1. "My old water softener is leaking" |

### Tool Call Sequence
```
TURN 1:
  Step 1: get_plan(user_message) ──────────────────────► Planner MCP returns workflow steps
  Step 2: get_service_directory(product_type="SALT") ──► Actions MCP returns 3 providers
  Step 3: [LLM Response] ──────────────────────────────► Return provider list with contact info
```

### Expected Outcome
- No warranty coverage (expired)
- **Service provider list returned** with 3 SALT-certified providers:
  - AquaPure Service Co. (4.8★, 5.2 miles)
  - SoftWater Solutions (4.5★, 8.7 miles)
  - ClearFlow Technicians (4.9★, 12.3 miles)
- Customer can contact providers directly for paid service

---

## Scenario 6: HEAT + No Warranty (Expired) + Customer Agrees

### Input
| Field | Value |
|-------|-------|
| Product | HEAT-002 (Voltex Hybrid Electric Heat Pump) |
| Warranty | Expired 2024-08-22 (no coverage) |
| Location | Houston, TX 77001 (Serviceable) |
| Customer Messages | 1. "My heat pump water heater from 2023 needs repair" |
|                   | 2. "Yes, I understand I'll pay the full amount" |

### Tool Call Sequence
```
TURN 1:
  Step 1: calculate_charges(product_id, product_type) ─► Compute MCP returns FULL charge breakdown
  Step 2: [LLM Response] ──────────────────────────────► Present $510 total, ASK: "Would you like to proceed?"

TURN 2:
  Step 3: check_territory(location) ───────────────────► Actions MCP returns serviceable=true
  Step 4: calculate_charges(product_id, product_type) ─► Compute MCP confirms charges
  Step 5: generate_paypal_link(amount=510.0) ──────────► Actions MCP returns PayPal URL
  Step 6: [LLM Response] ──────────────────────────────► Provide PayPal link for $510
```

### Expected Outcome
- No warranty savings (expired)
- Full charges: Labor $285 + Parts $100 + Service Fee $125 = **$510**
- PayPal link generated for full payment

---

## Decision Tree Summary

```
┌─────────────────────────────────────────────────────────────────────────┐
│                         WARRANTY ORCHESTRATOR                            │
│                     (Agentic Loop with Tool Calls)                       │
└─────────────────────────────────────────────────────────────────────────┘
                                    │
                           1. get_plan (FIRST)
                           Planner MCP returns workflow steps
                                    │
                           2. get_warranty_record (SECOND)*
                           Warranty Docs MCP returns product type,
                           coverage types, expiry date, limits
                                    │
                           3. run_calculation (THIRD)
                           Code interpreter computes days remaining,
                           coverage gaps, out-of-pocket costs
                                    │
                    ┌───────────────┴───────────────┐
                    │                               │
                 SALT                            HEAT
                    │                               │
         ┌──────────┴──────────┐            calculate_charges
         │                     │                    │
    Has Warranty?         No Warranty        ┌──────┴──────┐
         │                     │             │             │
         ▼                     ▼         Agrees?      Declines?
   route_to_queue    get_service_directory   │             │
   (WarrantySalt)    (return provider list)  ▼             ▼
         │                            check_territory  log_decline_reason
         ▼                                  │             │
   notify_next_steps               ┌────────┴────────┐    ▼
   "Rep will contact"              │                 │  END CASE
                              Serviceable?     Not Serviceable
                                   │                 │
                                   ▼                 ▼
                         generate_paypal_link  get_service_directory
                         (payment link)        (return provider list)
```

*Note: If warranty details are already provided in context, LLM may skip get_warranty_record call.

---

## Orchestrator History Flow

For each turn, the LLM's conversation history accumulates tool call results:

### Turn 1 (First Message)
```
1. [User Message] → "My heat pump water heater is making strange noises"
2. [Tool Call]    → get_plan(user_message) → Returns workflow steps from Planner MCP
3. [Tool Call]    → get_warranty_record(product_id) → Returns warranty details from Warranty Docs MCP*
4. [Tool Call]    → run_calculation(code) → Code interpreter calculates days remaining, coverage gaps
5. [Tool Call]    → calculate_charges() → Compute MCP returns charge breakdown
6. [Assistant]    → Presents charges, asks "Would you like to proceed?"
```

*Skipped if warranty details already in context.

### Turn 2 (Customer Response - Yes)
```
1. [User Message] → "Yes, I'd like to proceed"
2. [Tool Call]    → check_territory() → Actions MCP checks serviceability
3. [Tool Call]    → generate_paypal_link() OR get_service_directory()
4. [Assistant]    → Final response with payment link or provider list
```

### Turn 2 (Customer Response - No)
```
1. [User Message] → "No, that's too expensive"
2. [Tool Call]    → log_decline_reason() → Actions MCP logs the reason
3. [Assistant]    → Acknowledges decline, ends case
```

---

## Coverage Limits (from Dummy Data)

| Product | Coverage Type | Max Amount | Used Amount |
|---------|--------------|------------|-------------|
| HEAT-001 | Parts | $500.00 | $0.00 |
| HEAT-001 | Labor | $1,000.00 | $0.00 |
| HEAT-001 | Controller | $200.00 | $0.00 |
| SALT-001 | Parts | $300.00 | $0.00 |
| SALT-001 | Labor | $500.00 | $0.00 |

The code interpreter calculates remaining coverage and out-of-pocket costs when service costs exceed these limits.

---

## Test Execution

Run all scenarios automatically:
```bash
python main.py
```

The output shows:
- Each scenario with its turns
- Tool calls made by the LLM (including code interpreter)
- Bot responses with calculated values
- Summary of all passed scenarios

---

## Questions for Business Validation

1. **HEAT Decline Path**: When customer declines due to cost, should we offer the service directory as an alternative, or end the case as shown?

2. **SALT Warranty Queue**: Is 4-8 hours the correct SLA for warranty queue response?

3. **Service Call Fee**: Is $125 the correct non-refundable service call fee for HEAT products?

4. **PayPal Authorization**: For $0 charges (fully covered by warranty), should we still require PayPal authorization or skip it?

5. **Non-Serviceable Territory**: Are the third-party providers shown appropriate, or should we filter by proximity to the customer's actual location?

6. **Coverage Limits**: Are the coverage limits ($500 parts, $1000 labor, $200 controller) accurate for warranty policies?

7. **Code Interpreter Calculations**: Should the bot always display the "X days remaining" warranty information to customers?
