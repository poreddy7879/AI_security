from dotenv import load_dotenv
load_dotenv()


from typing import Any
from langchain.agents.middleware import (
    AgentMiddleware, AgentState, hook_config
)
from langchain.agents.middleware import (
    PIIMiddleware
)
from langgraph.runtime import Runtime
from langchain.agents import create_agent
from langchain_core.tools import tool
from langchain_ollama import ChatOllama
from langchain_core.messages import AIMessage

class HealthcareSafetyFilter(AgentMiddleware):
    """Block non-medical or harmful requests in a healthcare context."""

    BLOCKED_TOPICS = [
        "drug synthesis", "self-harm", "suicide method",
        "weapon", "hack"
    ]

    @hook_config(can_jump_to=["end"])
    def before_agent(
        self, state: AgentState, runtime: Runtime
    ) -> dict[str, Any] | None:
        if not state["messages"]:
            return None

        first_msg = state["messages"][0]
        if first_msg.type != "human":
            return None

        content = first_msg.content.lower()
        for topic in self.BLOCKED_TOPICS:
            if topic in content:
                return {
                    "messages": [{
                        "role": "assistant",
                        "content": (
                            "I'm a healthcare assistant and can only help "
                            "with medical questions, appointments, and "
                            "health information. If you're in crisis, "
                            "please call 112 or your local emergency number."
                        )
                    }],
                    "jump_to": "end"
                }
        return None
    
class MedicalOutputValidator(AgentMiddleware):
       """Ensure all responses include appropriate medical disclaimers."""

       DISCLAIMER = (
            "\n\nThis is general health information, not medical advice. "
            "Please consult a qualified healthcare professional."
       )

       @hook_config(can_jump_to=["end"])
       def after_agent(
            self, state: AgentState, runtime: Runtime
        ) -> dict[str, Any] | None:
            if not state["messages"]:
                return None

            last_message = state["messages"][-1]
            if not isinstance(last_message, AIMessage):
                return None

            # Add disclaimer if not already present
            if "medical advice" not in last_message.content.lower():
                last_message.content += self.DISCLAIMER

            return None
        
@tool
def search_symptoms(symptoms: str) -> str:
    """Search for information about medical symptoms."""
    return (
            f"Symptom information for: {symptoms}. "
            "Please consult a doctor for diagnosis."
    )

@tool
def book_appointment(patient_name: str, date: str, doctor: str) -> str:
        """Book a medical appointment."""
        return (
            f"Appointment booked for {patient_name} "
            f"with Dr. {doctor} on {date}"
    )

@tool
def get_medication_info(medication: str) -> str:
        """Get information about a medication."""
        return (
            f"General info about {medication}. "
            "Always follow your doctor's prescription."
    )

local_llm = ChatOllama(
        model="llama3.1",      # must match the name you used with `ollama pull`
        temperature=0.2,
        base_url="http://localhost:11434",  # default Ollama server address
    )

healthcare_bot = create_agent(
        model=local_llm,
        tools=[search_symptoms, book_appointment, get_medication_info],
        middleware=[
            # Guardrail 1: Block harmful/off-topic requests
            HealthcareSafetyFilter(),

            # Guardrail 2: Redact patient PII from inputs AND outputs
            PIIMiddleware(
                "email",
                strategy="redact",
                apply_to_input=True,
                apply_to_output=True,
            ),
            PIIMiddleware(
                "credit_card",
                strategy="mask",
                apply_to_input=True,
                apply_to_output=True,
            ),

            # Guardrail 3: Add medical disclaimer to all outputs
            MedicalOutputValidator(),
        ],
        system_prompt=(
            "You are a helpful healthcare assistant. "
            "You can search for symptoms, medication information, "
            "and help book appointments. Always be empathetic and "
            "remind users to consult a doctor for diagnosis."
        ),
    )

print("Healthcare chatbot with full guardrail stack created!")
