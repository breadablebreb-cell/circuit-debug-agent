from PySpice.Spice.Netlist import Circuit
from PySpice.Unit import *
import random
import os
from google import genai
from google.genai import types

# ---------- Circuit simulation ----------

def build_circuit():
    circuit = Circuit('Voltage Divider Fault Demo')
    circuit.V('input', 'vin', circuit.gnd, 10@u_V)
    circuit.R(1, 'vin', 'n1', 1@u_kOhm)
    circuit.R(2, 'n1', 'n2', 2@u_kOhm)
    circuit.R(3, 'n2', circuit.gnd, 1@u_kOhm)
    return circuit

def inject_random_fault(circuit):
    faults = [
        ('R1', 'open'), ('R2', 'open'), ('R3', 'open'),
        ('R1', 'short'), ('R2', 'short'), ('R3', 'short'),
    ]
    component, fault_type = random.choice(faults)
    resistor = getattr(circuit, component)
    if fault_type == 'open':
        resistor.resistance = 1@u_GOhm
    else:
        resistor.resistance = 0.01@u_Ohm
    return component, fault_type

def measure(circuit, node_name):
    simulator = circuit.simulator(temperature=25, nominal_temperature=25)
    analysis = simulator.operating_point()
    return float(analysis[node_name][0])

# ---------- Gemini agent setup ----------

client = genai.Client(api_key=os.environ["GEMINI_API_KEY"])

measure_node_decl = {
    "name": "measure_node",
    "description": "Measure the voltage at a specific node in the circuit using a virtual probe.",
    "parameters": {
        "type": "object",
        "properties": {
            "node": {"type": "string", "description": "Node name, e.g. 'n1' or 'n2'."}
        },
        "required": ["node"]
    }
}

declare_fault_decl = {
    "name": "declare_fault",
    "description": "Declare the final diagnosis once confident about which component is faulty and how.",
    "parameters": {
        "type": "object",
        "properties": {
            "component": {"type": "string", "description": "e.g. 'R1', 'R2', 'R3'"},
            "fault_type": {"type": "string", "description": "e.g. 'open' or 'short'"},
            "reasoning": {"type": "string", "description": "Brief explanation of the evidence."}
        },
        "required": ["component", "fault_type", "reasoning"]
    }
}

tools = types.Tool(function_declarations=[measure_node_decl, declare_fault_decl])

SYSTEM_PROMPT = """You are an autonomous circuit debugging agent. You are given a voltage 
divider circuit topology:
vin (10V source) -- R1 (1kOhm) -- n1 -- R2 (2kOhm) -- n2 -- R3 (1kOhm) -- ground

In a HEALTHY circuit: n1 = 7.5V, n2 = 2.5V.

Exactly one component (R1, R2, or R3) has a fault: either 'open' (near-infinite resistance) 
or 'short' (near-zero resistance).

You may call measure_node to probe n1 or n2, one at a time.

IMPORTANT PROCESS: After your FIRST measurement, you must state a PRELIMINARY hypothesis 
in your reasoning text, even if you're not fully certain, based on that single data point 
alone. Then take a second measurement to test that hypothesis. If the second measurement 
contradicts your preliminary hypothesis, explicitly say so ("This contradicts my initial 
hypothesis because...") before revising and declaring the corrected final diagnosis. If it 
confirms your hypothesis, say so and declare with confidence.

Use the physics of the circuit (which node voltages each possible fault would produce) to 
reason at each step. Do not declare_fault without at least two measurements, since a single 
measurement can be ambiguous between multiple possible faults."""

config = types.GenerateContentConfig(
    system_instruction=SYSTEM_PROMPT,
    tools=[tools],
)

# ---------- Run one debugging session ----------

def run_agent_session(circuit, actual_fault):
    chat = client.chats.create(model="gemini-3.6-flash", config=config)
    response = chat.send_message("Begin debugging. Find the fault.")

    while True:
        function_called = False
        parts = response.candidates[0].content.parts

        for part in parts:
            if part.text:
                print(f"[Agent reasoning]: {part.text}")

            if part.function_call:
                function_called = True
                fn = part.function_call
                args = dict(fn.args)

                if fn.name == "measure_node":
                    node = args["node"]
                    value = measure(circuit, node)
                    print(f"[Tool] measure_node('{node}') -> {value:.4f} V")
                    response = chat.send_message(
                        types.Part.from_function_response(
                            name="measure_node",
                            response={"result": f"{value:.4f} V"}
                        )
                    )
                elif fn.name == "declare_fault":
                    component = args["component"]
                    fault_type = args["fault_type"]
                    reasoning = args["reasoning"]
                    print(f"\n=== AGENT DIAGNOSIS ===")
                    print(f"Component: {component}")
                    print(f"Fault type: {fault_type}")
                    print(f"Reasoning: {reasoning}")
                    print(f"\n=== ACTUAL FAULT (hidden from agent) ===")
                    print(f"Component: {actual_fault[0]}, Fault type: {actual_fault[1]}")
                    correct = (component == actual_fault[0] and fault_type == actual_fault[1])
                    print(f"CORRECT: {correct}")
                    return

        if not function_called:
            print("Agent stopped without declaring a fault.")
            return

# ---------- Main ----------

circuit = build_circuit()
actual_fault = inject_random_fault(circuit)
run_agent_session(circuit, actual_fault)
