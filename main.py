import asyncio
import logging
import uuid

from langchain_core.messages import HumanMessage

from agent.graph import deep_research_agent


def _silence_external_logs() -> None:
    """Отключает предупреждения"""
    logging.captureWarnings(True)

    quiet_loggers = ["langgraph", "langchain_google_genai"]
    for name in quiet_loggers:
        logger = logging.getLogger(name)
        logger.setLevel(logging.ERROR)
        logger.propagate = False


async def main() -> None:
    _silence_external_logs()

    print("🤖 Добро пожаловать в Deep Research Agent!")
    print("Введите тему исследования (или '/exit' для выхода)")

    while True:
        topic = input("\nТема исследования: ").strip()
        if topic.lower() == "/exit":
            print("До встречи!")
            return
        if not topic:
            continue

        session_id = str(uuid.uuid4())
        config = {"configurable": {"thread_id": session_id}}
        inputs = {"messages": [HumanMessage(content=topic)]}

        while True:
            async for event in deep_research_agent.astream(inputs, config=config, stream_mode="updates"):
                if event.get("clarify_with_user"):
                    print(f"\n🤖 {event['clarify_with_user']['messages'][0].content}")
                elif event.get("write_research_brief"):
                    print("\n" + "=" * 80)
                    print("ИССЛЕДОВАТЕЛЬСКОЕ ЗАДАНИЕ:\n")
                    print(event["write_research_brief"]["research_brief"])
                    print("=" * 80)
                    print("\nИдёт исследование...")
                elif event.get("generate_report"):
                    print("\n" + "=" * 80)
                    print("ОТЧЁТ:\n")
                    print(event["generate_report"]["final_report"])
                    print("=" * 80)
                    break
            else:
                followup = input("\nОтветьте на уточняющие вопросы: ").strip()
                inputs = {"messages": [HumanMessage(content=followup)]}
                continue
            break


if __name__ == "__main__":
    asyncio.run(main())
