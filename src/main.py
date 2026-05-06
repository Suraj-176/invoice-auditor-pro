import argparse
import os
import json
from src.workflow import create_workflow
from src.schema import InvoiceState

def main():
    parser = argparse.ArgumentParser(description="Invoice Compliance Validator")
    parser.add_argument("--input", required=True, help="Path to input invoice file (JSON for now)")
    parser.add_argument("--output", required=True, help="Path to save output JSON")
    args = parser.parse_args()

    if not os.path.exists(args.input):
        print(f"Error: Input file {args.input} not found.")
        return

    # Create the workflow
    workflow = create_workflow()

    # Initialize state
    initial_state = InvoiceState(raw_file_path=args.input)

    # Run the workflow
    print(f"Processing invoice: {args.input}...")
    result = workflow.invoke(initial_state.model_dump())

    # Ensure output directory exists
    os.makedirs(os.path.dirname(args.output), exist_ok=True)

    # If result is a dict, we might need to convert it back to InvoiceState for generate_output_json
    # or update generate_output_json to handle dicts.
    # For now, let's reconstruct the state object to keep ReporterAgent clean.
    final_state = InvoiceState(**result)

    from src.agents.reporter import ReporterAgent
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
