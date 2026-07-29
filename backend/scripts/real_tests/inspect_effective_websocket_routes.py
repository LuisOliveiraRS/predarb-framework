from __future__ import annotations

from collections import Counter

from fastapi.routing import (
    APIWebSocketRoute,
    iter_route_contexts,
)

from app.core.application import create_app


def resolve_effective_route(context):
    effective_route = getattr(
        context,
        "_effective_route",
        None,
    )

    starlette_route = getattr(
        effective_route,
        "starlette_route",
        None,
    )

    return (
        starlette_route
        or context.original_route
    )


def resolve_path(context):
    route = resolve_effective_route(context)

    return (
        getattr(route, "path", None)
        or context.path
        or getattr(
            context.original_route,
            "path",
            "",
        )
    )


def resolve_endpoint(context):
    route = resolve_effective_route(context)

    return (
        getattr(route, "endpoint", None)
        or getattr(
            context.original_route,
            "endpoint",
            None,
        )
    )


def endpoint_description(endpoint):
    if endpoint is None:
        return "<endpoint indisponível>"

    module = getattr(
        endpoint,
        "__module__",
        "<módulo desconhecido>",
    )

    name = getattr(
        endpoint,
        "__name__",
        endpoint.__class__.__name__,
    )

    return f"{module}.{name}"


app = create_app()

rows = []

for context in iter_route_contexts(
    app.routes
):
    if not isinstance(
        context.original_route,
        APIWebSocketRoute,
    ):
        continue

    path = resolve_path(context)
    endpoint = resolve_endpoint(context)

    rows.append(
        {
            "path": path,
            "name": (
                context.name
                or getattr(
                    context.original_route,
                    "name",
                    None,
                )
            ),
            "endpoint": endpoint_description(
                endpoint
            ),
            "raw_context_path": context.path,
            "original_path": getattr(
                context.original_route,
                "path",
                None,
            ),
        }
    )


print("Rotas WebSocket efetivas:")

for row in rows:
    print(row)


counts = Counter(
    row["path"]
    for row in rows
)


duplicates = {
    path: count
    for path, count in counts.items()
    if count > 1
}


print()
print(
    "Caminhos encontrados:",
    sorted(counts),
)

print(
    "Duplicações reais:",
    duplicates,
)


assert "/ws/live" in counts, counts
assert "/ws/router" in counts, counts
assert not duplicates, duplicates


print()
print(
    "WebSockets distintos e válidos."
)
