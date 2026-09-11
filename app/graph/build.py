"""Wires the nodes into one StateGraph with the sqlite checkpointer.

Does: build_graph() -> compiled graph. make_flowchart.py calls compiled.get_graph().draw_mermaid().
Does not: run anything. app/graph/service.py runs it.
"""
import sqlite3

from langgraph.checkpoint.sqlite import SqliteSaver
from langgraph.graph import END, START, StateGraph

from app import config
from app.graph import nodes, nodes_answer
from app.graph.state import GraphState

_compiled = None


def build_graph():
    """route -> specialist (fan out per corpus) -> verify -> recall_memory -> decide -> escalate | customer_service."""
    graph = StateGraph(GraphState)
    graph.add_node("route", nodes.route)
    graph.add_node("specialist", nodes.specialist)
    graph.add_node("verify", nodes.verify)
    graph.add_node("recall_memory", nodes_answer.recall_memory)
    graph.add_node("decide", nodes_answer.decide)
    graph.add_node("escalate", nodes_answer.escalate)
    graph.add_node("customer_service", nodes_answer.customer_service)
    graph.add_edge(START, "route")
    graph.add_conditional_edges("route", nodes.fan_out, ["specialist", "verify"])
    graph.add_edge("specialist", "verify")
    graph.add_edge("verify", "recall_memory")
    graph.add_edge("recall_memory", "decide")
    graph.add_conditional_edges("decide", nodes_answer.next_step, ["escalate", "customer_service"])
    graph.add_edge("escalate", END)
    graph.add_edge("customer_service", END)
    return graph.compile(checkpointer=checkpointer())


def checkpointer() -> SqliteSaver:
    """Sqlite checkpointer under store/, so a thread survives a process restart."""
    config.CHECKPOINT_DB.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(config.CHECKPOINT_DB), check_same_thread=False)
    return SqliteSaver(conn)


def compiled():
    """The one compiled graph per process."""
    global _compiled
    if _compiled is None:
        _compiled = build_graph()
    return _compiled
