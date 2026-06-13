import argparse
import os
import json
import sys

# Add src directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from workflow import create_workflow
from schema import InvoiceState

def main():
    parser = argparse.ArgumentParser(description="Invoice Compliance Validator")
    parser.add_argument("--input", required=True, help="Path to input invoice file (JSON for now)")
    parser.add_argument("--output", default=None, help="Path to save output JSON (default: result/output/filename.json)")
    args = parser.parse_args()

    if not os.path.exists(args.input):
        print(f"Error: Input file {args.input} not found.")
        return

    # Determine output path
    if args.output is None:
        # Default output path: result/output/[input_filename_without_extension]_result.json
        input_filename = os.path.basename(args.input)
        input_name_only = os.path.splitext(input_filename)[0]
        output_filename = f"{input_name_only}_result.json"
        args.output = os.path.join("result", "output", output_filename)

    # Create the workflow
    workflow = create_workflow()

    # Initialize state
    initial_state = InvoiceState(raw_file_path=args.input)

    # Run the workflow
    print(f"Processing invoice: {args.input}...")
    result = workflow.invoke(initial_state.model_dump())

    # If result is a dict, we might need to convert it back to InvoiceState for generate_output_json
    # or update generate_output_json to handle dicts.
    # For now, let's reconstruct the state object to keep ReporterAgent clean.
    final_state = InvoiceState(**result)

    from agents.report_builder import ReporterAgent
    reporter = ReporterAgent()
    output_json = reporter.generate_output_json(final_state)

    # Ensure output directory exists
    os.makedirs(os.path.dirname(args.output), exist_ok=True)

    with open(args.output, 'w') as f:
        json.dump(output_json, f, indent=2)

    print(f"Processing complete. Decision: {final_state.overall_decision}")
    print(f"Output saved to: {args.output}")

if __name__ == "__main__":
    main()
