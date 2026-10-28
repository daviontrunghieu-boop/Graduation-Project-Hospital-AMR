from __future__ import annotations

import math
from collections.abc import Sequence
from typing import TYPE_CHECKING

if __package__ in (None, ""):
    import visual_tokens as vt
else:
    from . import visual_tokens as vt

if TYPE_CHECKING:
    from panel_tabs import PanelTabSpec, PanelViewState


class RuntimeLayoutShell:
    """Static screen regions that keep the face stage separate from support surfaces."""

    def __init__(self, canvas) -> None:
        self.canvas = canvas
        self.tab_hitboxes: dict[str, tuple[int, int, int, int]] = {}
        self.action_hitboxes: dict[str, tuple[int, int, int, int]] = {}
        self.tab_nodes: list[tuple[str, int, int]] = []
        self.action_nodes: list[tuple[str, int, int]] = []
        self.map_overlay_tag = "map-overlay"

        self._create_scene_backdrop()
        self._create_panel_shell()
        self._create_map_shell()

    def set_view(
        self,
        view_state: "PanelViewState",
        tab_specs: Sequence["PanelTabSpec"],
        map_snapshot=None,
    ) -> None:
        palette = _panel_palette(view_state.active_tab)
        show_summary = False
        show_info_cards = False
        show_map = False
        show_header = False
        show_actions = False
        show_tabs = False
        visible_action_keys = _visible_action_keys(view_state.active_tab)
        self.tab_hitboxes.clear()
        self.action_hitboxes.clear()

        self._ensure_tab_nodes(tab_specs)
        self._ensure_action_nodes(view_state.actions)

        self.canvas.itemconfigure(self.panel_frame, state="hidden")
        self.canvas.itemconfigure(self.panel_inner, state="hidden")
        self.canvas.itemconfigure(
            self.panel_header,
            fill=palette["header_fill"],
            outline=palette["header_outline"],
            state="normal" if show_header else "hidden",
        )
        self.canvas.itemconfigure(
            self.panel_section_label,
            text=_summary_label(view_state.active_tab),
            fill=palette["accent_text"],
            state="normal" if show_header else "hidden",
        )
        self.canvas.itemconfigure(self.panel_title, state="normal" if show_header else "hidden")
        self.canvas.itemconfigure(self.panel_mode, state="normal" if show_header else "hidden")
        self.canvas.itemconfigure(
            self.summary_card,
            fill=palette["summary_fill"],
            outline=palette["summary_outline"],
            state="normal" if show_summary else "hidden",
        )
        self.canvas.itemconfigure(
            self.summary_label,
            fill=palette["accent_text"],
            state="normal" if show_summary else "hidden",
        )
        self.canvas.itemconfigure(
            self.summary_text,
            state="normal" if show_summary else "hidden",
        )
        self.canvas.itemconfigure(self.left_card, state="normal" if show_info_cards else "hidden")
        self.canvas.itemconfigure(self.right_card, state="normal" if show_info_cards else "hidden")
        self.canvas.itemconfigure(self.left_label, state="normal" if show_info_cards else "hidden")
        self.canvas.itemconfigure(self.right_label, state="normal" if show_info_cards else "hidden")
        self.canvas.itemconfigure(self.left_value, state="normal" if show_info_cards else "hidden")
        self.canvas.itemconfigure(self.right_value, state="normal" if show_info_cards else "hidden")
        self.canvas.itemconfigure(self.footer_text, state="hidden")

        map_state = "normal" if show_map else "hidden"
        self.canvas.itemconfigure(
            self.map_frame,
            fill=palette["map_fill"],
            outline=palette["map_outline"],
            width=2,
            state=map_state,
        )
        self.canvas.itemconfigure(self.map_heading, fill=palette["map_heading_fill"], state=map_state)
        self.canvas.itemconfigure(self.map_source, fill=palette["label_fill"], state=map_state)
        self.canvas.itemconfigure(self.map_caption, fill=palette["map_caption_fill"], state=map_state)

        for key, rect_id, text_id in self.tab_nodes:
            is_active = key == view_state.active_tab
            tab_visible = show_tabs
            self.canvas.itemconfigure(
                rect_id,
                fill=palette["tab_active_fill"] if is_active else palette["tab_idle_fill"],
                outline=palette["tab_active_outline"] if is_active else palette["tab_idle_outline"],
                width=2,
                state="normal" if tab_visible else "hidden",
            )
            self.canvas.itemconfigure(
                text_id,
                fill=palette["tab_active_text"] if is_active else palette["tab_idle_text"],
                state="normal" if tab_visible else "hidden",
            )
            if tab_visible:
                self.tab_hitboxes[key] = self._tab_bounds(key)

        for action_state, (key, rect_id, text_id) in zip(view_state.actions, self.action_nodes):
            highlight = action_state.active
            action_visible = show_actions and key in visible_action_keys
            self.canvas.itemconfigure(
                rect_id,
                fill=palette["action_active_fill"] if highlight else palette["action_idle_fill"],
                outline=palette["action_active_outline"] if highlight else palette["action_idle_outline"],
                width=2,
                state="normal" if action_visible else "hidden",
            )
            self.canvas.itemconfigure(
                text_id,
                text=action_state.label,
                fill=palette["action_active_text"] if highlight else palette["action_idle_text"],
                state="normal" if action_visible else "hidden",
            )
            if action_visible:
                self.action_hitboxes[key] = self._action_bounds(key)

        self.canvas.itemconfigure(self.panel_title, text=view_state.title, fill=vt.TEXT_PRIMARY)
        self.canvas.itemconfigure(self.panel_mode, text=view_state.mode_label, fill=palette["accent_text"])
        self.canvas.itemconfigure(self.summary_text, text=view_state.summary, fill=palette["summary_text_fill"])
        self.canvas.itemconfigure(self.left_label, text=view_state.left_label, fill=palette["label_fill"])
        self.canvas.itemconfigure(self.left_value, text=view_state.left_value, fill=palette["value_fill"])
        self.canvas.itemconfigure(self.right_label, text=view_state.right_label, fill=palette["label_fill"])
        self.canvas.itemconfigure(self.right_value, text=view_state.right_value, fill=palette["value_fill"])
        self.canvas.itemconfigure(self.left_card, fill=palette["card_fill"], outline=palette["card_outline"])
        self.canvas.itemconfigure(self.right_card, fill=palette["card_fill"], outline=palette["card_outline"])
        self.canvas.itemconfigure(self.map_heading, text=view_state.map_title)
        self.canvas.itemconfigure(self.map_caption, text=view_state.map_caption)

        self._render_map_snapshot(map_snapshot, visible=show_map)

    def _create_scene_backdrop(self) -> None:
        self.canvas.create_rectangle(
            0,
            0,
            vt.WINDOW_WIDTH,
            vt.WINDOW_HEIGHT,
            fill=vt.BACKGROUND,
            outline="",
        )
        self.canvas.create_oval(
            52,
            18,
            vt.WINDOW_WIDTH - 52,
            566,
            fill="#092132",
            outline="",
        )
        self.canvas.create_rectangle(
            36,
            24,
            vt.WINDOW_WIDTH - 36,
            536,
            fill=vt.SURFACE_DEEP,
            outline="",
        )

    def _create_panel_shell(self) -> None:
        self.panel_frame = self.canvas.create_rectangle(
            *vt.PANEL_BOUNDS,
            fill="#030912",
            outline=vt.PANEL_OUTLINE,
            width=3,
        )
        self.panel_inner = self.canvas.create_rectangle(
            vt.PANEL_BOUNDS[0] + 12,
            vt.PANEL_BOUNDS[1] + 12,
            vt.PANEL_BOUNDS[2] - 12,
            vt.PANEL_BOUNDS[3] - 12,
            fill=vt.PANEL_FILL,
            outline="",
        )
        self.panel_header = self.canvas.create_rectangle(
            *vt.PANEL_HEADER_BOUNDS,
            fill=vt.CARD_FILL,
            outline=vt.CARD_OUTLINE,
            width=2,
        )
        self.panel_section_label = self.canvas.create_text(
            vt.PANEL_HEADER_BOUNDS[0] + 18,
            vt.PANEL_HEADER_BOUNDS[1] + 14,
            anchor="nw",
            text="Thông tin hiện tại",
            fill=vt.ACCENT,
            font=("Helvetica", 10, "bold"),
        )
        self.panel_title = self.canvas.create_text(
            vt.PANEL_HEADER_BOUNDS[0] + 18,
            vt.PANEL_HEADER_BOUNDS[1] + 34,
            anchor="nw",
            text="Trang chờ",
            fill=vt.TEXT_PRIMARY,
            font=("Helvetica", 22, "bold"),
        )
        self.panel_mode = self.canvas.create_text(
            vt.PANEL_HEADER_BOUNDS[0] + 18,
            vt.PANEL_HEADER_BOUNDS[1] + 62,
            anchor="nw",
            text="Robot đang chờ bạn",
            fill=vt.ACCENT,
            font=("Helvetica", 11, "bold"),
        )

        self.summary_card = self.canvas.create_rectangle(
            *vt.SUMMARY_CARD_BOUNDS,
            fill=vt.CARD_FILL,
            outline=vt.CARD_OUTLINE,
            width=2,
        )
        self.summary_label = self.canvas.create_text(
            vt.SUMMARY_CARD_BOUNDS[0] + 16,
            vt.SUMMARY_CARD_BOUNDS[1] + 14,
            anchor="nw",
            text="Thông tin hiện tại",
            fill=vt.TEXT_MUTED,
            font=("Helvetica", 10, "bold"),
        )
        self.summary_text = self.canvas.create_text(
            vt.SUMMARY_CARD_BOUNDS[0] + 16,
            vt.SUMMARY_CARD_BOUNDS[1] + 34,
            anchor="nw",
            width=(vt.SUMMARY_CARD_BOUNDS[2] - vt.SUMMARY_CARD_BOUNDS[0]) - 32,
            text="Robot đang sẵn sàng hỗ trợ bạn.",
            fill=vt.TEXT_SOFT,
            font=("Helvetica", 11),
        )

        self.left_card, self.left_label, self.left_value = self._create_info_card(
            vt.QUEUE_CARD_BOUNDS,
            "Trạng thái",
            "Trang chờ",
        )
        self.right_card, self.right_label, self.right_value = self._create_info_card(
            vt.ROOM_CARD_BOUNDS,
            "Điểm đến",
            "Sẽ hiển thị khi có lượt",
        )

        self.footer_text = self.canvas.create_text(0, 0, text="", state="hidden")

    def _create_info_card(
        self,
        bounds: tuple[int, int, int, int],
        label: str,
        value: str,
    ) -> tuple[int, int, int]:
        card_id = self.canvas.create_rectangle(
            *bounds,
            fill=vt.CARD_FILL,
            outline=vt.CARD_OUTLINE,
            width=2,
        )
        label_id = self.canvas.create_text(
            bounds[0] + 14,
            bounds[1] + 14,
            anchor="nw",
            text=label,
            fill=vt.TEXT_MUTED,
            font=("Helvetica", 10, "bold"),
        )
        value_id = self.canvas.create_text(
            bounds[0] + 14,
            bounds[1] + 44,
            anchor="nw",
            width=(bounds[2] - bounds[0]) - 28,
            text=value,
            fill=vt.TEXT_PRIMARY,
            font=("Helvetica", 15, "bold"),
        )
        return (card_id, label_id, value_id)

    def _create_map_shell(self) -> None:
        x1, y1, x2, y2 = vt.MAP_BOUNDS
        self.map_frame = self.canvas.create_rectangle(
            x1,
            y1,
            x2,
            y2,
            fill=vt.MAP_FILL,
            outline=vt.CARD_OUTLINE,
            width=2,
        )
        self.map_heading = self.canvas.create_text(
            x1 + 14,
            y1 + 14,
            anchor="nw",
            text="Bản đồ chờ",
            fill=vt.TEXT_PRIMARY,
            font=("Helvetica", 13, "bold"),
        )
        self.map_source = self.canvas.create_text(
            x2 - 14,
            y1 + 16,
            anchor="ne",
            text="Bản đồ chờ hướng dẫn",
            fill=vt.TEXT_MUTED,
            font=("Helvetica", 9, "bold"),
        )
        self.map_caption = self.canvas.create_text(
            (x1 + x2) / 2,
            y2 - 18,
            width=368,
            justify="center",
            text="Khi có phòng khám, lối đi sẽ hiện tại đây để bạn nhìn nhanh.",
            fill=vt.TEXT_SOFT,
            font=("Helvetica", 10),
        )
        self._render_map_snapshot(None, visible=False)

    def _render_map_snapshot(self, map_snapshot, *, visible: bool) -> None:
        self.canvas.delete(self.map_overlay_tag)
        if not visible:
            return
        x1, y1, x2, y2 = vt.MAP_BOUNDS
        inset_x1 = x1 + 14
        inset_y1 = y1 + 42
        inset_x2 = x2 - 14
        inset_y2 = y2 - 38

        self.canvas.create_rectangle(
            inset_x1,
            inset_y1,
            inset_x2,
            inset_y2,
            fill=vt.MAP_FILL,
            outline=vt.MAP_GRID,
            width=1,
            tags=self.map_overlay_tag,
        )

        if map_snapshot is None:
            self.canvas.itemconfigure(self.map_source, text="Bản đồ đang chờ hướng dẫn")
            self._render_placeholder_map(inset_x1, inset_y1, inset_x2, inset_y2)
            return

        self.canvas.itemconfigure(
            self.map_source,
            text="Bản đồ đang cập nhật theo robot",
        )
        self._render_live_grid(inset_x1, inset_y1, inset_x2, inset_y2, map_snapshot)
        self._render_live_route(inset_x1, inset_y1, inset_x2, inset_y2, map_snapshot)
        self._render_robot_pose(inset_x1, inset_y1, inset_x2, inset_y2, map_snapshot)

    def _render_placeholder_map(self, x1: int, y1: int, x2: int, y2: int) -> None:
        for offset in range(x1, x2, 56):
            self.canvas.create_line(
                offset,
                y1,
                offset,
                y2,
                fill=vt.MAP_GRID,
                width=1,
                tags=self.map_overlay_tag,
            )
        for offset in range(y1, y2, 28):
            self.canvas.create_line(
                x1,
                offset,
                x2,
                offset,
                fill=vt.MAP_GRID,
                width=1,
                tags=self.map_overlay_tag,
            )
        route_points = [
            x1 + 18,
            y2 - 24,
            x1 + 86,
            y2 - 58,
            x1 + 182,
            y2 - 76,
            x2 - 44,
            y1 + 18,
        ]
        self.canvas.create_line(
            *route_points,
            fill=vt.MAP_ROUTE,
            width=3,
            smooth=True,
            tags=self.map_overlay_tag,
        )

    def _render_live_grid(self, x1: int, y1: int, x2: int, y2: int, map_snapshot) -> None:
        rows = tuple(getattr(map_snapshot, "grid_rows", ()))
        if not rows:
            return
        row_count = len(rows)
        col_count = max(len(row) for row in rows)
        cell_width = (x2 - x1) / max(col_count, 1)
        cell_height = (y2 - y1) / max(row_count, 1)
        color_map = {
            "#": "#355D78",
            "?": "#102033",
        }
        for row_index, row in enumerate(rows):
            for col_index, marker in enumerate(row):
                if marker == ".":
                    continue
                fill = color_map.get(marker, "#102033")
                left = x1 + (col_index * cell_width)
                top = y1 + (row_index * cell_height)
                self.canvas.create_rectangle(
                    left,
                    top,
                    left + cell_width,
                    top + cell_height,
                    fill=fill,
                    outline="",
                    tags=self.map_overlay_tag,
                )

    def _render_live_route(self, x1: int, y1: int, x2: int, y2: int, map_snapshot) -> None:
        route_points = tuple(getattr(map_snapshot, "route_points", ()))
        if len(route_points) < 2:
            return
        scaled_points: list[float] = []
        for point_x, point_y in route_points:
            scaled_points.extend(
                [
                    x1 + ((x2 - x1) * point_x),
                    y1 + ((y2 - y1) * point_y),
                ]
            )
        self.canvas.create_line(
            *scaled_points,
            fill=vt.MAP_ROUTE,
            width=4,
            smooth=True,
            tags=self.map_overlay_tag,
        )

    def _render_robot_pose(self, x1: int, y1: int, x2: int, y2: int, map_snapshot) -> None:
        pose = tuple(getattr(map_snapshot, "robot_pose", ()))
        if len(pose) != 3:
            return
        pose_x = x1 + ((x2 - x1) * pose[0])
        pose_y = y1 + ((y2 - y1) * pose[1])
        heading = math.radians(float(pose[2]))
        self.canvas.create_oval(
            pose_x - 7,
            pose_y - 7,
            pose_x + 7,
            pose_y + 7,
            fill=vt.MAP_NODE,
            outline="",
            tags=self.map_overlay_tag,
        )
        self.canvas.create_line(
            pose_x,
            pose_y,
            pose_x + (16 * math.cos(heading)),
            pose_y - (16 * math.sin(heading)),
            fill="#F9FCFF",
            width=3,
            tags=self.map_overlay_tag,
        )

    def _ensure_tab_nodes(self, tab_specs: Sequence["PanelTabSpec"]) -> None:
        if self.tab_nodes:
            return
        for spec in tab_specs:
            x1, y1, x2, y2 = self._tab_bounds(spec.key)
            rect_id = self.canvas.create_rectangle(
                x1,
                y1,
                x2,
                y2,
                fill=vt.CARD_FILL,
                outline=vt.CARD_OUTLINE,
                width=2,
            )
            text_id = self.canvas.create_text(
                (x1 + x2) / 2,
                (y1 + y2) / 2,
                text=spec.label,
                fill=vt.TEXT_SOFT,
                font=("Helvetica", 10, "bold"),
            )
            self.tab_nodes.append((spec.key, rect_id, text_id))

    def _ensure_action_nodes(self, actions: Sequence) -> None:
        if self.action_nodes:
            return
        for action in actions:
            x1, y1, x2, y2 = self._action_bounds(action.key)
            rect_id = self.canvas.create_rectangle(
                x1,
                y1,
                x2,
                y2,
                fill=vt.CARD_FILL,
                outline=vt.CARD_OUTLINE,
                width=2,
            )
            text_id = self.canvas.create_text(
                (x1 + x2) / 2,
                (y1 + y2) / 2,
                text=action.label,
                fill=vt.TEXT_PRIMARY,
                font=("Helvetica", 10, "bold"),
            )
            self.action_nodes.append((action.key, rect_id, text_id))

    @staticmethod
    def _tab_bounds(key: str) -> tuple[int, int, int, int]:
        bounds = {
            "waiting": (852, 298, 978, 342),
            "turn_info": (992, 298, 1118, 342),
            "map": (1132, 298, 1260, 342),
            "robot_status": (852, 350, 1048, 394),
            "help": (1062, 350, 1260, 394),
        }
        return bounds[key]

    @staticmethod
    def _action_bounds(key: str) -> tuple[int, int, int, int]:
        bounds = {
            "view_info": (852, 590, 978, 634),
            "view_map": (992, 590, 1118, 634),
            "confirm_understanding": (1132, 590, 1260, 634),
        }
        return bounds[key]


def _summary_label(active_tab: str) -> str:
    labels = {
        "waiting": "Thông tin hiện tại",
        "turn_info": "Thông tin lượt",
        "map": "Đường đến phòng khám",
        "robot_status": "Robot đang hỗ trợ bạn",
        "help": "Cần thêm hỗ trợ",
    }
    return labels.get(active_tab, "Thông tin hiện tại")


def _visible_action_keys(active_tab: str) -> frozenset[str]:
    if active_tab == "turn_info":
        return frozenset({"view_map"})
    if active_tab == "map":
        return frozenset({"view_info"})
    if active_tab == "help":
        return frozenset({"confirm_understanding"})
    return frozenset()


def _panel_palette(active_tab: str) -> dict[str, str]:
    base = {
        "shell_fill": vt.PANEL_FILL,
        "shell_outline": vt.PANEL_OUTLINE,
        "header_fill": "#0E1C31",
        "header_outline": "#244868",
        "summary_fill": "#0B1728",
        "summary_outline": vt.CARD_OUTLINE,
        "card_fill": vt.CARD_FILL,
        "card_outline": vt.CARD_OUTLINE,
        "map_fill": vt.MAP_FILL,
        "map_outline": vt.CARD_OUTLINE,
        "accent_text": vt.ACCENT,
        "label_fill": vt.TEXT_MUTED,
        "value_fill": vt.TEXT_PRIMARY,
        "summary_text_fill": vt.TEXT_SOFT,
        "map_heading_fill": vt.TEXT_PRIMARY,
        "map_caption_fill": vt.TEXT_SOFT,
        "footer_fill": vt.TEXT_MUTED,
        "tab_active_fill": "#133049",
        "tab_active_outline": vt.ACCENT,
        "tab_active_text": vt.TEXT_PRIMARY,
        "tab_idle_fill": vt.CARD_FILL,
        "tab_idle_outline": vt.CARD_OUTLINE,
        "tab_idle_text": vt.TEXT_SOFT,
        "action_active_fill": "#7AD8F1",
        "action_active_outline": "#A8EFFF",
        "action_active_text": "#041119",
        "action_idle_fill": vt.CARD_FILL,
        "action_idle_outline": vt.CARD_OUTLINE,
        "action_idle_text": vt.TEXT_PRIMARY,
    }

    if active_tab == "turn_info":
        base.update(
            header_fill="#10233A",
            header_outline="#2A5A82",
            summary_fill="#0C1E33",
            summary_outline="#30658D",
            card_fill="#0D2035",
            card_outline="#2A5A82",
            map_outline="#2A5A82",
            accent_text="#A7EEFF",
            summary_text_fill="#DDF7FF",
            tab_active_fill="#174361",
            action_active_fill="#8EE7FF",
        )
        return base
    if active_tab == "map":
        base.update(
            shell_outline="#27597A",
            header_fill="#0C2436",
            header_outline="#2E698F",
            summary_fill="#0C2234",
            summary_outline="#2E698F",
            card_fill="#0C1D2F",
            card_outline="#2B5C80",
            map_fill="#071722",
            map_outline="#57B8DE",
            accent_text="#8FE8FF",
            summary_text_fill="#CDEFFF",
            map_heading_fill="#DDF7FF",
            map_caption_fill="#B5DCEE",
            footer_fill="#8EBBCE",
            tab_active_fill="#0F4869",
            action_active_fill="#7DDBF8",
        )
        return base
    if active_tab == "robot_status":
        base.update(
            header_fill="#141F31",
            header_outline="#4A6383",
            summary_fill="#131D2D",
            summary_outline="#425978",
            card_fill="#101B2A",
            card_outline="#344A65",
            map_outline="#344A65",
            accent_text="#C1D9F1",
            label_fill="#94A6BF",
            summary_text_fill="#D5E4F5",
            footer_fill="#9CB0C8",
            tab_active_fill="#2A3F57",
            action_active_fill="#B8D7F0",
            action_active_outline="#D9EEFF",
            action_active_text="#071019",
        )
        return base
    if active_tab == "help":
        base.update(
            shell_outline="#8E5E3B",
            header_fill="#291B12",
            header_outline="#AF7447",
            summary_fill="#261810",
            summary_outline="#AF7447",
            card_fill="#21150E",
            card_outline="#835638",
            map_fill="#17100B",
            map_outline="#835638",
            accent_text=vt.ACCENT_ALERT,
            label_fill="#D1A684",
            value_fill="#FFF3E7",
            summary_text_fill="#F7D8BE",
            map_heading_fill="#FFF0E2",
            map_caption_fill="#E9C6A7",
            footer_fill="#E1B791",
            tab_active_fill="#5A351F",
            tab_active_outline="#E1AA73",
            action_active_fill="#F0BD8A",
            action_active_outline="#FFE1BF",
            action_active_text="#1B0E07",
        )
        return base
    return base
