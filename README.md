# Autonomous Circuit Debugging Agent

An agentic AI system that diagnoses faults in an electronic circuit through iterative,
tool-based measurement — the same way a human debugging a circuit would probe one test
point, reason about the result, and decide what to check next.

Built for the Tech Zephyr 4.0 Agentic AI Hackathon (IIT Bhubaneswar).

## Why this needs to be agentic

A single LLM call cannot diagnose a circuit fault, because the diagnostic information is
revealed incrementally: an initial voltage reading is often ambiguous between multiple
possible faults, and only becomes conclusive once a *second, strategically chosen*
measurement is taken. The system must:

- **Observe** partial evidence (one voltage reading)
- **Decide** dynamically which node to probe next, based on circuit physics
- **Act** by calling a measurement tool
- **Evaluate** whether the new evidence confirms or contradicts its working hypothesis
- **Adapt** by revising its diagnosis when contradicted

This loop cannot be short-circuited into a single prompt-response — the agent's second
action is only knowable after seeing the first result.

## How it works

1. A voltage-divider circuit (`vin -- R1 -- n1 -- R2 -- n2 -- R3 -- gnd`) is simulated in
   SPICE via PySpice/ngspice.
2. One of six possible faults (R1/R2/R3, each either open or shorted) is injected at
   random. The agent has no visibility into which fault was injected.
3. The agent (Gemini) is given the circuit topology and healthy-state voltages, and two
   tools:
   - `measure_node(node)` — returns the voltage at a given node
   - `declare_fault(component, fault_type, reasoning)` — submits a final diagnosis
4. The agent must take at least two measurements before declaring, since a single
   measurement can be ambiguous between multiple fault types. After its first
   measurement it states a preliminary hypothesis, then confirms or revises it based
   on the second measurement.
5. The declared diagnosis is checked against the actual (hidden) injected fault.

## Architecture

See `docs/architecture.md` for the full diagram. Summary:
Agent controller (Gemini)
├─ measure_node tool → Simulation environment (PySpice/ngspice) → loops result back to agent
└─ declare_fault tool → Evaluation (compare vs hidden ground truth) → Output


## Setup

### Prerequisites
- Python 3.10+
- ngspice (system package, not installed via pip)
  - Arch Linux: `sudo pacman -S ngspice`
  - Debian/Ubuntu: `sudo apt install ngspice`
  - macOS: `brew install ngspice`
- A Gemini API key from [Google AI Studio](https://aistudio.google.com/apikey)

### Installation

```bash
git clone https://github.com/breadablebreb-cell/circuit-debug-agent.git
cd circuit-debug-agent
pip install -r requirements.txt --break-system-packages
```

### Environment configuration

Set your Gemini API key as an environment variable.

**bash/zsh:**
```bash
export GEMINI_API_KEY="your-key-here"
```

**fish:**
```fish
set -x GEMINI_API_KEY "your-key-here"
```

### Running

```bash
python3 agent.py
```

Each run injects a random fault and prints the agent's full reasoning trace, including
any preliminary hypothesis and correction, followed by the final diagnosis and whether
it matched the actual injected fault.

## Example output

See `logs/sample_runs.txt` for captured example sessions, including a run where the
agent's initial hypothesis is contradicted by a second measurement and it explicitly
revises its diagnosis.


## Limitations / future work

- Currently simulation-only; a hardware-in-the-loop version (real ESP32 + multiplexed
  probes on a physical breadboard circuit) is a planned extension.
- Circuit topology is fixed to a single voltage divider; a larger circuit with more
  measurable nodes would give the agent richer strategic choices.
- No persistent memory across sessions — each debugging run starts fresh.
