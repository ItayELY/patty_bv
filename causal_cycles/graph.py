"""A tiny dependency-free directed graph with cycle/SCC detection.

We avoid pulling in networkx (not part of this project's environment) since
all we need is: add nodes/edges, find self-loops, and find strongly
connected components with more than one node (i.e. non-trivial cycles).
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Set, Tuple


@dataclass
class DiGraph:
    nodes: Set[str] = field(default_factory=set)
    # (source, target) -> set of edge labels (e.g. action names) causing it
    edges: Dict[Tuple[str, str], Set[str]] = field(default_factory=dict)

    def add_node(self, node: str) -> None:
        self.nodes.add(node)

    def add_edge(self, source: str, target: str, label: str = "") -> None:
        self.nodes.add(source)
        self.nodes.add(target)
        self.edges.setdefault((source, target), set())
        if label:
            self.edges[(source, target)].add(label)

    def successors(self, node: str) -> List[str]:
        return sorted({t for (s, t) in self.edges if s == node})

    def self_loops(self) -> List[str]:
        return sorted(n for n in self.nodes if (n, n) in self.edges)

    def strongly_connected_components(self) -> List[List[str]]:
        """Tarjan's SCC algorithm, iterative to avoid recursion-depth issues."""
        index_counter = [0]
        stack: List[str] = []
        on_stack: Set[str] = set()
        indices: Dict[str, int] = {}
        lowlink: Dict[str, int] = {}
        result: List[List[str]] = []

        adjacency: Dict[str, List[str]] = {n: self.successors(n) for n in self.nodes}

        for start in sorted(self.nodes):
            if start in indices:
                continue

            # work_stack holds (node, iterator index into adjacency[node])
            work_stack: List[Tuple[str, int]] = [(start, 0)]
            indices[start] = lowlink[start] = index_counter[0]
            index_counter[0] += 1
            stack.append(start)
            on_stack.add(start)

            while work_stack:
                node, i = work_stack[-1]
                neighbors = adjacency[node]
                if i < len(neighbors):
                    work_stack[-1] = (node, i + 1)
                    succ = neighbors[i]
                    if succ not in indices:
                        indices[succ] = lowlink[succ] = index_counter[0]
                        index_counter[0] += 1
                        stack.append(succ)
                        on_stack.add(succ)
                        work_stack.append((succ, 0))
                    elif succ in on_stack:
                        lowlink[node] = min(lowlink[node], indices[succ])
                else:
                    work_stack.pop()
                    if work_stack:
                        parent = work_stack[-1][0]
                        lowlink[parent] = min(lowlink[parent], lowlink[node])
                    if lowlink[node] == indices[node]:
                        component = []
                        while True:
                            w = stack.pop()
                            on_stack.discard(w)
                            component.append(w)
                            if w == node:
                                break
                        result.append(component)

        return result

    def cycles(self) -> List[List[str]]:
        """Non-trivial cycles: SCCs with >1 node, plus single-node self-loops."""
        cycles = [c for c in self.strongly_connected_components() if len(c) > 1]
        cycles.extend([n] for n in self.self_loops())
        return cycles

    def cyclic_nodes(self) -> Set[str]:
        return {n for c in self.cycles() for n in c}

    def cyclic_edges(self) -> Set[Tuple[str, str]]:
        """Edges that lie on an actual cycle (both endpoints in the *same*
        non-trivial SCC, or a self-loop) - stricter than "both endpoints are
        cyclic somewhere", which would wrongly span two disjoint cycles."""
        comps = self.strongly_connected_components()
        comp_of: Dict[str, int] = {}
        comp_size: Dict[int, int] = {}
        for i, comp in enumerate(comps):
            comp_size[i] = len(comp)
            for n in comp:
                comp_of[n] = i

        result = set()
        for (s, t) in self.edges:
            if s == t or (comp_of.get(s) == comp_of.get(t) and comp_size[comp_of[s]] > 1):
                result.add((s, t))
        return result

    def to_dot(self, name: str = "influence") -> str:
        cyclic_nodes = self.cyclic_nodes()
        cyclic_edges = self.cyclic_edges()
        lines = [f"digraph {name} {{", "  rankdir=LR;"]
        for n in sorted(self.nodes):
            color = ' color="red" fontcolor="red"' if n in cyclic_nodes else ""
            lines.append(f'  "{n}"[{color.strip()}];' if color else f'  "{n}";')
        for (s, t), labels in sorted(self.edges.items()):
            cyclic_edge = (s, t) in cyclic_edges
            attrs = []
            if labels:
                attrs.append(f'label="{", ".join(sorted(labels))}"')
            if cyclic_edge:
                attrs.append('color="red"')
            attr_str = f" [{', '.join(attrs)}]" if attrs else ""
            lines.append(f'  "{s}" -> "{t}"{attr_str};')
        lines.append("}")
        return "\n".join(lines)
