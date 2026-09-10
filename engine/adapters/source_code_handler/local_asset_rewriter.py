from __future__ import annotations

import tinycss2

_SRCSET_ATTRIBUTES = {"srcset", "data-srcset"}


def extract_reference_candidates(
    value: str | None,
    attribute_name: str | None = None,
) -> list[str]:
    try:
        if not (text := str(value or "").strip()):
            return []

        match str(attribute_name or "").casefold():
            case attr if attr in _SRCSET_ATTRIBUTES:
                return [
                    parts[0]
                    for item in text.split(",")
                    if (parts := item.split()) and not parts[0].startswith("#")
                ]
            case attr if attr != "":
                candidate = text.strip("\"'")
                return [candidate] if candidate and not candidate.startswith("#") else []
            case _:
                pending = tinycss2.parse_component_value_list(
                    text,
                    skip_comments=True,
                )
                candidates: set[str] = set()

                while pending:
                    token = pending.pop(0)
                    token_type = getattr(token, "type", "")
                    token_name = str(
                        getattr(
                            token,
                            "lower_name",
                            getattr(token, "name", ""),
                        )
                    ).casefold()

                    if token_type == "url":
                        candidates.add(str(token.value))
                    elif token_type == "function" and token_name == "url":
                        candidates.add(
                            tinycss2.serialize(token.arguments)
                            .strip()
                            .strip("\"'")
                        )
                    elif isinstance(
                        nested := getattr(
                            token,
                            "content",
                            getattr(token, "arguments", None),
                        ),
                        list,
                    ):
                        pending.extend(nested)

                return sorted(
                    candidate
                    for candidate in candidates
                    if candidate and not candidate.startswith("#")
                )
    except Exception:
        return []


def rewrite_reference_candidates(
    value: str | None,
    new_path: str,
    attribute_name: str | None = None,
    old_path: str | None = None,
) -> str:
    try:
        if not (text := str(value or "").strip()):
            return ""

        target_path = str(old_path or "").strip().strip("\"'")

        match str(attribute_name or "").casefold():
            case attr if attr in _SRCSET_ATTRIBUTES:
                new_items = []
                for item in text.split(","):
                    parts = item.split()
                    if (
                        parts
                        and not parts[0].startswith("#")
                        and (not target_path or parts[0] == target_path)
                    ):
                        parts[0] = new_path
                        new_items.append(" ".join(parts))
                    else:
                        new_items.append(item.strip())
                return ", ".join(new_items)

            case attr if attr != "":
                current = text.strip("\"'")
                if current.startswith("#") or (target_path and current != target_path):
                    return text
                return new_path

            case _:
                tokens = tinycss2.parse_component_value_list(
                    text,
                    skip_comments=True,
                )

                def update_tokens(token_list: list[object]) -> None:
                    for index, token in enumerate(token_list):
                        token_type = getattr(token, "type", "")
                        token_name = str(
                            getattr(
                                token,
                                "lower_name",
                                getattr(token, "name", ""),
                            )
                        ).casefold()

                        if token_type == "url":
                            current = str(token.value).strip()
                            if (
                                not current.startswith("#")
                                and (not target_path or current == target_path)
                            ):
                                token.value = new_path
                                token.representation = f"url({new_path})"
                        elif token_type == "function" and token_name == "url":
                            current = (
                                tinycss2.serialize(token.arguments)
                                .strip()
                                .strip("\"'")
                            )
                            if (
                                not current.startswith("#")
                                and (not target_path or current == target_path)
                            ):
                                replacement = tinycss2.parse_component_value_list(
                                    f"url({new_path})",
                                    skip_comments=True,
                                )
                                if replacement:
                                    token_list[index] = replacement[0]
                        elif isinstance(
                            nested := getattr(
                                token,
                                "content",
                                getattr(token, "arguments", None),
                            ),
                            list,
                        ):
                            update_tokens(nested)

                update_tokens(tokens)
                return tinycss2.serialize(tokens)

    except Exception:
        return str(value or "")
