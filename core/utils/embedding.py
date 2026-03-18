from typing import List

from loguru import logger

from core.ai.provision import provision_embedding_model


async def generate_embedding(text: str) -> List[float]:
    model = await provision_embedding_model()
    return await model.aembed_query(text)


async def generate_embeddings(texts: List[str]) -> List[List[float]]:
    model = await provision_embedding_model()
    return await model.aembed_documents(texts)
