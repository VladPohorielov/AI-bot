import g4f
import asyncio
import logging
from typing import List, Dict, Any
from config import SUMMARY_STYLES

logger = logging.getLogger(__name__)


async def generate_summary(text: str, style_key: str) -> str:
    style_info = SUMMARY_STYLES.get(style_key, SUMMARY_STYLES["default"])
    system_prompt = style_info["prompt"]
    
    if not text or not text.strip():
        return "⚠️ Пустой текст для резюмирования."

    messages: List[Dict[str, Any]] = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": text},
    ]
    
    try:
        logger.info(f"Generating summary with style: {style_key}")
        
        # Use sync method in executor for compatibility with auto provider
        loop = asyncio.get_event_loop()
        response = await loop.run_in_executor(
            None,
            lambda: g4f.ChatCompletion.create(
                model=g4f.models.gpt_4o_mini,
                messages=messages
            )
        )
        
        if response and isinstance(response, str) and response.strip():
            # Check if response is blocked
            blocked_phrases = ["request blocked", "get in touch", "solution for your use case"]
            if any(phrase in response.lower() for phrase in blocked_phrases):
                logger.warning("Request was blocked by provider")
                return "⚠️ Запрос заблокирован провайдером. Попробуйте позже."
            
            logger.info(f"Summary generated successfully, length: {len(response)}")
            return response.strip()
        else:
            logger.error(f"Empty or invalid response: {response}")
            return "⚠️ Ошибка: пустой или некорректный ответ от LLM."
            
    except Exception as e:
        logger.error(f"Error generating summary: {e}", exc_info=True)
        return f"⚠️ Не удалось получить ответ от LLM: {str(e)}"
