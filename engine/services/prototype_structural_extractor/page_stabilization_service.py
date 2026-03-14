from __future__ import annotations

from typing import Any


def wait_for_render_stability(
    page: Any,
    *,
    wait_after_load_ms: int,
    stability_interval_ms: int,
    max_checks: int,
    scroll_step_px: int,
) -> dict:
    page.wait_for_load_state("load")
    page.wait_for_function(
        """
        () => {
          if (!document.fonts || !document.fonts.status) {
            return true;
          }
          return document.fonts.status === 'loaded';
        }
        """
    )
    page.wait_for_function(
        """
        async () => {
          const images = Array.from(document.images || []);
          await Promise.all(images.map((image) => image.decode ? image.decode().catch(() => null) : Promise.resolve()));
          return true;
        }
        """
    )
    if wait_after_load_ms > 0:
        page.wait_for_timeout(wait_after_load_ms)

    page.evaluate(
        """
        async (stepPx) => {
          const root = document.scrollingElement || document.documentElement;
          const maxScroll = Math.max(0, root.scrollHeight - window.innerHeight);
          const step = Math.max(stepPx, 1);
          for (let offset = 0; offset <= maxScroll; offset += step) {
            window.scrollTo(0, offset);
            await new Promise((resolve) => window.requestAnimationFrame(() => resolve()));
          }
          window.scrollTo(0, 0);
        }
        """,
        scroll_step_px,
    )

    previous = None
    stable_count = 0
    samples: list[dict] = []
    for _ in range(max_checks):
        current = page.evaluate(
            """
            () => {
              const root = document.scrollingElement || document.documentElement;
              return {
                width: Math.max(root.scrollWidth, document.documentElement.scrollWidth, document.body ? document.body.scrollWidth : 0),
                height: Math.max(root.scrollHeight, document.documentElement.scrollHeight, document.body ? document.body.scrollHeight : 0),
                viewportWidth: window.innerWidth,
                viewportHeight: window.innerHeight,
                scrollX: window.scrollX,
                scrollY: window.scrollY,
              };
            }
            """
        )
        samples.append(current)
        if current == previous:
            stable_count += 1
            if stable_count >= 1:
                break
        else:
            stable_count = 0
            previous = current
        page.wait_for_timeout(stability_interval_ms)

    return samples[-1] if samples else {}
