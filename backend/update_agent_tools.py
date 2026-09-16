import os
import httpx
import asyncio
from dotenv import load_dotenv

from app.agents.sentinel_agent import SENTINEL_SYSTEM_PROMPT

async def update_agent():
    load_dotenv()
    api_key = os.environ.get("ASSEMBLYAI_API_KEY")
    agent_id = os.environ.get("SENTINEL_AGENT_ID")
    
    if not api_key or not agent_id:
        print("Missing API key or Agent ID")
        return

    agent_config = {
        "name": "SENTINEL Safety Agent",
        "system_prompt": SENTINEL_SYSTEM_PROMPT,
        "greeting": "SENTINEL online. What's happening?",
        "voice": {"voice_id": "anna"},
        "tools": [
            {
                "name": "update_situation",
                "description": "Extract facts from the worker and update the situation. Call this immediately when you learn new facts. The tool returns your 'next_question_goal'. You MUST naturally ask the worker about the next_question_goal.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "equipment": { "type": "string" },
                        "location": { "type": "string" },
                        "machine_running": { "type": "boolean" },
                        "people_nearby": { "type": "number" },
                        "abnormal_vibration": { "type": "boolean" },
                        "vibration_increasing": { "type": "boolean" },
                        "sparks": { "type": "boolean" },
                        "smoke": { "type": "boolean" },
                        "observation": { "type": "string", "description": "Any other notable symptoms" }
                    }
                },
                "execution_mode": "interactive",
                "timeout_seconds": 15
            }
        ],
        "input": {
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
            ],
        },
        "output": {
            "format": {"encoding": "audio/pcm", "sample_rate": 24000},
        },
    }

    async with httpx.AsyncClient() as client:
        resp = await client.put(
            f"https://agents.assemblyai.com/v1/agents/{agent_id}",
            headers={"Authorization": api_key, "Content-Type": "application/json"},
            json=agent_config
        )
        if resp.status_code == 200:
            print(f"Successfully updated agent {agent_id} with tools!")
        else:
            print(f"Failed to update agent: {resp.status_code}")
            print(resp.text)

if __name__ == "__main__":
    asyncio.run(update_agent())
