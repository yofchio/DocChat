import os
from typing import Any, Dict, List, Optional

from langchain_core.messages import AIMessage, HumanMessage, SystemMessage
from loguru import logger

from core.ai.provision import provision_chat_model


async def run_chat(
    message: str,
    notebook_context: str,
    history: List[Dict[str, str]] = None,
    model_override: Optional[str] = None,
) -> str:
    """Simple chat invocation with notebook context."""
    provider = None
    model_name = None
    if model_override and "/" in model_override:
        parts = model_override.split("/", 1)
        provider, model_name = parts[0], parts[1]

    model = await provision_chat_model(provider=provider, model_name=model_name)

    messages = [
        SystemMessage(content=f"""You are an AI research assistant. Answer based on the provided context from the user's notebook. If the context doesn't contain relevant information, say so and provide your best answer.

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

    response = await model.ainvoke(messages)
    return response.content


async def run_chat_stream(
    message: str,
    notebook_context: str,
    history: List[Dict[str, str]] = None,
    model_override: Optional[str] = None,
    use_citations: bool = False,
):
    """Streaming chat invocation."""
    provider = None
    model_name = None
    if model_override and "/" in model_override:
        parts = model_override.split("/", 1)
        provider, model_name = parts[0], parts[1]

    model = await provision_chat_model(provider=provider, model_name=model_name)

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

    async for chunk in model.astream(messages):
        if hasattr(chunk, "content") and chunk.content:
            yield chunk.content
