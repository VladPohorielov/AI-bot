#!/usr/bin/env python3
"""
Test script to verify summarization functionality
"""
import asyncio
import sys
import os

# Add current directory to path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from services.summarization import generate_summary

async def test_summarization():
    print("🧪 Testing summarization service...")
    
    test_text = """
    Це довгий текст про штучний інтелект та машинне навчання. 
    Штучний інтелект змінює світ, надаючи можливості автоматизації 
    різних процесів. Машинне навчання є підгалуззю штучного інтелекту, 
    яка дозволяє комп'ютерам навчатися без явного програмування. 
    Глибоке навчання використовує нейронні мережі для вирішення 
    складних завдань. Важливо розуміти етичні аспекти використання 
    штучного інтелекту в суспільстві.
    """
    
    try:
        print("📝 Generating summary...")
        summary = await generate_summary(test_text, "default")
        print(f"✅ Summary generated:")
        print(f"Original length: {len(test_text)} chars")
        print(f"Summary length: {len(summary)} chars")
        print(f"Summary: {summary}")
        return True
    except Exception as e:
        print(f"❌ Error: {e}")
        return False

if __name__ == "__main__":
    success = asyncio.run(test_summarization())
    sys.exit(0 if success else 1) 