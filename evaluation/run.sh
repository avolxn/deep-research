#!/bin/bash
# Full pipeline for deep_research_bench evaluation
# Usage: ./run.sh [--limit N] [--evaluator MODEL_NAME] [--resume]

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
RESULTS_DIR="$SCRIPT_DIR/results"
LIMIT=""
RESUME=""
EVALUATOR=""

# Parse arguments
while [[ $# -gt 0 ]]; do
    case $1 in
        --limit)
            LIMIT="--limit $2"
            shift 2
            ;;
        --evaluator)
            EVALUATOR="--model $2"
            shift 2
            ;;
        --resume)
            RESUME="--resume"
            shift
            ;;
        *)
            echo "Unknown option: $1"
            echo "Usage: $0 [--limit N] [--evaluator MODEL_NAME] [--resume]"
            exit 1
            ;;
    esac
done

echo "=========================================="
echo "Deep Research Benchmark Evaluation"
echo "=========================================="
echo "Results dir: $RESULTS_DIR"
if [ -n "$LIMIT" ]; then
    echo "Limit: $LIMIT"
fi
if [ -n "$EVALUATOR" ]; then
    echo "Evaluator model: $EVALUATOR"
else
    echo "Evaluator model: gpt-oss-120b (default)"
fi
if [ -n "$RESUME" ]; then
    echo "Resume mode: enabled"
fi
echo "=========================================="

# Create results directory
mkdir -p "$RESULTS_DIR"

# Step 1: Generate research articles
echo ""
echo "Step 1/3: Generating research articles..."
python "$SCRIPT_DIR/run_benchmark.py" $LIMIT $RESUME

# Step 2: Convert to benchmark format
echo ""
echo "Step 2/3: Converting results to benchmark format..."
python "$SCRIPT_DIR/process_results.py" \
    --input "$RESULTS_DIR/deep_research_results.jsonl" \
    --model-name "deep-research"

# Step 3: Run evaluation
echo ""
echo "Step 3/3: Running benchmark evaluation..."
python "$SCRIPT_DIR/evaluate_benchmark.py" $LIMIT $EVALUATOR

echo ""
echo "=========================================="
echo "Pipeline completed successfully!"
echo "=========================================="
echo "Results location:"
echo "  - Generated articles: $RESULTS_DIR/deep_research_results.jsonl"
echo "  - Benchmark format: ../deep_research_bench/data/test_data/raw_data/deep-research.jsonl"
echo "  - Evaluation results: ../deep_research_bench/results/race/deep-research/"
echo "=========================================="
