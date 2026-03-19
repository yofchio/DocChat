import asyncio
from typing import Optional

from content_core import extract_content
from loguru import logger

from core.ai.provision import provision_chat_model
from core.database.repository import ensure_record_id, repo_insert, repo_query
from core.domain.notebook import Source
from core.utils.chunking import chunk_text
from core.utils.embedding import generate_embeddings


async def process_source(source_id: str):
    """Background task: extract content from source, chunk, and vectorize."""
    try:
        # This runs in background (fire-and-forget) to keep API responses fast.
        # Flow:
        # 1) extract content -> store `full_text`
        # 2) generate Source Guide (summary + keywords) once per source
        # 3) chunk text + create embeddings for vector retrieval
        source = await Source.get(source_id)
        source.status = "processing"
        source.status_message = "Extracting content..."
        await source.save()
        logger.info(f"Processing source {source_id}: {source.title}")

        if source.asset:
            asset_dict = source.asset.model_dump() if hasattr(source.asset, "model_dump") else source.asset
            content_state = {
                "url": asset_dict.get("url"),
                "file_path": asset_dict.get("file_path"),
                "url_engine": "auto",
                "document_engine": "auto",
                "output_format": "markdown",
            }

            processed = await extract_content(content_state)

            if processed.content and processed.content.strip():
                source.full_text = processed.content
                source.title = processed.title or source.title
                if hasattr(processed, "topics") and processed.topics:
                    source.topics = processed.topics
                source.status_message = "Generating summary..."
                await source.save()
                logger.info(f"Content extracted for {source_id}: {len(source.full_text)} chars")

                try:
                    await generate_source_guide(source)
                except Exception as ge:
                    logger.warning(f"Summary generation failed for {source_id}: {ge}")

                source.status_message = "Generating embeddings..."
                await source.save()

                try:
                    await vectorize_source(source)
                    source.status = "completed"
                    source.status_message = None
                    await source.save()
                except Exception as ve:
                    logger.error(f"Vectorization failed for {source_id}: {ve}")
                    source.status = "error"
                    source.status_message = f"Embedding failed: {str(ve)[:150]}"
                    await source.save()
            else:
                source.status = "error"
                source.status_message = "No content could be extracted"
                await source.save()
                logger.warning(f"No content extracted for {source_id}")
        else:
            source.status = "error"
            source.status_message = "Source has no file or URL"
            await source.save()
            logger.warning(f"Source {source_id} has no asset to process")

    except Exception as e:
        logger.error(f"Failed to process source {source_id}: {e}")
        logger.exception(e)
        try:
            source = await Source.get(source_id)
            source.status = "error"
            source.status_message = str(e)[:200]
            await source.save()
        except Exception:
            pass


async def generate_source_guide(source: Source):
    """Use AI to generate a summary and keywords for a source."""
    try:
        # Guide parsing is intentionally strict to make the frontend stable:
        # - expects lines starting with SUMMARY: and KEYWORDS:
        # If the model deviates, guide generation may silently skip fields.
        llm = await provision_chat_model()
        text_preview = source.full_text[:6000] if source.full_text else ""
        prompt = (
            "Analyze the following document and provide:\n"
            "1. A concise summary (2-3 sentences)\n"
            "2. 5-8 key topics/keywords\n\n"
            "Format your response EXACTLY as:\n"
            "SUMMARY: <your summary>\n"
            "KEYWORDS: keyword1, keyword2, keyword3, ...\n\n"
            f"Document:\n{text_preview}"
        )
        response = await llm.ainvoke(prompt)
        text = response.content if hasattr(response, "content") else str(response)

        for line in text.strip().split("\n"):
            line = line.strip()
            if line.upper().startswith("SUMMARY:"):
                source.summary = line[8:].strip()
            elif line.upper().startswith("KEYWORDS:"):
                keywords = [k.strip() for k in line[9:].split(",") if k.strip()]
                if keywords:
                    source.topics = keywords

        await source.save()
        logger.info(f"Source guide generated for {source.id}")
    except Exception as e:
        logger.warning(f"Failed to generate source guide: {e}")


async def vectorize_source(source: Source):
    """Chunk text and create embeddings in the source_embedding table."""
    if not source.full_text or not source.full_text.strip():
        logger.warning(f"Source {source.id} has no text to vectorize")
        return

    try:
        source_rid = ensure_record_id(source.id)

        # Remove old embeddings
        await repo_query(
            "DELETE source_embedding WHERE source = $source_id",
            {"source_id": source_rid},
        )

        # Chunk text
        chunks = chunk_text(source.full_text)
        if not chunks:
            return

        logger.info(f"Vectorizing {len(chunks)} chunks for source {source.id}")

        # Generate embeddings in batches
        batch_size = 20
        all_records = []
        for i in range(0, len(chunks), batch_size):
            batch = chunks[i : i + batch_size]
            embeddings = await generate_embeddings(batch)
            for text, embedding in zip(batch, embeddings):
                all_records.append({
                    "source": source_rid,
                    "content": text,
                    "embedding": embedding,
                })

        # Bulk insert
        if all_records:
            await repo_insert("source_embedding", all_records)
            logger.info(f"Inserted {len(all_records)} embeddings for source {source.id}")

    except Exception as e:
        logger.error(f"Vectorization failed for {source.id}: {e}")
        raise


def submit_source_processing(source_id: str):
    """Fire-and-forget source processing in the background."""
    try:
        loop = asyncio.get_running_loop()
        loop.create_task(process_source(source_id))
    except RuntimeError:
        asyncio.run(process_source(source_id))
