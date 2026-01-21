"""
Run deep-research on deep_research_bench.

Usage:
    python run_benchmark.py --limit 5
    python run_benchmark.py --output-dir results/test_run
"""

import argparse
import asyncio
import json
import logging
import sys
from datetime import datetime
from pathlib import Path
from typing import Any

script_dir = Path(__file__).parent
deep_research_dir = script_dir.parent
benchmark_dir = deep_research_dir.parent / "deep_research_bench"
sys.path.insert(0, str(deep_research_dir))
sys.path.insert(0, str(benchmark_dir))

log_dir = script_dir / "logs"
log_dir.mkdir(parents=True, exist_ok=True)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[
        logging.FileHandler(log_dir / "benchmark.log"),
        logging.StreamHandler(sys.stdout),
    ],
)
logger = logging.getLogger(__name__)

from utils.io_utils import load_jsonl


async def run_single_research(query: str, query_id: int) -> dict[str, Any]:
    """
    Run research for a single query.

    Args:
        query: Research query
        query_id: Query ID for tracking

    Returns:
        Dictionary with research results
    """
    from langchain_core.messages import HumanMessage

    from deep_research.ml.graph import deep_research_agent

    start_time = datetime.now()

    try:
        result = await deep_research_agent.ainvoke(
            {"messages": [HumanMessage(content=query)]},
            config={"configurable": {"thread_id": f"benchmark_{query_id}"}},
        )

        end_time = datetime.now()
        duration = (end_time - start_time).total_seconds()

        final_report = result.get("final_report", "")

        if not final_report:
            logger.warning(f"Query {query_id}: Empty final_report")
            return {
                "id": query_id,
                "prompt": query,
                "error": "Empty final_report returned",
                "timing": {
                    "start_time": start_time.isoformat(),
                    "end_time": end_time.isoformat(),
                    "duration_seconds": duration,
                },
            }

        return {
            "id": query_id,
            "prompt": query,
            "article": final_report,
            "timing": {
                "start_time": start_time.isoformat(),
                "end_time": end_time.isoformat(),
                "duration_seconds": duration,
            },
            "metadata": {
                "article_length": len(final_report),
                "word_count": len(final_report.split()),
            },
        }

    except Exception as e:
        end_time = datetime.now()
        duration = (end_time - start_time).total_seconds()

        logger.error(f"Query {query_id}: Research failed - {e}", exc_info=True)

        return {
            "id": query_id,
            "prompt": query,
            "error": str(e),
            "timing": {
                "start_time": start_time.isoformat(),
                "end_time": end_time.isoformat(),
                "duration_seconds": duration,
            },
        }


async def run_benchmark(
    limit: int = None,
    output_dir: str = "evaluation/results",
    resume: bool = False,
):
    """
    Run benchmark evaluation on deep_research_bench queries.

    Args:
        limit: Maximum number of queries to process
        output_dir: Output directory for results
        resume: Resume from existing results file
    """
    benchmark_start = datetime.now()

    logger.info("=" * 80)
    logger.info("Starting Deep Research Benchmark Evaluation")
    logger.info(f"Start time: {benchmark_start.strftime('%Y-%m-%d %H:%M:%S')}")
    logger.info(f"Resume mode: {resume}")
    logger.info("=" * 80)

    query_file = benchmark_dir / "data" / "prompt_data" / "query.jsonl"

    if not query_file.exists():
        logger.error(f"Query file not found: {query_file}")
        raise FileNotFoundError(f"Query file not found: {query_file}")

    all_queries = load_jsonl(str(query_file))
    queries = [q for q in all_queries if q.get("language") == "en"]

    if limit:
        queries = queries[:limit]

    logger.info(f"Loaded {len(queries)} English queries from benchmark")
    if limit:
        logger.info(f"Limited to first {limit} queries")

    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)

    output_file = output_path / "deep_research_results.jsonl"

    existing_results = {}
    if resume and output_file.exists():
        logger.info(f"Resume mode: Loading existing results from {output_file}")
        with open(output_file, encoding="utf-8") as f:
            for line in f:
                if line.strip():
                    result = json.loads(line)
                    existing_results[result["id"]] = result
        logger.info(f"Found {len(existing_results)} existing results")

    results = []
    processed_ids = set(existing_results.keys())

    for i, query_data in enumerate(queries, 1):
        query_id = query_data.get("id")
        prompt = query_data.get("prompt")

        if query_id in processed_ids:
            logger.info(f"[{i}/{len(queries)}] Skipping query {query_id} (already processed)")
            results.append(existing_results[query_id])
            continue

        logger.info(f"\n{'='*80}")
        logger.info(f"[{i}/{len(queries)}] Processing query {query_id}")
        logger.info(f"{'='*80}")
        logger.info(f"Prompt: {prompt[:200]}{'...' if len(prompt) > 200 else ''}")

        result = await run_single_research(prompt, query_id)
        results.append(result)

        if resume:
            with open(output_file, "a", encoding="utf-8") as f:
                f.write(json.dumps(result, ensure_ascii=False) + "\n")

        if "error" in result:
            logger.error(f"Query {query_id} failed: {result['error']}")
        else:
            duration = result["timing"]["duration_seconds"]
            word_count = result["metadata"]["word_count"]
            logger.info(f"Query {query_id} completed successfully")
            logger.info(f"  Duration: {duration:.1f}s")
            logger.info(f"  Word count: {word_count}")

    if not resume:
        with open(output_file, "w", encoding="utf-8") as f:
            for result in results:
                f.write(json.dumps(result, ensure_ascii=False) + "\n")

    successful = [r for r in results if "error" not in r]
    failed = [r for r in results if "error" in r]

    benchmark_end = datetime.now()
    total_duration = (benchmark_end - benchmark_start).total_seconds()

    logger.info("\n" + "=" * 80)
    logger.info("Benchmark Evaluation Complete")
    logger.info("=" * 80)
    logger.info(f"Results saved to: {output_file}")
    logger.info(f"Total queries: {len(results)}")
    logger.info(f"Successful: {len(successful)}")
    logger.info(f"Failed: {len(failed)}")
    logger.info(f"Total time: {total_duration:.1f}s ({total_duration/60:.1f} minutes)")

    if successful:
        avg_duration = sum(r["timing"]["duration_seconds"] for r in successful) / len(successful)
        avg_words = sum(r["metadata"]["word_count"] for r in successful) / len(successful)

        logger.info("\nStatistics (successful queries):")
        logger.info(f"  Average duration: {avg_duration:.1f}s")
        logger.info(f"  Average word count: {avg_words:.0f}")
        logger.info(f"  Throughput: {len(successful) / total_duration * 3600:.1f} queries/hour")

    if failed:
        logger.warning(f"\nFailed queries: {[r['id'] for r in failed]}")

    logger.info("=" * 80)


def main():
    parser = argparse.ArgumentParser(
        description="Run deep-research on deep_research_bench (English queries only)",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python run_benchmark.py --limit 5
  python run_benchmark.py --limit 10 --output-dir results/test_run
  python run_benchmark.py --limit 50 --resume
        """,
    )

    parser.add_argument(
        "--limit",
        type=int,
        default=None,
        help="Maximum number of queries to process (default: all)",
    )

    parser.add_argument(
        "--output-dir",
        default="evaluation/results",
        help="Output directory for results (default: evaluation/results)",
    )

    parser.add_argument(
        "--resume",
        action="store_true",
        help="Resume from existing results file (skip already processed queries)",
    )

    args = parser.parse_args()

    try:
        asyncio.run(
            run_benchmark(
                limit=args.limit,
                output_dir=args.output_dir,
                resume=args.resume,
            )
        )
        return 0
    except KeyboardInterrupt:
        logger.info("\nBenchmark interrupted by user")
        return 1
    except Exception as e:
        logger.error(f"Benchmark failed: {e}", exc_info=True)
        return 1


if __name__ == "__main__":
    sys.exit(main())
