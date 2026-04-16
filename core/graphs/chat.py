import os
from typing import Any, Dict, List, Optional

from langchain_core.messages import AIMessage, HumanMessage, SystemMessage
from loguru import logger

from core.ai.provision import provision_chat_model

# =============================================================================
# LLM Invocation Layer
# =============================================================================
# This module is the final step in the pipeline — it takes the assembled
# context (from chat_service.py) and actually calls the LLM.
#
# Two modes:
#   run_chat()        — waits for the full response (non-streaming)
#   run_chat_stream() — yields partial content chunks as they arrive (SSE)
#
# Message format follows the LangChain convention:
#   SystemMessage  → sets the assistant role + injects notebook context
#   HumanMessage   → user turns (history + current question)
#   AIMessage      → assistant turns (history only)
# =============================================================================


async def run_chat(
    message: str,
    notebook_context: str,
    history: List[Dict[str, str]] = None,
    model_override: Optional[str] = None,
) -> str:
    """Non-streaming LLM call — returns the complete answer as a string."""
    # Parse optional "provider/model" override (e.g. "google/gemini-2.5-flash")
    provider = None
    model_name = None
    if model_override and "/" in model_override:
        parts = model_override.split("/", 1)
        provider, model_name = parts[0], parts[1]

    # provision_chat_model() picks the right LangChain chat model class
    # based on provider (Google → ChatGoogleGenerativeAI, OpenAI → ChatOpenAI)
    model = await provision_chat_model(provider=provider, model_name=model_name)

    # Build the LangChain message list:
    #   [SystemMessage, ...history pairs..., HumanMessage(current question)]
    messages = [
        SystemMessage(content=f"""You are an AI research assistant. Answer based on the provided context from the user's notebook. If the context doesn't contain relevant information, say so and provide your best answer.

## Notebook Context
{notebook_context}"""),
    ]

    # Replay conversation history so the LLM has multi-turn context
    if history:
        for msg in history:
            if msg["role"] == "human":
                messages.append(HumanMessage(content=msg["content"]))
            elif msg["role"] == "ai":
                messages.append(AIMessage(content=msg["content"]))

    # Append the current user question as the final message
    messages.append(HumanMessage(content=message))

    response = await model.ainvoke(messages)
    return response.content

    """Streaming LLM call — yields content strings as the model generates.

    When use_citations is True, we append an extra instruction to the system
    prompt telling the LLM to cite numbered references like [1], [2].
    The numbers correspond to the references that build_rag_context() put
    into the notebook_context, and the frontend will later map them to
    clickable CitationPopover components.
    """

async def run_chat_stream(
    message: str,
    notebook_context: str,
    history: List[Dict[str, str]] = None,
    model_override: Optional[str] = None,
    use_citations: bool = False,
):

    provider = None
    model_name = None
    if model_override and "/" in model_override:
        parts = model_override.split("/", 1)
        provider, model_name = parts[0], parts[1]

    model = await provision_chat_model(provider=provider, model_name=model_name)

    # When RAG references are present, instruct the LLM to cite them inline.
    # This is what makes the model output "[1]", "[2]" in its answer text.
    citation_instruction = ""
    if use_citations:
        citation_instruction = """

IMPORTANT: The context below contains numbered references like [1], [2], etc. When you use information from a specific reference, cite it inline using the same number, e.g. [1]. Place citations at the end of the relevant sentence. You may cite multiple references for one statement, e.g. [1][3]."""

    messages = [
        SystemMessage(content=f"""You are an AI research assistant. Answer based on the provided context from the user's notebook. If the context doesn't contain relevant information, say so and provide your best answer.{citation_instruction}

## Notebook Context
{notebook_context}"""),
    ]

    if history:
        for msg in history:
            if msg["role"] == "human":
                messages.append(HumanMessage(content=msg["content"]))
            elif msg["role"] == "ai":
                messages.append(AIMessage(content=msg["content"]))

    messages.append(HumanMessage(content=message))

    # model.astream() returns an async iterator of AIMessageChunk objects.
    # Each chunk's `.content` is a small piece of the generated text
    # (could be a word, a few characters, or a sentence fragment).
    # We yield each piece immediately so the router can push it via SSE.
    async for chunk in model.astream(messages):
        if hasattr(chunk, "content") and chunk.content:
            yield chunk.content
