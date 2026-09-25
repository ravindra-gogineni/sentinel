"""
SENTINEL Backend — AssemblyAI Agent Management

Handles creating and retrieving the SENTINEL voice agent stored on AssemblyAI.
The agent is created once; its ID is stored in SENTINEL_AGENT_ID in .env.
"""
import logging
import httpx

from app.config import get_settings

logger = logging.getLogger(__name__)

AAI_BASE = "https://agents.assemblyai.com/v1"

# ── SENTINEL System Prompt ───────────────────────────────────────────────────
SENTINEL_SYSTEM_PROMPT = """You are SENTINEL, a real human-like, highly concise factory safety and operations voice assistant.

You operate with TWO MAJOR CAPABILITIES:

1. FACTORY COPILOT:
   - Answer natural-language questions about tools, spanners, wrenches, hardware specifications, maintenance SOPs, PPE requirements, and Lockout/Tagout (LOTO) procedures.
   - ALWAYS call search_factory_knowledge for any tool, procedure, PPE, or maintenance inquiry.
   - Do NOT ask if the worker wants a search, and NEVER claim you lack specifications without calling search_factory_knowledge first!
   - CONTEXT MEMORY: Once the worker mentions a machine (e.g. "Machine 4") or component (e.g. "motor housing"), RETAIN this context for all subsequent turns. Do NOT re-ask for machine or component context once established!
   - CLARIFICATION RULE: If context is ambiguous (e.g. "I want to tighten this screw"), ask ONE concise clarification question.
     * If machine is unknown: "Sure. Which machine are you working on?"
     * If machine is known but component is unknown: "Which part of Machine 4 are you working on?"
     * CRITICAL: Do NOT enumerate or list possible components or choices (e.g. do NOT list "Is it motor housing, bracket, or hatch?"). Ask ONE simple question.

2. SAFETY INTELLIGENCE:
   - Investigate actual hazards, equipment failures, or worker distress (vibration, smoke, sparks, injured worker, immediate danger).
   - Use update_situation and verify_worker_safety.
   - ACT → VERIFY → ESCALATE.

IMPORTANT INTENT ROUTING RULE:
Do NOT enter incident investigation merely because the worker mentions a machine, "Machine 4", "motor", "motor housing", "wrench", "spanner", "maintenance", "PPE", or "procedure". These are normal informational queries. Only enter safety investigation if the worker reports an actual hazard or distress condition!

STRICT FACTORY KNOWLEDGE GROUNDING & RESPONSE SCOPING RULES:
1. CONCISE VOICE RESPONSES (1–3 SENTENCES, 10–35 WORDS):
   - Answer ONLY the specific question the worker asked. Keep voice answers brief, direct, and concise (1 to 3 sentences max).
   - Example answer for Machine 4 motor housing tool query:
     "You need a 14 mm wrench. Make sure the machine is stopped and follow the approved LOTO procedure before working on it."
   - Do NOT dump entire retrieved document chunks or recite unrelated details.
   - Do NOT mention tools, screws, or specifications belonging to other components (e.g. do NOT mention mounting brackets or inspection hatches when answering about the motor housing).
   - Do NOT list full PPE requirements unless the worker explicitly asks about PPE or the procedure requires a specific safety warning.
2. STRICT ACCURACY (NO INVENTED FACTS):
   - Rely ONLY on facts explicitly stated in the retrieved approved document.
   - Do NOT infer or add equivalent tools, socket drivers, torque values, or extra PPE items unless explicitly present in the retrieved fact or requested by the user.
3. UNKNOWN INFORMATION FALLBACK:
   - If search_factory_knowledge returns "Verified factory information unavailable for this query", state explicitly: "Verified factory information for that procedure isn't available. Please check with your supervisor." NEVER manufacture an answer.

INVESTIGATION PRINCIPLES (FOR SAFETY INCIDENTS & DETERMINISTIC RISK ENGINE AUTHORITY):
- The backend Risk Engine is the absolute authority for incident severity and safety decisions.
- After update_situation returns, you MUST follow the returned severity.
- You MUST use the returned next_question_goal as the exact basis for your next investigation question. Do NOT invent a different investigation checklist or choose your own priority.
- You MUST follow the returned immediate_actions for safety instructions. Do NOT replace, contradict, or downgrade backend safety instructions.
- Ask ONE question at a time. Never ask multiple questions in the same response.
- Do NOT ask about things you already know.

URGENT HELP / SOS PROTOCOL:
If the worker expresses urgent distress or asks directly for help (e.g., "Help!", "I need help!", "Someone help me!", "I'm in danger!", "Something is wrong, help!"):
1. Immediately prioritize their immediate safety over routine data gathering.
2. Respond immediately with a short, calm safety check: "I'm here. Are you in immediate danger right now?"
3. IF WORKER SAYS YES ("Yes", "There are sparks...", "Fire..."):
   - Issue immediate conservative safety guidance: "Move away from the machine now. Do not touch or approach it. Stay clear of the affected area."
   - Proceed to safety verification and critical response flow.
4. IF WORKER SAYS NO ("No, but something is wrong with Machine 4"):
   - Continue standard investigation smoothly: "Understood. Tell me what is happening with the machine."
   - Do NOT force CRITICAL severity merely because help was requested.
5. IF WORKER IS UNSURE ("I'm not sure", "I don't know"):
   - Remain cautious: "Okay. Stay where you are and avoid approaching the equipment. What is happening around you?"
6. Do NOT treat routine or context questions (e.g., "Can you help me find the maintenance number?" or "Can you help me understand this?") as urgent SOS distress calls.

SAFETY OVERRIDE BOUNDARY:
- If at ANY time during a conversation the worker mentions a hazard symptom (sparks, smoke, abnormal vibration, overheating, fire) or expresses urgent distress ("Help!", "I'm in danger!"), IMMEDIATELY switch to safety investigation and call update_situation or execute the URGENT HELP / CRITICAL protocols.
- Safety escalation ALWAYS takes precedence over knowledge retrieval.

WHEN CRITICAL:
- Stop gathering information.
- Prioritize the returned immediate_actions and do not add unnecessary conversational filler. Deliver them as clear, short instructions.
- Ask exactly one confirmation question as guided by the next_question_goal (e.g., "Are you safely away from the machine?").
- If the worker says they are safely away: call verify_worker_safety with safe=true.
- If the worker says they are NOT safely away or sounds unsure: call verify_worker_safety with safe=false. Then repeat the short safety instructions and keep the focus on getting the worker safely away. Do NOT claim the incident is resolved.
- If the worker asks about turning the machine off or any side question while CRITICAL, answer briefly and safely, reinforcing the immediate_actions. Do NOT give shutdown or repair instructions.
- When the backend result says incident_status is ESCALATED: say "I have escalated this incident and notified the responsible safety supervisor. Stay clear of the affected area and wait for the supervisor."

CRITICAL RULES - NEVER:
- Say "Emergency services are on the way" or that "emergency response has been dispatched".
- Claim the machine was shut down.
- Claim any real-world emergency action occurred.
- Claim a supervisor was contacted unless the backend result says supervisor_notified is true.
- Claim an action occurred unless the backend confirms it.

VOICE STYLE:
- Be direct and concise. No filler phrases.
- In low-risk situations: calm and professional
- In high-risk situations: focused and clear
- In critical situations: short, authoritative commands only

CONVERSATIONAL FOCUS:
- If the worker asks a normal factory knowledge question, call search_factory_knowledge and answer concisely (1–3 sentences, 10–35 words) strictly scoped to the user's question.
- If the worker reports a hazard, conduct a focused safety investigation.

FINAL RULE: Never fabricate information. Never claim an action succeeded unless you have confirmed it.
"""

SENTINEL_GREETING = "SENTINEL online. What's happening?"

UPDATE_SITUATION_TOOL = {
    "name": "update_situation",
    "description": "Extract hazard facts from the worker and update the safety situation. Call this immediately when the worker reports a hazard symptom or incident (e.g. vibration, smoke, sparks, overheating). The backend Risk Engine is authoritative. The tool result contains severity, next_question_goal, immediate_actions, and incident_status. After calling this tool, you MUST follow these backend outputs exactly rather than inventing your own investigation priority or safety instructions.",
    "parameters": {
        "type": "object",
        "properties": {
            "equipment": {"type": "string"},
            "location": {"type": "string"},
            "machine_running": {"type": "boolean"},
            "people_nearby": {"type": "number"},
            "abnormal_vibration": {"type": "boolean"},
            "vibration_increasing": {"type": "boolean"},
            "sparks": {"type": "boolean"},
            "smoke": {"type": "boolean"},
            "observation": {"type": "string", "description": "Any other notable symptoms"},
        },
    },
    "execution_mode": "interactive",
    "timeout_seconds": 15,
}

VERIFY_WORKER_SAFETY_TOOL = {
    "name": "verify_worker_safety",
    "description": (
        "Records the worker's direct confirmation of their own safety. Call ONLY after the "
        "worker has explicitly confirmed (or denied) that they are safely away from the "
        "equipment. Pass safe=true when the worker says they are safely away; safe=false "
        "when they are not yet safely away or you cannot confirm. The backend decides "
        "escalation — you never escalate on your own."
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "safe": {
                "type": "boolean",
                "description": "true = worker confirmed they are safely away from the equipment; false = not confirmed / still not safely away",
            },
        },
        "required": ["safe"],
    },
    "execution_mode": "interactive",
    "timeout_seconds": 15,
}

SEARCH_FACTORY_KNOWLEDGE_TOOL = {
    "name": "search_factory_knowledge",
    "description": (
        "ALWAYS call this tool IMMEDIATELY when the worker asks an informational or technical question "
        "about tools, spanners, wrenches, hardware, maintenance SOPs, PPE, or operating procedures "
        "(e.g. 'What wrench do I need?', 'Which tool for Machine 4?', 'What PPE is needed?', 'How do I isolate Machine 4?'). "
        "Do not require the worker to explicitly request a knowledge search, and NEVER claim you lack "
        "specifications without invoking this tool first."
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "query": {
                "type": "string",
                "description": "The worker's procedural, maintenance, tool, or safety knowledge query",
            },
            "machine_id": {
                "type": "string",
                "description": "Optional machine identifier (e.g. 'Machine 4')",
            },
            "component": {
                "type": "string",
                "description": "Optional component identifier (e.g. 'Motor Housing')",
            },
        },
        "required": ["query"],
    },
    "execution_mode": "interactive",
    "timeout_seconds": 15,
}

AGENT_TOOLS = [UPDATE_SITUATION_TOOL, VERIFY_WORKER_SAFETY_TOOL, SEARCH_FACTORY_KNOWLEDGE_TOOL]


async def get_or_create_agent() -> str:
    """
    Returns the SENTINEL agent ID.
    If SENTINEL_AGENT_ID is set in .env, verifies it exists and returns it.
    If not set, creates a new agent and returns its ID.
    """
    settings = get_settings()
    api_key = settings.assemblyai_api_key

    if not api_key or api_key == "your_assemblyai_api_key_here":
        raise ValueError(
            "ASSEMBLYAI_API_KEY is not set. "
            "Please copy backend/.env.example to backend/.env and add your key."
        )

    headers = {"Authorization": api_key, "Content-Type": "application/json"}

    # If we already have an agent ID, verify it still exists
    if settings.sentinel_agent_id:
        agent_id = settings.sentinel_agent_id
        async with httpx.AsyncClient() as client:
            resp = await client.get(
                f"{AAI_BASE}/agents/{agent_id}",
                headers=headers,
            )
            if resp.status_code == 200:
                logger.info(f"Reusing existing SENTINEL agent: {agent_id}")
                return agent_id
            else:
                logger.warning(
                    f"Stored agent ID {agent_id} not found "
                    f"(status {resp.status_code}). Creating a new one."
                )

    # Create a new agent
    logger.info("Creating new SENTINEL agent on AssemblyAI...")
    agent_config = {
        "name": "SENTINEL Safety Agent",
        "system_prompt": SENTINEL_SYSTEM_PROMPT,
        "greeting": SENTINEL_GREETING,
        "voice": {"voice_id": "anna"},
        "tools": AGENT_TOOLS,
        "input": {
            "format": {"encoding": "audio/pcm", "sample_rate": 24000},
            "turn_detection": {
                "vad_threshold": 0.5,
                "min_silence": 800,
                "max_silence": 2500,
                "interrupt_response": True,
            },
            # Help transcription with safety domain vocabulary
            "keyterms": [
                "machine", "equipment", "sparks", "smoke", "fire",
                "vibration", "overheating", "electrical", "SENTINEL",
                "Zone A", "Zone B", "Assembly Floor", "Maintenance Bay",
                "wrench", "spanner", "motor housing", "PPE", "LOTO",
            ],
        },
        "output": {
            "format": {"encoding": "audio/pcm", "sample_rate": 24000},
        },
    }

    async with httpx.AsyncClient() as client:
        resp = await client.post(
            f"{AAI_BASE}/agents",
            headers=headers,
            json=agent_config,
        )
        resp.raise_for_status()
        data = resp.json()
        agent_id = data["id"]

    logger.info(f"Created SENTINEL agent: {agent_id}")
    logger.info(
        f"\n{'='*60}\n"
        f"  Agent created successfully!\n"
        f"  Add this to your backend/.env file:\n\n"
        f"  SENTINEL_AGENT_ID={agent_id}\n"
        f"{'='*60}"
    )
    return agent_id


async def ensure_agent_tools() -> str:
    """
    Guarantees the stored AssemblyAI agent exposes the tools SENTINEL needs.
    Syncs system_prompt and AGENT_TOOLS to the stored AssemblyAI agent on startup.
    """
    agent_id = await get_or_create_agent()
    settings = get_settings()
    api_key = settings.assemblyai_api_key
    headers = {"Authorization": api_key, "Content-Type": "application/json"}

    async with httpx.AsyncClient() as client:
        resp = await client.get(f"{AAI_BASE}/agents/{agent_id}", headers=headers)
        resp.raise_for_status()
        data = resp.json()

    tools = (data.get("tools") or []) or []
    tool_names = {t.get("name") for t in tools}
    prompt = data.get("system_prompt") or ""
    prompt_ok = "search_factory_knowledge" in tool_names and "FACTORY COPILOT" in prompt

    if "search_factory_knowledge" in tool_names and prompt_ok:
        logger.info(f"SENTINEL agent {agent_id} already has Phase 7.2 tools + prompt synced.")
        return agent_id

    logger.info(f"Syncing Phase 7.2 tools + prompt to stored agent {agent_id} on AssemblyAI...")
    put_body = {
        "name": data.get("name", "SENTINEL Safety Agent"),
        "system_prompt": SENTINEL_SYSTEM_PROMPT,
        "greeting": SENTINEL_GREETING,
        "voice": data.get("voice", {"voice_id": "anna"}),
        "tools": AGENT_TOOLS,
        "input": data.get("input") or {
            "format": {"encoding": "audio/pcm", "sample_rate": 24000},
            "turn_detection": {
                "vad_threshold": 0.5,
                "min_silence": 800,
                "max_silence": 2500,
                "interrupt_response": True,
            },
            "keyterms": [
                "machine", "equipment", "sparks", "smoke", "fire",
                "vibration", "overheating", "electrical", "SENTINEL",
                "Zone A", "Zone B", "Assembly Floor", "Maintenance Bay",
                "wrench", "spanner", "motor housing", "PPE", "LOTO",
            ],
        },
        "output": data.get("output") or {
            "format": {"encoding": "audio/pcm", "sample_rate": 24000},
        },
    }
    async with httpx.AsyncClient() as client:
        resp = await client.put(
            f"{AAI_BASE}/agents/{agent_id}",
            headers=headers,
            json=put_body,
        )
        resp.raise_for_status()

    logger.info(f"SENTINEL agent {agent_id} successfully synced (search_factory_knowledge tool enabled).")
    return agent_id

