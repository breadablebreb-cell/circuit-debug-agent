# Architecture

## Overview

The system consists of five components in a feedback loop: an agent controller that
reasons and decides, two tools it can call, a simulation environment that stands in for
real circuit hardware, and an evaluation step that checks the agent's final answer.

Agent controller (Gemini 3.6 Flash)
|
|--- calls --> measure_node tool --> Simulation environment (PySpice/ngspice)
| |
|<---------- voltage reading returns ------|
|
|--- calls --> declare_fault tool --> Evaluation (compare vs hidden ground truth) --> Output


## Components

### Agent controller
The reasoning core of the system (Gemini 3.6 Flash). Given the circuit topology and
known healthy-state voltages, it decides which action to take next: measure another
node, or declare a final diagnosis. This is the only component making decisions — every
other part is a passive tool or evaluator.

### Tools

**`measure_node(node)`** — the agent's only way to gather evidence. Takes a node name
(e.g. `n1`, `n2`) and returns the simulated voltage at that node. The agent cannot see
any other part of the circuit's state; each call reveals exactly one data point, forcing
genuinely sequential, evidence-driven decision-making.

**`declare_fault(component, fault_type, reasoning)`** — the agent's terminal action.
Submits a final diagnosis (which component, what kind of fault) along with its
reasoning. The agent is instructed not to call this before taking at least two
measurements, since a single measurement is often ambiguous between multiple possible
faults.

### Simulation environment
A SPICE circuit (voltage divider: `vin -- R1 -- n1 -- R2 -- n2 -- R3 -- gnd`) run via
PySpice/ngspice. Before each session, exactly one component is given a random fault
(open: resistance set near-infinite; short: resistance set near-zero). This fault is
hidden from the agent — it can only be inferred through measurements.

### Evaluation
After the agent declares a diagnosis, it's checked against the actual injected fault
(known to the harness, never revealed to the agent during the session). This produces a
simple correct/incorrect verdict alongside the agent's full reasoning trace.

## Memory / state

State is handled implicitly through the conversation history maintained in the chat
session — each tool call and its result are appended to the context, so the agent's
next decision is always informed by everything it has measured so far in that session.
There is no persistence across separate debugging sessions; each run starts fresh with
a newly injected fault.

## Failure handling / adaptation

The agent is explicitly prompted to state a preliminary hypothesis after its first
measurement, then test that hypothesis with a second measurement. When the second
reading contradicts the hypothesis, the agent is required to state the contradiction
explicitly and revise its diagnosis before declaring a final answer. This produces
visible, auditable self-correction rather than silent guessing — see
`logs/sample_runs.txt` for a captured example where the agent's initial hypothesis
("R2 open") is contradicted and revised to the correct answer ("R1 short").

## Why a single LLM call can't replace this loop

The second measurement to take is only knowable after seeing the result of the first —
the diagnostic value of probing `n2` depends entirely on what `n1` read. This is
irreducibly sequential: no fixed prompt or one-shot generation can substitute for the
agent's step-by-step reasoning under partial information.


<img width="2720" height="1960" alt="circuit_debug_agent_architecture" src="https://github.com/user-attachments/assets/70279073-dcbe-47c8-8f0e-53833c2e106c" />

