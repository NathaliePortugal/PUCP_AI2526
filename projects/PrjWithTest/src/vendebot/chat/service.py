"""Orquesta un turno de /chat: presupuesto, historial acotado y bucle de herramientas.

La estimacion de tokens es aproximada (caracteres / 4), no el conteo exacto
del proveedor: alcanza para el proposito real del limite, frenar a un
cliente que abusa del chat, sin fingir una precision que no se verifico.
"""

from dataclasses import dataclass, field

from vendebot.chat.tools import TOOL_SPECS, execute_tool
from vendebot.config import Settings
from vendebot.errors import BudgetExceededError
from vendebot.llm.base import ChatTurn, LLMClient, ToolResult
from vendebot.repo.factory import Repos
from vendebot.repo.models import Customer, Proposal

MAX_TOOL_ROUNDS = 4
CHARS_PER_TOKEN_ESTIMATE = 4


@dataclass
class ChatResult:
    reply: str
    proposal: Proposal | None
    tools_used: list[str] = field(default_factory=list)


def _estimate_tokens(text: str) -> int:
    return max(1, len(text) // CHARS_PER_TOKEN_ESTIMATE)


def run_chat_turn(
    *,
    llm_client: LLMClient,
    repos: Repos,
    settings: Settings,
    customer: Customer,
    session_id: str,
    message: str,
) -> ChatResult:
    usage_today = repos.budget.get_usage_today(customer.id)
    if usage_today >= settings.daily_token_budget_per_customer:
        raise BudgetExceededError("Se alcanzo el presupuesto diario de tokens para este cliente")

    history = repos.sessions.get_history(session_id, customer.id)
    bounded = history[-settings.chat_history_max_turns :]
    turns = [ChatTurn(role=t["role"], text=t["text"]) for t in bounded]
    turns.append(ChatTurn(role="user", text=message))

    tools_used: list[str] = []
    last_proposal: Proposal | None = None

    reply = llm_client.generate_reply(turns, TOOL_SPECS)
    rounds = 0
    while reply.tool_calls and rounds < MAX_TOOL_ROUNDS:
        rounds += 1
        results: list[ToolResult] = []
        for call in reply.tool_calls:
            if call.name not in tools_used:
                tools_used.append(call.name)
            result, proposal = execute_tool(
                call.name, call.arguments, repos, customer, settings.proposal_expiration_minutes
            )
            if proposal is not None:
                last_proposal = proposal
            results.append(ToolResult(name=call.name, call_id=call.call_id, result=result))
        reply = llm_client.continue_with_tool_results(reply.continuation_token, results, TOOL_SPECS)

    final_text = reply.text or "No pude generar una respuesta, por favor intenta de nuevo."

    repos.sessions.append_turn(session_id, customer.id, "user", message)
    repos.sessions.append_turn(session_id, customer.id, "model", final_text)
    repos.budget.add_usage(customer.id, _estimate_tokens(message) + _estimate_tokens(final_text))

    return ChatResult(reply=final_text, proposal=last_proposal, tools_used=tools_used)
