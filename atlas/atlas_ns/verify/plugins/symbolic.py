"""Symbolic verifier (#3): networkx over the profile's triplet graph.

The graph is the profile's OWN symbolic memory (seeded from NS when
present). Nodes are triplet ids; edges carry {supports | contradicts}.
A contradiction against a cited triplet is a HARD BLOCK — the one
verifier that can veto on its own. Every verdict cites triplet ids.

Claim context contract:
  triplets : list[{subject, predicate, object}]  the claim's atoms
"""

from __future__ import annotations

import networkx as nx

from atlas_ns.verify.composite import Verdict


class SymbolicVerifier:
    name = "symbolic"

    def __init__(self, graph: nx.DiGraph | dict | None = None) -> None:
        if isinstance(graph, nx.DiGraph) or graph is None:
            self.graph = graph if graph is not None else nx.DiGraph()
        else:  # serialized profile graph: {"nodes": [...], "edges": [...]}
            g = nx.DiGraph()
            for node in graph.get("nodes", []):
                g.add_node(node["id"], **{k: v for k, v in node.items()
                                          if k != "id"})
            for edge in graph.get("edges", []):
                g.add_edge(edge["source"], edge["target"],
                           rel=edge.get("rel", "supports"))
            self.graph = g

    # -- graph helpers ---------------------------------------------------------
    @staticmethod
    def triplet_key(t: dict) -> tuple:
        return (str(t.get("subject", "")).lower(),
                str(t.get("predicate", "")).lower(),
                str(t.get("object", "")).lower())

    def node_by_key(self, key: tuple) -> str | None:
        for node, data in self.graph.nodes(data=True):
            if self.triplet_key({
                    "subject": data.get("subject", node),
                    "predicate": data.get("predicate", ""),
                    "object": data.get("object", "")}) == key:
                return node
        return None

    # -- verify ------------------------------------------------------------------
    def verify(self, claim: str, context: dict | None = None) -> Verdict:
        atoms = (context or {}).get("triplets", [])
        if not atoms:
            return Verdict(self.name, 0.5,
                           "no triplets to check: neutral vote",
                           hard_block=False)

        claim_low = str(claim or "").lower()
        supports, unknown = 0, 0
        for atom in atoms:
            key = self.triplet_key(atom)
            node = self.node_by_key(key)
            if node is None:
                unknown += 1
                continue
            contradicts = [nbr for nbr in self.graph.successors(node)
                           if self.graph[node][nbr].get("rel")
                           == "contradicts"]
            if contradicts:
                cited = self.graph.nodes[node]
                return Verdict(
                    self.name, 0.0,
                    f"contradicts triplet {node} "
                    f"({cited.get('subject')} {cited.get('predicate')} "
                    f"{cited.get('object')}); conflicting nodes: "
                    f"{sorted(contradicts)}",
                    hard_block=True)
            # answer-text grounding: the graph knows the family; the
            # answer must actually reference it (def <subject> or the
            # subject tokens). Otherwise the vote stays neutral.
            subject = str(atom.get("subject", "")).lower()
            if subject and (subject in claim_low
                            or any(tok in claim_low for tok in
                                   subject.split("_") if len(tok) > 3)):
                supports += 1
            else:
                unknown += 1

        if supports and not unknown:
            score, evidence = 1.0, f"all {supports} atoms supported in graph"
        elif supports:
            # partial support sits STRICTLY between neutral (0.5) and full
            score = 0.5 + 0.5 * (supports / (supports + unknown))
            evidence = (f"{supports} supported, {unknown} unknown: partial "
                        f"graph support")
        else:
            score, evidence = 0.5, "no atom present in graph: neutral"
        return Verdict(self.name, score, evidence, hard_block=False)
