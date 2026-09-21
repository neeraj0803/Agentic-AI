from langgraph.graph import (
    StateGraph,
    END
)

from .state import PRDState

from .nodes.context_analyzer_node import (
    context_analyzer_node
)


def build_graph():

    graph = StateGraph(
        PRDState
    )

    graph.add_node(
        "context_analyzer",
        context_analyzer_node
    )

    graph.set_entry_point(
        "context_analyzer"
    )

    graph.add_edge(
        "context_analyzer",
        END
    )

    return graph.compile()
