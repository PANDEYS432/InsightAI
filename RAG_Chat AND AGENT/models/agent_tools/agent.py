"""
models/agent_tools/agent.py
JSON-mode agentic loop for Sarvam (and Ollama fallback).
"""

import json
import logging
import os
import re
import time
from typing import Any, Dict, List, Optional

from models.agent_tools.api_client import AccidentAPIClient

logger = logging.getLogger(__name__)

# ── Config ────────────────────────────────────────────────────────────────────
AGENT_BACKEND  = os.getenv("AGENT_BACKEND", "sarvam").lower()
SARVAM_API_KEY = os.getenv("SARVAM_API_KEY", "")
SARVAM_MODEL   = os.getenv("SARVAM_AGENT_MODEL", "sarvam-m")
OLLAMA_API_URL = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434") + "/api/chat"
OLLAMA_MODEL   = os.getenv("OLLAMA_MODEL", "llama3.2")
MAX_RETRIES    = 3
TIMEOUT        = 120
MAX_TOOL_ROUNDS = 8

# ── Tool catalogue ────────────────────────────────────────────────────────────
TOOL_CATALOGUE = """
TOOLS YOU MUST USE (call by name exactly as shown):

- list_cities                      args: {} or {"dataset": "weather_2020"}
- list_datasets                    args: {}
- query_road_features              args: {"year": 2019}  optional: city, sort_by, top_n
- query_road_features_summary      args: {"year": 2019}
- query_junctions                  args: {"year": 2019}  optional: city, sort_by, top_n
- query_junctions_summary          args: {"year": 2019}
- query_traffic_control            args: {"year": 2019}  optional: city, sort_by, top_n
- query_traffic_control_summary    args: {"year": 2019}
- query_traffic_violations         args: {"year": 2019}  optional: city, sort_by, top_n
- query_traffic_violations_summary args: {"year": 2019}
- query_weather                    args: {"year": 2020}  optional: city, sort_by, top_n
- query_weather_summary            args: {"year": 2020}
- query_vehicles                   args: {}              optional: city, sort_by, top_n
- query_vehicles_summary           args: {}
- query_road_defects               args: {}              optional: state, year(2006-2016), top_n
- query_road_defects_summary       args: {}
- compare_years                    args: {"category": "weather", "years": [2019, 2020]}  optional: city
  category options: road_features | junctions | traffic_control | traffic_violations | weather | vehicles
"""

# ── System prompt ─────────────────────────────────────────────────────────────
SYSTEM_PROMPT = f"""You are a road accident data analyst for India. You answer questions using REAL DATA from tools.

{TOOL_CATALOGUE}

OUTPUT FORMAT — respond with ONLY a single JSON object, nothing else:

Step 1 — call a tool (MANDATORY for every data question):
{{"action": "call_tool", "tool": "query_junctions", "args": {{"year": 2019}}}}

Step 2 — after receiving tool results, give the final answer:
{{"action": "final_answer", "text": "Based on data: Delhi had 120 accidents..."}}

CRITICAL RULES:
- You MUST call at least one tool before giving a final_answer.
- NEVER skip tool calls. NEVER invent numbers.
- For "major causes" questions: call query_traffic_violations, query_junctions, query_weather, query_road_features.
- For comparisons across years: use compare_years tool.
- For city-specific: pass "city" arg.
- Your response must be a single JSON object. No text before or after. No markdown.
- Do NOT say "please wait" or "I'm analyzing". Just return the JSON action.
"""

# ── Per-question system prompt (injected into user turn for stronger enforcement) ──
ENFORCE_MSG = """REMEMBER: Respond with ONLY a JSON object.
Either: {"action":"call_tool","tool":"<name>","args":{...}}
Or after seeing tool results: {"action":"final_answer","text":"..."}
DO NOT skip tool calls."""


class AccidentAgent:
    def __init__(
        self,
        backend: str = AGENT_BACKEND,
        data_api_base: str = "http://localhost:8001",
        sarvam_api_key: str = SARVAM_API_KEY,
        ollama_model: str = OLLAMA_MODEL,
    ):
        self.backend        = backend
        self.api_client     = AccidentAPIClient(data_api_base)
        self.sarvam_api_key = sarvam_api_key
        self.ollama_model   = ollama_model
        self._history: List[Dict] = []

    def chat(self, user_message: str) -> str:
        self._history.append({"role": "user", "content": user_message})
        try:
            reply = self._run_json_loop(user_message)
        except Exception as exc:
            logger.error("AccidentAgent error: %s", exc)
            reply = f"Error running agent: {exc}"
        self._history.append({"role": "assistant", "content": reply})
        return reply

    def reset(self):
        self._history = []

    # ── Agentic loop ──────────────────────────────────────────────────────────

    def _run_json_loop(self, user_question: str) -> str:
        # Build conversation context (last 6 turns to avoid token bloat)
        recent = self._history[-6:] if len(self._history) > 6 else self._history
        history_text = ""
        for m in recent[:-1]:  # exclude the current question
            role = "User" if m["role"] == "user" else "Assistant"
            history_text += f"{role}: {m['content']}\n"

        tool_results: List[str] = []
        tools_called = 0

        for round_num in range(MAX_TOOL_ROUNDS):
            # Build the user prompt for this round
            parts = []
            if history_text:
                parts.append(f"Conversation so far:\n{history_text}")
            parts.append(f"Current question: {user_question}")
            if tool_results:
                parts.append("Tool results:\n" + "\n\n".join(tool_results))
            if tools_called == 0:
                parts.append(
                    "\nYou MUST call a tool now. "
                    "Return: {\"action\":\"call_tool\",\"tool\":\"<name>\",\"args\":{...}}"
                )
            else:
                parts.append(
                    "\nYou now have data. Either call another tool or give final_answer."
                )
            parts.append(ENFORCE_MSG)

            prompt = "\n\n".join(parts)

            raw = self._call_llm(prompt)
            if raw is None:
                return "Error: Could not reach the language model."

            # Strip <think>...</think> blocks (Sarvam-M reasoning traces)
            raw_clean = re.sub(r"<think>.*?</think>", "", raw, flags=re.DOTALL).strip()

            logger.info("[Agent] Round %d | tools_called=%d | response: %s",
                        round_num + 1, tools_called, raw_clean[:300])

            parsed = self._extract_json(raw_clean)
            if parsed is None:
                logger.warning("[Agent] Could not parse JSON from: %s", raw_clean[:200])
                tool_results.append(
                    "ERROR: Your last response was not valid JSON. "
                    "You MUST respond with a JSON object only."
                )
                continue

            action = parsed.get("action", "")

            # ── Final answer ──────────────────────────────────────────────
            if action == "final_answer":
                if tools_called == 0:
                    # Force it to call a tool first
                    tool_results.append(
                        "ERROR: You gave a final_answer without calling any tools. "
                        "You MUST call at least one tool first. "
                        "Return a call_tool action now."
                    )
                    continue
                answer = parsed.get("text", "").strip()
                return answer or "No answer generated."

            # ── Tool call ─────────────────────────────────────────────────
            if action == "call_tool":
                tool_name = parsed.get("tool", "")
                tool_args = parsed.get("args", {})
                if isinstance(tool_args, str):
                    try:
                        tool_args = json.loads(tool_args)
                    except Exception:
                        tool_args = {}

                logger.info("[Agent] Calling tool: %s(%s)", tool_name, tool_args)
                result = self.api_client.dispatch(tool_name, tool_args)
                tools_called += 1

                result_str = json.dumps(result, default=str)
                # Truncate very large results to avoid token overflow
                if len(result_str) > 4000:
                    result_str = result_str[:4000] + "... (truncated)"

                tool_results.append(
                    f"Tool '{tool_name}' result:\n{result_str}"
                )
                continue

            # ── Unknown ───────────────────────────────────────────────────
            tool_results.append(
                f"ERROR: Unknown action '{action}'. "
                "Use 'call_tool' or 'final_answer'."
            )

        return (
            "I reached the maximum reasoning steps. "
            "Please ask a more specific question."
        )

    # ── LLM callers ───────────────────────────────────────────────────────────

    def _call_llm(self, user_prompt: str) -> Optional[str]:
        if self.backend == "sarvam":
            return self._call_sarvam(user_prompt)
        return self._call_ollama(user_prompt)

    def _call_sarvam(self, user_prompt: str) -> Optional[str]:
        try:
            from sarvamai import SarvamAI
        except ImportError:
            logger.error("sarvamai not installed")
            return None

        if not self.sarvam_api_key:
            logger.error("SARVAM_API_KEY not set")
            return None

        client = SarvamAI(api_subscription_key=self.sarvam_api_key)

        for attempt in range(1, MAX_RETRIES + 1):
            try:
                response = client.chat.completions(
                    model=SARVAM_MODEL,
                    messages=[
                        {"role": "system", "content": SYSTEM_PROMPT},
                        {"role": "user",   "content": user_prompt},
                    ],
                    temperature=0.1,
                    max_tokens=1024,
                )
                return response.choices[0].message.content or ""
            except Exception as exc:
                logger.error("[Sarvam] attempt %d error: %s", attempt, exc)
                if attempt < MAX_RETRIES:
                    time.sleep(2 ** attempt)
        return None

    def _call_ollama(self, user_prompt: str) -> Optional[str]:
        import requests
        from requests.exceptions import ConnectionError as ConnErr, Timeout

        payload = {
            "model":    self.ollama_model,
            "messages": [
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user",   "content": user_prompt},
            ],
            "stream":  False,
            "options": {"temperature": 0.1},
        }

        for attempt in range(1, MAX_RETRIES + 1):
            try:
                resp = requests.post(OLLAMA_API_URL, json=payload, timeout=TIMEOUT)
                if resp.status_code == 200:
                    return resp.json().get("message", {}).get("content", "")
                logger.error("[Ollama] HTTP %d", resp.status_code)
                if attempt < MAX_RETRIES:
                    time.sleep(2 ** attempt)
            except Timeout:
                if attempt < MAX_RETRIES:
                    time.sleep(2 ** attempt)
                else:
                    return None
            except ConnErr:
                return None
            except Exception as exc:
                logger.error("[Ollama] error: %s", exc)
                return None
        return None

    # ── JSON extraction ───────────────────────────────────────────────────────

    def _extract_json(self, text: str) -> Optional[Dict]:
        text = text.strip()
        # Strip markdown fences
        text = re.sub(r"^```(?:json)?\s*", "", text)
        text = re.sub(r"\s*```$",          "", text)
        text = text.strip()

        # Direct parse
        try:
            return json.loads(text)
        except json.JSONDecodeError:
            pass

        # Find first {...} block
        match = re.search(r"\{.*\}", text, re.DOTALL)
        if match:
            try:
                return json.loads(match.group())
            except json.JSONDecodeError:
                pass

        return None
