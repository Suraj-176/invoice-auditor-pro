import sys
import os

# Add src directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from langgraph.graph import StateGraph, END
from schema import InvoiceState
from agents.document_parser import ExtractorAgent
from agents.compliance_checker import ValidatorAgent
from agents.decision_resolver import ResolverAgent
from agents.report_builder import ReporterAgent

def create_workflow(config: dict = None):
    # Initialize agents with dynamic config
    extractor = ExtractorAgent(config=config)
    validator = ValidatorAgent()
    resolver = ResolverAgent()
    reporter = ReporterAgent()

    # Define the graph
    workflow = StateGraph(InvoiceState)

    # Add nodes
    workflow.add_node("extractor", extractor.process)
    workflow.add_node("validator", validator.process)
    workflow.add_node("resolver", resolver.process)
    workflow.add_node("reporter", reporter.process)

    # Define edges
    workflow.set_entry_point("extractor")
    workflow.add_edge("extractor", "validator")
    workflow.add_edge("validator", "resolver")
    workflow.add_edge("resolver", "reporter")
    workflow.add_edge("reporter", END)

    return workflow.compile()

if __name__ == "__main__":
    app = create_workflow()
    print("Workflow Graph Compiled Successfully.")
