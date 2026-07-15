"""
Streamlit UI wrapper for the healthcare chatbot agent.

Run with:
    streamlit run app.py

Expects `healthcare_bot.py` (your agent definition) to be in the same
directory, and a valid OPENAI_API_KEY available via .env or the environment
(healthcare_bot.py already calls load_dotenv() for you).
"""

import streamlit as st

# --- Import your agent -------------------------------------------------
# healthcare_bot.py defines a module-level variable also named
# `healthcare_bot` (the compiled agent graph). We import the module and
# pull that variable out explicitly to avoid name confusion.
try:
    import healthcare_bot as bot_module
    agent = bot_module.healthcare_bot
    IMPORT_ERROR = None
except Exception as e:  # noqa: BLE001 - surface any import/config error in the UI
    agent = None
    IMPORT_ERROR = str(e)

# --- Page config ---------------------------------------------------------
st.set_page_config(
    page_title="Healthcare Assistant",
    page_icon="🩺",
    layout="centered",
)

# Text that HealthcareSafetyFilter returns when it blocks a request.
# Used to visually flag blocked turns differently in the UI.
SAFETY_BLOCK_MARKER = "I'm a healthcare assistant and can only help"

# --- Session state ---------------------------------------------------------
if "messages" not in st.session_state:
    # Each item: {"role": "user"|"assistant", "content": str, "blocked": bool}
    st.session_state.messages = []

# --- Sidebar ---------------------------------------------------------------
with st.sidebar:
    st.header("🩺 Healthcare Assistant")
    st.caption(
        "A guarded medical information assistant. "
        "Not a substitute for professional medical advice."
    )

    st.subheader("Active guardrails")
    st.markdown(
        "- 🚫 **Safety filter** — blocks off-topic / harmful requests\n"
        "- 🔒 **PII redaction** — emails and credit card numbers are "
        "redacted/masked before reaching the model\n"
        "- 📋 **Disclaimer injection** — every response is checked to "
        "include a medical disclaimer"
    )

    st.divider()

    if st.button("🗑️ New conversation", use_container_width=True):
        st.session_state.messages = []
        st.rerun()

    st.divider()
    st.caption(
        "If you are experiencing a medical emergency or crisis, "
        "call 112 (or your local emergency number) immediately."
    )

# --- Header ---------------------------------------------------------------
st.title("Healthcare Assistant")
st.caption("Ask about symptoms, medications, or book an appointment.")

if IMPORT_ERROR:
    st.error(
        "Couldn't load the chatbot agent. Make sure `healthcare_bot.py` is "
        "in the same folder as this app, dependencies are installed, and "
        "your OPENAI_API_KEY is set.\n\n"
        f"Details: {IMPORT_ERROR}"
    )
    st.stop()

# --- Render existing chat history ------------------------------------------
for msg in st.session_state.messages:
    avatar = "🩺" if msg["role"] == "assistant" else None
    with st.chat_message(msg["role"], avatar=avatar):
        if msg["role"] == "assistant" and msg.get("blocked"):
            st.warning(msg["content"])
        else:
            st.markdown(msg["content"])

# --- Chat input --------------------------------------------------------
user_input = st.chat_input("Type your health-related question...")

if user_input:
    # Build the full message history for the agent: prior (already-redacted)
    # turns from session state, plus the new raw input.
    agent_input = {
        "messages": [
            {"role": m["role"], "content": m["content"]}
            for m in st.session_state.messages
        ]
        + [{"role": "user", "content": user_input}]
    }

    with st.spinner("Thinking..."):
        reply_text = None
        try:
            result = agent.invoke(agent_input)
            response_messages = result.get("messages", [])
        except Exception as e:  # noqa: BLE001 - surface runtime errors in the UI
            response_messages = []
            reply_text = f"Something went wrong while processing your request. ({e})"

    # Pull the redacted version of what we just sent, straight from the
    # agent's own state, instead of trusting the raw text we typed.
    redacted_user_text = user_input
    for m in reversed(response_messages):
        if getattr(m, "type", None) == "human":
            redacted_user_text = m.content
            break

    st.session_state.messages.append(
        {"role": "user", "content": redacted_user_text}
    )
    with st.chat_message("user"):
        st.markdown(redacted_user_text)

    if response_messages:
        reply_text = response_messages[-1].content
    elif not reply_text:
        reply_text = "Sorry, I couldn't generate a response."

    is_blocked = SAFETY_BLOCK_MARKER in reply_text
    with st.chat_message("assistant", avatar="🩺"):
        if is_blocked:
            st.warning(reply_text)
        else:
            st.markdown(reply_text)

    st.session_state.messages.append(
        {"role": "assistant", "content": reply_text, "blocked": is_blocked}
    )
