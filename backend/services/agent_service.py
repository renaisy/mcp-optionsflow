"""
Agent service - LLM chat with options/strategy tools
"""
import json
import logging
from typing import Optional, Dict, Any, List, Iterator
import sys
import os

sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from openai import OpenAI
import httpx

logger = logging.getLogger(__name__)

# Preset models for providers that don't support listing
OPENAI_PRESETS = ["gpt-4o", "gpt-4o-mini", "gpt-4-turbo", "gpt-4", "gpt-3.5-turbo"]
GLM_PRESETS = ["glm-4-flash", "glm-4", "glm-3-turbo"]

# Tool definitions for OpenAI function calling
AGENT_TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "get_stock_info",
            "description": "Get comprehensive stock information including price, volume, market cap, and key metrics",
            "parameters": {
                "type": "object",
                "properties": {
                    "symbol": {"type": "string", "description": "Stock symbol (e.g., AAPL, TSLA, 510050)"}
                },
                "required": ["symbol"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "get_expiration_dates",
            "description": "Get all available options expiration dates for a stock",
            "parameters": {
                "type": "object",
                "properties": {
                    "symbol": {"type": "string", "description": "Stock symbol"}
                },
                "required": ["symbol"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "get_option_chain",
            "description": "Get options chain data for a specific expiration date. Returns calls and puts with strike, bid, ask, volume, IV.",
            "parameters": {
                "type": "object",
                "properties": {
                    "symbol": {"type": "string", "description": "Stock symbol"},
                    "expiration_date": {"type": "string", "description": "Expiration date (YYYY-MM-DD). If not provided, uses nearest."},
                    "option_type": {"type": "string", "enum": ["call", "put", "all"], "description": "Filter by option type (default: all)"}
                },
                "required": ["symbol"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "analyze_strategy",
            "description": "Analyze options strategies: CCS (Credit Call Spread), PCS (Put Credit Spread), CSP (Cash Secured Put), CC (Covered Call)",
            "parameters": {
                "type": "object",
                "properties": {
                    "symbol": {"type": "string", "description": "Stock symbol"},
                    "strategy": {"type": "string", "enum": ["ccs", "pcs", "csp", "cc"], "description": "Strategy type"},
                    "expiration_date": {"type": "string", "description": "Expiration date (YYYY-MM-DD)"},
                    "delta_target": {"type": "number", "description": "Target delta for CSP/CC (default: 0.3)"},
                    "width_pct": {"type": "number", "description": "Width for spreads as decimal (default: 0.05)"}
                },
                "required": ["symbol", "strategy", "expiration_date"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "compare_strategies",
            "description": "Compare multiple options strategies for the same symbol and expiration",
            "parameters": {
                "type": "object",
                "properties": {
                    "symbol": {"type": "string", "description": "Stock symbol"},
                    "expiration_date": {"type": "string", "description": "Expiration date (YYYY-MM-DD)"},
                    "strategies": {
                        "type": "array",
                        "items": {"type": "string", "enum": ["ccs", "pcs", "csp", "cc"]},
                        "description": "Strategies to compare"
                    }
                },
                "required": ["symbol", "expiration_date", "strategies"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "analyze_pnl_scenarios",
            "description": "Analyze profit/loss scenarios for an options strategy at different stock prices at expiration",
            "parameters": {
                "type": "object",
                "properties": {
                    "symbol": {"type": "string"},
                    "strategy": {"type": "string", "enum": ["ccs", "pcs", "csp", "cc"]},
                    "expiration_date": {"type": "string"},
                    "price_range_pct": {"type": "number", "description": "Range around current price (default: 0.20)"},
                    "steps": {"type": "integer", "description": "Number of price points (default: 20)"}
                },
                "required": ["symbol", "strategy", "expiration_date"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "find_best_strategies",
            "description": "Find best options strategies by risk/reward criteria",
            "parameters": {
                "type": "object",
                "properties": {
                    "symbol": {"type": "string"},
                    "expiration_date": {"type": "string", "description": "Optional. Uses 30-45 DTE if not provided."},
                    "min_probability_profit": {"type": "number", "description": "Min probability of profit (default: 0.60)"},
                    "max_risk_reward_ratio": {"type": "number", "description": "Max risk/reward ratio (default: 3.0)"},
                    "strategy_preference": {"type": "string", "enum": ["bullish", "bearish", "neutral", "any"], "description": "Market outlook (default: any)"}
                },
                "required": ["symbol"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "get_data_sources_status",
            "description": "Get status of all available data sources and their availability",
            "parameters": {"type": "object", "properties": {}, "required": []}
        }
    },
]


def _truncate_for_context(s: str, max_chars: int = 8000) -> str:
    """Truncate string to avoid exceeding LLM context"""
    if len(s) <= max_chars:
        return s
    return s[:max_chars] + "\n\n[... truncated for length ...]"


def _execute_tool(name: str, arguments: dict) -> str:
    """Execute a tool and return JSON string result"""
    from backend.services.options_service import OptionsService
    from backend.services.strategy_service import StrategyService
    from backend.utils.data_source import get_sources_status

    strategy_service = StrategyService()

    try:
        if name == "get_stock_info":
            symbol = (arguments.get("symbol") or "").strip().upper()
            if not symbol:
                return json.dumps({"success": False, "error": "symbol is required"})
            result = OptionsService.get_stock_info(symbol)
            if not result:
                return json.dumps({"success": False, "error": f"Stock info not found for {symbol}"})
            return json.dumps({"success": True, "data": result})

        elif name == "get_expiration_dates":
            symbol = (arguments.get("symbol") or "").strip().upper()
            if not symbol:
                return json.dumps({"success": False, "error": "symbol is required"})
            exp_dates = OptionsService.get_expiration_dates(symbol)
            if not exp_dates:
                return json.dumps({"success": False, "error": f"No expiration dates for {symbol}"})
            return json.dumps({"success": True, "data": {"symbol": symbol, "expiration_dates": exp_dates}})

        elif name == "get_option_chain":
            symbol = (arguments.get("symbol") or "").strip().upper()
            if not symbol:
                return json.dumps({"success": False, "error": "symbol is required"})
            exp_date = arguments.get("expiration_date")
            option_type = arguments.get("option_type") or "all"
            chain = OptionsService.get_option_chain(symbol, exp_date, option_type if option_type != "all" else None)
            if not chain:
                return json.dumps({"success": False, "error": f"Option chain not found for {symbol}"})
            out = json.dumps({"success": True, "data": chain})
            return _truncate_for_context(out)

        elif name == "analyze_strategy":
            symbol = (arguments.get("symbol") or "").strip().upper()
            strategy = (arguments.get("strategy") or "").lower()
            exp_date = arguments.get("expiration_date")
            delta_target = arguments.get("delta_target")
            width_pct = arguments.get("width_pct")
            if not symbol or strategy not in ("ccs", "pcs", "csp", "cc"):
                return json.dumps({"success": False, "error": "symbol and strategy (ccs/pcs/csp/cc) required"})
            result = strategy_service.analyze_strategy(
                symbol=symbol, strategy_type=strategy,
                expiration_date=exp_date, delta_target=delta_target, width_pct=width_pct
            )
            if not result:
                return json.dumps({"success": False, "error": "Analysis failed"})
            return json.dumps({"success": True, "data": result})

        elif name == "compare_strategies":
            symbol = (arguments.get("symbol") or "").strip().upper()
            exp_date = arguments.get("expiration_date")
            strategies = arguments.get("strategies") or []
            if not symbol or not strategies:
                return json.dumps({"success": False, "error": "symbol and strategies list required"})
            configs = [{"strategy_type": s, "expiration_date": exp_date} for s in strategies]
            results = strategy_service.analyze_multiple_strategies(symbol, configs)
            return json.dumps({"success": True, "data": results})

        elif name == "analyze_pnl_scenarios":
            symbol = (arguments.get("symbol") or "").strip().upper()
            strategy = (arguments.get("strategy") or "").lower()
            exp_date = arguments.get("expiration_date")
            price_range_pct = arguments.get("price_range_pct", 0.20)
            steps = arguments.get("steps", 20)
            if not symbol or strategy not in ("ccs", "pcs", "csp", "cc") or not exp_date:
                return json.dumps({"success": False, "error": "symbol, strategy, expiration_date required"})
            result = strategy_service.analyze_pnl_scenarios(
                symbol, strategy, exp_date, price_range_pct, steps
            )
            if not result:
                return json.dumps({"success": False, "error": "P&L analysis failed"})
            return json.dumps({"success": True, "data": result})

        elif name == "find_best_strategies":
            symbol = (arguments.get("symbol") or "").strip().upper()
            if not symbol:
                return json.dumps({"success": False, "error": "symbol required"})
            exp_date = arguments.get("expiration_date")
            min_pop = arguments.get("min_probability_profit", 0.60)
            max_rr = arguments.get("max_risk_reward_ratio", 3.0)
            pref = arguments.get("strategy_preference", "any")
            result = strategy_service.find_best_strategies(
                symbol, exp_date, min_pop, max_rr, pref
            )
            if not result:
                return json.dumps({"success": False, "error": "Find best failed"})
            return json.dumps({"success": True, "data": result})

        elif name == "get_data_sources_status":
            result = get_sources_status()
            return json.dumps({"success": True, "data": result})

        return json.dumps({"success": False, "error": f"Unknown tool: {name}"})

    except ValueError as e:
        return json.dumps({"success": False, "error": str(e)})
    except Exception as e:
        logger.exception("Tool %s failed: %s", name, e)
        return json.dumps({"success": False, "error": str(e)})


async def list_available_models(config: Dict[str, Any]) -> List[Dict[str, Any]]:
    """
    List available models for the configured provider with status.
    Returns: [{ id, name, status, provider }]
    status: "available" | "unavailable" | "unknown"
    """
    provider = (config.get("provider") or "openai").lower()
    base_url = (config.get("base_url") or "").rstrip("/")
    api_key = config.get("api_key") or ""
    current_model = config.get("model") or ""

    result: List[Dict[str, Any]] = []

    async with httpx.AsyncClient(timeout=10.0) as client:
        if provider == "ollama":
            # Ollama: GET /api/tags + /api/ps for running status
            ollama_base = base_url.replace("/v1", "").rstrip("/") or "http://localhost:11434"
            running_models: set = set()
            try:
                ps_resp = await client.get(f"{ollama_base}/api/ps")
                if ps_resp.status_code == 200:
                    ps_data = ps_resp.json()
                    for m in ps_data.get("models") or []:
                        rn = (m.get("name") or "").split(":")[0]
                        if rn:
                            running_models.add(rn)
            except Exception:
                pass
            url = f"{ollama_base}/api/tags"
            try:
                resp = await client.get(url)
                if resp.status_code == 200:
                    data = resp.json()
                    models = data.get("models") or []
                    seen = set()
                    for m in models:
                        raw = m.get("name") or m.get("model") or ""
                        name = raw.split(":")[0] if ":" in raw else raw
                        if name and name not in seen:
                            seen.add(name)
                            result.append({
                                "id": name,
                                "name": name,
                                "status": "running" if name in running_models else "available",
                                "provider": "ollama",
                                "is_current": name == current_model or current_model.startswith(name),
                            })
                else:
                    result.append({
                        "id": current_model or "ollama",
                        "name": current_model or "Ollama",
                        "status": "unavailable",
                        "provider": "ollama",
                        "is_current": True,
                        "note": f"HTTP {resp.status_code}",
                    })
            except Exception as e:
                logger.warning("Ollama models fetch failed: %s", e)
                result.append({
                    "id": current_model or "ollama",
                    "name": current_model or "Ollama",
                    "status": "unavailable",
                    "provider": "ollama",
                    "is_current": True,
                    "note": str(e)[:80],
                })

        elif provider == "vllm":
            url = f"{base_url or 'http://localhost:8000/v1'}/models"
            try:
                resp = await client.get(url)
                if resp.status_code == 200:
                    data = resp.json()
                    models = data.get("data") or []
                    for m in models:
                        mid = m.get("id") or m.get("name") or ""
                        result.append({
                            "id": mid,
                            "name": mid,
                            "status": "available",
                            "provider": "vllm",
                            "is_current": mid == current_model,
                        })
                else:
                    result.append({
                        "id": current_model or "vllm",
                        "name": current_model or "vLLM",
                        "status": "unavailable",
                        "provider": "vllm",
                        "is_current": True,
                        "note": f"HTTP {resp.status_code}",
                    })
            except Exception as e:
                logger.warning("vLLM models fetch failed: %s", e)
                result.append({
                    "id": current_model or "vllm",
                    "name": current_model or "vLLM",
                    "status": "unavailable",
                    "provider": "vllm",
                    "is_current": True,
                    "note": str(e)[:80],
                })

        elif provider == "openai":
            api_base = base_url or "https://api.openai.com/v1"
            url = f"{api_base}/models"
            try:
                headers = {}
                if api_key:
                    headers["Authorization"] = f"Bearer {api_key}"
                resp = await client.get(url, headers=headers or None)
                if resp.status_code == 200:
                    data = resp.json()
                    items = data.get("data") or []
                    seen = set()
                    for m in items:
                        mid = (m.get("id") or "").strip()
                        if mid and ("gpt" in mid.lower() or "o1" in mid.lower()):
                            if mid not in seen:
                                seen.add(mid)
                                result.append({
                                    "id": mid,
                                    "name": mid,
                                    "status": "available",
                                    "provider": "openai",
                                    "is_current": mid == current_model,
                                })
                if not result:
                    for name in OPENAI_PRESETS:
                        result.append({
                            "id": name,
                            "name": name,
                            "status": "available",
                            "provider": "openai",
                            "is_current": name == current_model,
                        })
            except Exception as e:
                logger.warning("OpenAI models fetch failed: %s", e)
                for name in OPENAI_PRESETS:
                    result.append({
                        "id": name,
                        "name": name,
                        "status": "unknown",
                        "provider": "openai",
                        "is_current": name == current_model,
                    })

        elif provider == "glm":
            for name in GLM_PRESETS:
                result.append({
                    "id": name,
                    "name": name,
                    "status": "available",
                    "provider": "glm",
                    "is_current": name == current_model,
                })

        else:
            result.append({
                "id": current_model or provider,
                "name": current_model or provider,
                "status": "unknown",
                "provider": provider,
                "is_current": True,
            })

    # Ensure current config model is in list
    if result and current_model:
        found = any(r["id"] == current_model for r in result)
        if not found:
            result.insert(0, {
                "id": current_model,
                "name": current_model,
                "status": "available",
                "provider": provider,
                "is_current": True,
            })
    elif not result and current_model:
        result = [{
            "id": current_model,
            "name": current_model,
            "status": "unknown",
            "provider": provider,
            "is_current": True,
        }]

    return result


def _build_client(config: Dict[str, Any]) -> OpenAI:
    """Build OpenAI client from config"""
    base_url = config.get("base_url") or None
    api_key = config.get("api_key") or "dummy"  # Ollama often accepts any key
    if config.get("provider") == "openai" and not base_url:
        base_url = "https://api.openai.com/v1"
    if config.get("provider") == "glm" and not base_url:
        base_url = "https://open.bigmodel.cn/api/paas/v4"
    if config.get("provider") == "ollama" and not base_url:
        base_url = "http://localhost:11434/v1"
    if config.get("provider") == "vllm" and not base_url:
        base_url = "http://localhost:8000/v1"

    return OpenAI(
        base_url=base_url,
        api_key=api_key,
    )


def chat_with_tools(
    messages: List[Dict[str, Any]],
    config: Dict[str, Any],
) -> str:
    """
    Run chat with tool execution loop. Returns final assistant text.
    """
    client = _build_client(config)
    model = config.get("model") or "gpt-4o-mini"

    while True:
        response = client.chat.completions.create(
            model=model,
            messages=messages,
            tools=AGENT_TOOLS,
            tool_choice="auto",
        )
        choice = response.choices[0]
        if choice.finish_reason == "stop":
            return (choice.message.content or "").strip()

        if choice.message.tool_calls:
            for tc in choice.message.tool_calls:
                name = tc.function.name if hasattr(tc.function, "name") else getattr(tc, "function", {}).get("name")
                args_str = tc.function.arguments if hasattr(tc.function, "arguments") else getattr(tc, "function", {}).get("arguments", "{}")
                try:
                    args = json.loads(args_str) if isinstance(args_str, str) else args_str
                except json.JSONDecodeError:
                    args = {}
                result = _execute_tool(name, args)
                messages.append(choice.message)
                messages.append({
                    "role": "tool",
                    "tool_call_id": tc.id,
                    "content": result,
                })
        else:
            return (choice.message.content or "").strip()

        # Next iteration will use updated messages


CARD_TOOLS = {"analyze_strategy", "compare_strategies", "find_best_strategies", "analyze_pnl_scenarios", "get_stock_info"}


def chat_with_tools_stream(
    messages: List[Dict[str, Any]],
    config: Dict[str, Any],
) -> Iterator[Dict[str, Any]]:
    """
    Stream chat with tool execution. Yields dicts: {type: "chunk", content} or
    {type: "tool_call", tool} or {type: "tool_result", tool, data}.
    """
    client = _build_client(config)
    model = config.get("model") or "gpt-4o-mini"
    last_chunk = None

    while True:
        stream = client.chat.completions.create(
            model=model,
            messages=messages,
            tools=AGENT_TOOLS,
            tool_choice="auto",
            stream=True,
        )

        assistant_content = []
        tool_calls_buf: List[Dict] = []

        for chunk in stream:
            last_chunk = chunk
            if not chunk.choices:
                continue
            delta = chunk.choices[0].delta
            if delta.content:
                assistant_content.append(delta.content)
                yield {"type": "chunk", "content": delta.content}
            if delta.tool_calls:
                for tc in delta.tool_calls:
                    idx = tc.index if hasattr(tc, "index") else 0
                    while len(tool_calls_buf) <= idx:
                        tool_calls_buf.append({
                            "id": "",
                            "name": "",
                            "arguments": "",
                        })
                    if tc.id:
                        tool_calls_buf[idx]["id"] = tc.id
                    if tc.function:
                        fn = tc.function
                        if hasattr(fn, "name") and fn.name:
                            tool_calls_buf[idx]["name"] = fn.name
                        if hasattr(fn, "arguments") and fn.arguments:
                            tool_calls_buf[idx]["arguments"] = tool_calls_buf[idx].get("arguments", "") + (fn.arguments or "")

        # Check finish reason from last chunk
        finish_reason = (last_chunk.choices[0].finish_reason if last_chunk and last_chunk.choices else None)
        if finish_reason == "stop":
            return

        # If we had tool calls, execute and loop
        if tool_calls_buf:
            full_message: Dict[str, Any] = {
                "role": "assistant",
                "tool_calls": [
                    {
                        "id": t["id"],
                        "type": "function",
                        "function": {"name": t["name"], "arguments": t["arguments"]}
                    }
                    for t in tool_calls_buf
                ]
            }
            if assistant_content:
                full_message["content"] = "".join(assistant_content)
            messages.append(full_message)

            for t in tool_calls_buf:
                name = t["name"]
                try:
                    args = json.loads(t["arguments"]) if t["arguments"] else {}
                except json.JSONDecodeError:
                    args = {}
                result = _execute_tool(name, args)
                messages.append({
                    "role": "tool",
                    "tool_call_id": t["id"],
                    "content": result,
                })
                yield {"type": "tool_call", "tool": name}
                if name in CARD_TOOLS:
                    try:
                        parsed = json.loads(result)
                        if parsed.get("success") and "data" in parsed:
                            yield {"type": "tool_result", "tool": name, "data": parsed["data"]}
                    except (json.JSONDecodeError, TypeError):
                        pass
        else:
            return
