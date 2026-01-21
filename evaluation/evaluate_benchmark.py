"""
Wrapper for running deep_research_bench evaluation with custom evaluator model.

Usage:
    python evaluate_benchmark.py --evaluator gpt-oss-120b
    python evaluate_benchmark.py --evaluator gpt-oss-120b --limit 10
"""

import argparse
import logging
import sys
from pathlib import Path

script_dir = Path(__file__).parent
deep_research_dir = script_dir.parent
benchmark_dir = deep_research_dir.parent / "deep_research_bench"
sys.path.insert(0, str(deep_research_dir))
sys.path.insert(0, str(benchmark_dir))

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)


class LangChainAIClient:
    """Adapter for using get_llm() instead of Gemini API"""

    def __init__(self, evaluator_model: str = None):
        from deep_research.ml.utils import get_llm

        model = evaluator_model or "gpt-oss-120b"
        self.llm = get_llm(
            model_name=model,
            temperature=0.1,
        )
        logger.info(f"Using evaluator model: {model}")

    def generate(self, user_prompt: str, system_prompt: str = "", model: str | None = None) -> str:
        """
        Generate text response using LangChain LLM

        Args:
            user_prompt: User prompt
            system_prompt: System prompt (ignored for now)
            model: Model override (ignored, uses initialized model)

        Returns:
            Generated text
        """
        from langchain_core.messages import HumanMessage, SystemMessage

        messages = []
        if system_prompt:
            messages.append(SystemMessage(content=system_prompt))
        messages.append(HumanMessage(content=user_prompt))

        try:
            response = self.llm.invoke(messages)
            return response.content
        except Exception as e:
            logger.error(f"LLM generation failed: {e}", exc_info=True)
            raise Exception(f"Failed to generate content: {str(e)}")


def monkey_patch_ai_client(evaluator_model: str = None):
    """Replaces AIClient in utils.api with LangChainAIClient"""
    import utils.api as api_module

    original_client = api_module.AIClient

    class PatchedAIClient(LangChainAIClient):
        def __init__(self, api_key=None, model=None):
            super().__init__(evaluator_model=evaluator_model)

    api_module.AIClient = PatchedAIClient
    logger.info("Successfully patched AIClient with LangChain implementation")

    return original_client


def run_benchmark_evaluation(limit: int = None, evaluator_model: str = None, only_en: bool = True):
    """
    Run benchmark evaluation with custom evaluator model

    Args:
        limit: Limit number of queries
        evaluator_model: Evaluator model (e.g., "gpt-oss-120b")
        only_en: Only English queries
    """
    logger.info("=" * 80)
    logger.info("Starting Deep Research Benchmark Evaluation")
    logger.info("Evaluating: deep-research")
    logger.info(f"Evaluator model: {evaluator_model or 'gpt-oss-120b'}")
    logger.info("=" * 80)

    original_client = monkey_patch_ai_client(evaluator_model=evaluator_model)

    try:
        from deepresearch_bench_race import main as bench_main

        sys.argv = ["deepresearch_bench_race.py", "deep-research"]

        if limit:
            sys.argv.extend(["--limit", str(limit)])

        if only_en:
            sys.argv.append("--only_en")

        logger.info("Starting benchmark evaluation...")
        bench_main()

        logger.info("=" * 80)
        logger.info("Benchmark evaluation completed successfully")
        logger.info("=" * 80)

    except Exception as e:
        logger.error(f"Benchmark evaluation failed: {e}", exc_info=True)
        raise
    finally:
        import utils.api as api_module

        api_module.AIClient = original_client
        logger.info("Restored original AIClient")


def main():
    parser = argparse.ArgumentParser(
        description="Run deep_research_bench evaluation with custom evaluator model",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Use default evaluator (gpt-oss-120b)
  python evaluate_benchmark.py

  # Use custom evaluator model
  python evaluate_benchmark.py --evaluator gpt-oss-120b

  # Limit to 10 queries
  python evaluate_benchmark.py --evaluator gpt-oss-120b --limit 10
        """,
    )

    parser.add_argument("--limit", type=int, default=None, help="Limit number of queries to evaluate (for testing)")

    parser.add_argument(
        "--evaluator",
        type=str,
        default=None,
        help="Evaluator model (e.g., gpt-oss-120b)",
    )

    args = parser.parse_args()

    try:
        run_benchmark_evaluation(limit=args.limit, evaluator_model=args.evaluator)
        return 0
    except KeyboardInterrupt:
        logger.info("\nEvaluation interrupted by user")
        return 1
    except Exception as e:
        logger.error(f"Evaluation failed: {e}", exc_info=True)
        return 1


if __name__ == "__main__":
    sys.exit(main())
