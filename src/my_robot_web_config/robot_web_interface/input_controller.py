from __future__ import annotations

from collections.abc import Callable


class InputController:
    """Maps touch-like taps and dev shortcuts into the bounded Phase 2 actions."""

    def __init__(
        self,
        *,
        root,
        canvas,
        layout_shell,
        on_tab_selected: Callable[[str], None],
        on_action: Callable[[str], None],
    ) -> None:
        self.root = root
        self.canvas = canvas
        self.layout_shell = layout_shell
        self.on_tab_selected = on_tab_selected
        self.on_action = on_action

    def install(self) -> None:
        self.canvas.bind("<Button-1>", self._handle_tap)
        self.root.bind("i", lambda _event: self.on_action("view_info"))
        self.root.bind("m", lambda _event: self.on_action("view_map"))
        self.root.bind("<Return>", lambda _event: self.on_action("confirm_understanding"))
        self.root.bind("h", lambda _event: self.on_tab_selected("help"))

    def _handle_tap(self, event) -> None:
        tab_key = self._find_target(self.layout_shell.tab_hitboxes, event.x, event.y)
        if tab_key is not None:
            self.on_tab_selected(tab_key)
            return

        action_key = self._find_target(self.layout_shell.action_hitboxes, event.x, event.y)
        if action_key is not None:
            self.on_action(action_key)

    @staticmethod
    def _find_target(hitboxes: dict[str, tuple[int, int, int, int]], x: int, y: int) -> str | None:
        for key, (x1, y1, x2, y2) in hitboxes.items():
            if x1 <= x <= x2 and y1 <= y <= y2:
                return key
        return None
