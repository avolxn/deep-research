"""
Convert results to deep_research_bench evaluation format.

Usage:
    python process_results.py -i results/deep_research_results.jsonl -m deep-research
"""

import argparse
import json
import logging
from pathlib import Path

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)


def main():
    parser = argparse.ArgumentParser(description="Convert results to deep_research_bench evaluation format")

    parser.add_argument("--input", "-i", type=str, required=True, help="Path to results file (JSONL)")

    parser.add_argument(
        "--model-name",
        "-m",
        type=str,
        default="deep-research",
        help="Model name for output file (default: deep-research)",
    )

    parser.add_argument(
        "--output-dir",
        "-o",
        type=str,
        default="deep_research_bench/data/test_data/raw_data",
        help="Output directory for results file",
    )

    args = parser.parse_args()

    # Validate input file
    input_path = Path(args.input)
    if not input_path.exists():
        logger.error(f"Input file not found: {args.input}")
        return 1

    logger.info(f"Loading results from: {input_path}")

    # Load results
    results = []
    with open(input_path, encoding="utf-8") as f:
        for line_num, line in enumerate(f, 1):
            line = line.strip()
            if not line:
                continue

            try:
                data = json.loads(line)

                # Skip failed queries
                if "error" in data:
                    logger.warning(f"Skipping failed query {data.get('id')}: {data['error']}")
                    continue

                # Convert to benchmark format
                result = {"id": data["id"], "prompt": data["prompt"], "article": data["article"]}
                results.append(result)

            except (json.JSONDecodeError, KeyError) as e:
                logger.error(f"Error processing line {line_num}: {e}")
                continue

    if not results:
        logger.error("No valid results found")
        return 1

    logger.info(f"Loaded {len(results)} valid results")

    # Sort by ID
    results.sort(key=lambda x: x["id"])

    # Create output directory
    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    # Save in benchmark format
    output_file = output_dir / f"{args.model_name}.jsonl"
    with open(output_file, "w", encoding="utf-8") as f:
        for result in results:
            f.write(json.dumps(result, ensure_ascii=False) + "\n")

    logger.info(f"Results saved to: {output_file}")
    logger.info("\nNext steps:")
    logger.info("  cd deep_research_bench")
    logger.info(f"  python deepresearch_bench_race.py {args.model_name}")

    return 0


if __name__ == "__main__":
    exit(main())
