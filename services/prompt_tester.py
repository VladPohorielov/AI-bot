"""
Simple script to test GPT prompt accuracy
Usage: python -m services.prompt_tester
"""
import asyncio
from .analysis import gpt_analysis


async def main():
    """Test GPT prompts with example conversations"""
    print("🧪 Тестирование GPT промптов для анализа разговоров")
    print("=" * 50)
    
    # Get test examples
    examples = gpt_analysis.get_prompt_examples()
    
    print(f"Доступно примеров для тестирования: {len(examples)}")
    print()
    
    # Test all examples
    results = await gpt_analysis.test_prompt_accuracy()
    
    print(f"📊 Результаты тестирования:")
    print(f"Всего тестов: {results['total_tests']}")
    print(f"Успешных: {results['passed']}")
    print(f"Точность: {results['passed']/results['total_tests']*100:.1f}%")
    print()
    
    # Show detailed results
    for i, result in enumerate(results['results']):
        print(f"🔍 Тест {i+1}: {result['example_name']}")
        print(f"  Ожидалось событий: {result['expected_events']}")
        print(f"  Извлечено событий: {result['actual_events']}")
        print(f"  Статус: {'✅ PASSED' if result['events_match'] else '❌ FAILED'}")
        print(f"  Резюме: {result['summary'][:100]}...")
        
        if result['events']:
            print(f"  События:")
            for j, event in enumerate(result['events']):
                print(f"    {j+1}. {event['title']} ({event['type']}, приоритет: {event['priority']})")
        print()

if __name__ == "__main__":
    asyncio.run(main()) 