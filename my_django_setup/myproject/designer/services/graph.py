from collections import defaultdict

from designer.models import ManufacturingStep, StepDependency


def validate_dag(step_ids, edges):
    """Return True if the graph is a DAG (no cycles). Uses Kahn's algorithm."""
    adj = defaultdict(list)
    in_degree = defaultdict(int)
    for sid in step_ids:
        in_degree[sid] = 0

    for e in edges:
        adj[e["from"]].append(e["to"])
        in_degree[e["to"]] += 1

    queue = [n for n in step_ids if in_degree[n] == 0]
    visited = 0
    while queue:
        node = queue.pop(0)
        visited += 1
        for neighbour in adj[node]:
            in_degree[neighbour] -= 1
            if in_degree[neighbour] == 0:
                queue.append(neighbour)

    return visited == len(step_ids)


def save_graph_from_payload(plan, data):
    """
    Apply node positions and dependency edges from a dict like
    {'nodes': [{'id', 'x', 'y'}, ...], 'edges': [{'from', 'to'}, ...]}.
    Returns None on success, or an error string on failure.
    """
    if not isinstance(data, dict):
        return "Invalid graph payload."

    nodes = data.get("nodes", [])
    edges = data.get("edges", [])
    plan_step_ids = set(plan.steps.values_list("pk", flat=True))

    for node in nodes:
        if node.get("id") not in plan_step_ids:
            continue
        ManufacturingStep.objects.filter(pk=node["id"]).update(
            position_x=node.get("x", 0),
            position_y=node.get("y", 0),
        )

    valid_edges = [
        e
        for e in edges
        if e.get("from") in plan_step_ids and e.get("to") in plan_step_ids
    ]

    if not validate_dag(plan_step_ids, valid_edges):
        return "The graph contains a cycle. Dependencies must form a DAG."

    StepDependency.objects.filter(from_step__plan=plan).delete()
    for e in valid_edges:
        StepDependency.objects.create(
            from_step_id=e["from"],
            to_step_id=e["to"],
        )
    return None
