import os
from typing import Optional

from loguru import logger


def get_default_provider() -> str:
    return os.getenv("DEFAULT_AI_PROVIDER", "google")


def get_default_model() -> str:
    return os.getenv("DEFAULT_AI_MODEL", "gemini-2.5-flash")


async def provision_chat_model(
    provider: Optional[str] = None,
    model_name: Optional[str] = None,
):
    provider = provider or get_default_provider()
    model_name = model_name or get_default_model()

    logger.debug(f"Provisioning chat model: {provider}/{model_name}")

    if provider == "google":
        from langchain_google_genai import ChatGoogleGenerativeAI

        return ChatGoogleGenerativeAI(
            model=model_name,
            google_api_key=os.getenv("GOOGLE_API_KEY"),
        )
    elif provider == "openai":
        from langchain_openai import ChatOpenAI

        return ChatOpenAI(
            model=model_name,
            api_key=os.getenv("OPENAI_API_KEY"),
        )
    else:
        raise ValueError(f"Unsupported provider: {provider}")


async def provision_embedding_model(
    provider: Optional[str] = None,
):
    provider = provider or get_default_provider()

    if provider == "google":
        from langchain_google_genai import GoogleGenerativeAIEmbeddings

        return GoogleGenerativeAIEmbeddings(
            model="models/gemini-embedding-001",
            google_api_key=os.getenv("GOOGLE_API_KEY"),
        )
    elif provider == "openai":
        from langchain_openai import OpenAIEmbeddings

        return OpenAIEmbeddings(
            model="text-embedding-3-small",
            api_key=os.getenv("OPENAI_API_KEY"),
        )
    else:
        raise ValueError(f"Unsupported provider: {provider}")
