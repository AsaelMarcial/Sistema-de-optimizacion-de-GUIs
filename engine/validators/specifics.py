from typing import Any

from engine.domain.models.element import Element


def is_approved(
    current_node: dict[str, Any],
    approved: dict[int, tuple[dict[str, Any], Element]],
    stylesheet_owner_backend_node_ids: set[int],
    layout_nodes: dict[int, dict[str, Any]],
) -> bool:
    backend_node_id = int(current_node.get("backendNodeId") or 0)
    tag_name = str(current_node.get("nodeName") or "").strip().lower()
    children_nodes = (
        (current_node.get("children") or [])
        + (current_node.get("pseudoElements") or [])
    )
    attributes = current_node.get("attributes") or []
    node_value = str(current_node.get("nodeValue") or "").strip()
    has_approved_child = any(
        int(child.get("backendNodeId") or 0) in approved
        for child in children_nodes
    )

    return bool(
        backend_node_id > 0
        and tag_name != "#document"
        and (
            (
                tag_name in {"html", "body"}
                and (
                    backend_node_id in layout_nodes
                    or has_approved_child
                )
            )
            or tag_name.startswith("::")
            or (tag_name == "#text" and bool(node_value))
            or tag_name == "meta" and "color-scheme" in attributes
            or backend_node_id in stylesheet_owner_backend_node_ids
            or backend_node_id in layout_nodes
            or has_approved_child
        )
    )
