from __future__ import annotations

import argparse
import json
import math
import os
import pathlib
import signal
import sys
import tempfile
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Final

try:
    import rclpy
    from nav_msgs.msg import OccupancyGrid, Path as NavPath
    from rclpy.node import Node
    from tf2_ros import Buffer, TransformException, TransformListener
except ImportError:  # pragma: no cover - local proof path can run without ROS
    rclpy = None
    OccupancyGrid = None
    NavPath = None
    Node = object
    Buffer = None
    TransformException = Exception
    TransformListener = None


MAP_SNAPSHOT_ENV_VAR: Final[str] = "ROBOT_UI_MAP_SNAPSHOT_PATH"
DEFAULT_MAP_SNAPSHOT_BASENAME: Final[str] = "robothospital_runtime_map_snapshot.json"
DEFAULT_MAP_SOURCE: Final[str] = "/map"
DEFAULT_PLAN_SOURCE: Final[str] = "/plan"
DEFAULT_POSE_SOURCE: Final[str] = "TF map -> base_footprint_link"


def default_map_snapshot_path() -> Path:
    override = os.environ.get(MAP_SNAPSHOT_ENV_VAR)
    if override:
        return Path(override).expanduser().resolve()
    return Path(tempfile.gettempdir(), DEFAULT_MAP_SNAPSHOT_BASENAME).resolve()


@dataclass(frozen=True, slots=True)
class MapRuntimeSnapshot:
    sequence: int
    emitted_at_ms: float
    source: str
    map_source: str
    pose_source: str
    path_source: str
    grid_rows: tuple[str, ...]
    route_points: tuple[tuple[float, float], ...]
    robot_pose: tuple[float, float, float]
    status_text: str

    def to_dict(self) -> dict[str, object]:
        return {
            "sequence": self.sequence,
            "emitted_at_ms": self.emitted_at_ms,
            "source": self.source,
            "map_source": self.map_source,
            "pose_source": self.pose_source,
            "path_source": self.path_source,
            "grid_rows": list(self.grid_rows),
            "route_points": [list(point) for point in self.route_points],
            "robot_pose": list(self.robot_pose),
            "status_text": self.status_text,
        }

    @classmethod
    def from_dict(cls, data: dict[str, object]) -> "MapRuntimeSnapshot":
        return cls(
            sequence=int(data["sequence"]),
            emitted_at_ms=float(data["emitted_at_ms"]),
            source=str(data["source"]),
            map_source=str(data["map_source"]),
            pose_source=str(data["pose_source"]),
            path_source=str(data["path_source"]),
            grid_rows=tuple(str(row) for row in data.get("grid_rows", [])),
            route_points=tuple(
                (float(point[0]), float(point[1]))
                for point in data.get("route_points", [])
            ),
            robot_pose=tuple(float(value) for value in data["robot_pose"]),
            status_text=str(data.get("status_text", "")),
        )


class MapRuntimeSnapshotStore:
    def __init__(self, path: Path | None = None) -> None:
        self.path = path or default_map_snapshot_path()

    def write(self, snapshot: MapRuntimeSnapshot) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        tmp_path = self.path.with_suffix(self.path.suffix + ".tmp")
        tmp_path.write_text(
            json.dumps(snapshot.to_dict(), ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        tmp_path.replace(self.path)

    def read(self) -> MapRuntimeSnapshot | None:
        if not self.path.exists():
            return None
        return MapRuntimeSnapshot.from_dict(json.loads(self.path.read_text(encoding="utf-8")))

    def read_if_newer(self, sequence: int) -> MapRuntimeSnapshot | None:
        snapshot = self.read()
        if snapshot is None or snapshot.sequence <= sequence:
            return None
        return snapshot


@dataclass(frozen=True, slots=True)
class _MapMeta:
    width: int
    height: int
    resolution: float
    origin_x: float
    origin_y: float

    @property
    def world_width(self) -> float:
        return self.width * self.resolution

    @property
    def world_height(self) -> float:
        return self.height * self.resolution


class MapRuntimeEngine:
    def __init__(
        self,
        snapshot_store: MapRuntimeSnapshotStore | None = None,
        *,
        map_source: str = DEFAULT_MAP_SOURCE,
        pose_source: str = DEFAULT_POSE_SOURCE,
        path_source: str = DEFAULT_PLAN_SOURCE,
    ) -> None:
        self.snapshot_store = snapshot_store or MapRuntimeSnapshotStore(default_map_snapshot_path())
        self.map_source = map_source
        self.pose_source = pose_source
        self.path_source = path_source
        self.sequence = 0
        self.map_meta: _MapMeta | None = None
        self.grid_rows: tuple[str, ...] | None = None
        self.raw_route_points: tuple[tuple[float, float], ...] = ()
        self.raw_pose: tuple[float, float, float] | None = None

    def update_map(
        self,
        *,
        width: int,
        height: int,
        resolution: float,
        origin_x: float,
        origin_y: float,
        cells: list[int] | tuple[int, ...],
    ) -> None:
        self.map_meta = _MapMeta(
            width=width,
            height=height,
            resolution=resolution,
            origin_x=origin_x,
            origin_y=origin_y,
        )
        self.grid_rows = _downsample_grid(width=width, height=height, cells=cells)

    def update_map_from_occupancy(self, msg: OccupancyGrid) -> None:
        self.update_map(
            width=msg.info.width,
            height=msg.info.height,
            resolution=float(msg.info.resolution),
            origin_x=float(msg.info.origin.position.x),
            origin_y=float(msg.info.origin.position.y),
            cells=list(msg.data),
        )

    def update_route(self, points: list[tuple[float, float]] | tuple[tuple[float, float], ...]) -> None:
        self.raw_route_points = tuple(points)

    def update_route_from_path(self, msg: NavPath) -> None:
        self.update_route(
            [
                (float(pose.pose.position.x), float(pose.pose.position.y))
                for pose in msg.poses
            ]
        )

    def update_pose(self, *, x: float, y: float, yaw_deg: float) -> None:
        self.raw_pose = (x, y, yaw_deg)

    def update_pose_from_tf_transform(self, transform) -> None:
        translation = transform.transform.translation
        rotation = transform.transform.rotation
        self.update_pose(
            x=float(translation.x),
            y=float(translation.y),
            yaw_deg=_yaw_from_quaternion(
                x=float(rotation.x),
                y=float(rotation.y),
                z=float(rotation.z),
                w=float(rotation.w),
            ),
        )

    def emit_snapshot(self, *, source: str = "map_runtime") -> MapRuntimeSnapshot | None:
        snapshot = self.build_snapshot(source=source)
        if snapshot is None:
            return None
        self.snapshot_store.write(snapshot)
        return snapshot

    def build_snapshot(self, *, source: str) -> MapRuntimeSnapshot | None:
        if self.map_meta is None or self.grid_rows is None or self.raw_pose is None:
            return None
        if len(self.raw_route_points) < 2:
            return None

        route_points = tuple(
            _normalize_point(self.map_meta, x=point[0], y=point[1]) for point in self.raw_route_points
        )
        robot_x, robot_y, robot_yaw = self.raw_pose
        robot_pose = _normalize_pose(self.map_meta, x=robot_x, y=robot_y, yaw_deg=robot_yaw)

        self.sequence += 1
        return MapRuntimeSnapshot(
            sequence=self.sequence,
            emitted_at_ms=time.monotonic() * 1000.0,
            source=source,
            map_source=self.map_source,
            pose_source=self.pose_source,
            path_source=self.path_source,
            grid_rows=self.grid_rows,
            route_points=route_points,
            robot_pose=robot_pose,
            status_text=(
                f"Pose bám {self.pose_source}; tuyến dẫn đường bám {self.path_source}; "
                f"bản đồ nền lấy từ {self.map_source}."
            ),
        )

    def run_demo_sequence(
        self,
        *,
        step_delay_ms: int,
        print_snapshots: bool,
    ) -> list[MapRuntimeSnapshot]:
        self.update_map(
            width=18,
            height=10,
            resolution=1.0,
            origin_x=0.0,
            origin_y=0.0,
            cells=_demo_cells(),
        )
        self.update_route(
            [
                (1.0, 1.0),
                (3.0, 2.0),
                (6.0, 4.0),
                (10.0, 6.0),
                (14.0, 8.0),
            ]
        )

        snapshots: list[MapRuntimeSnapshot] = []
        for pose in ((1.0, 1.0, 15.0), (6.0, 4.0, 28.0), (10.0, 6.0, 35.0), (14.0, 8.0, 40.0)):
            self.update_pose(x=pose[0], y=pose[1], yaw_deg=pose[2])
            snapshot = self.emit_snapshot(source="demo_map_runtime")
            if snapshot is None:
                raise RuntimeError("Demo map runtime could not emit a complete snapshot")
            snapshots.append(snapshot)
            if print_snapshots:
                print(json.dumps(snapshot.to_dict(), ensure_ascii=True))
            if step_delay_ms > 0:
                time.sleep(step_delay_ms / 1000.0)
        return snapshots


class MapRuntimeBridgeNode(Node):
    def __init__(
        self,
        engine: MapRuntimeEngine,
        *,
        map_topic: str,
        plan_topic: str,
        map_frame: str,
        base_frame: str,
    ) -> None:
        super().__init__("robot_map_runtime_bridge")
        self.engine = engine
        self.map_frame = map_frame
        self.base_frame = base_frame
        self.tf_buffer = Buffer()
        self.tf_listener = TransformListener(self.tf_buffer, self)
        self.map_subscription = self.create_subscription(
            OccupancyGrid,
            map_topic,
            self._handle_map,
            10,
        )
        self.plan_subscription = self.create_subscription(
            NavPath,
            plan_topic,
            self._handle_plan,
            10,
        )
        self.publish_timer = self.create_timer(0.25, self._refresh_snapshot)
        self.get_logger().info(
            "Robot map runtime bridge ready "
            f"(map={map_topic}, plan={plan_topic}, pose={map_frame}->{base_frame}); "
            f"snapshots -> {self.engine.snapshot_store.path}"
        )

    def _handle_map(self, msg: OccupancyGrid) -> None:
        self.engine.update_map_from_occupancy(msg)

    def _handle_plan(self, msg: NavPath) -> None:
        self.engine.update_route_from_path(msg)

    def _refresh_snapshot(self) -> None:
        try:
            transform = self.tf_buffer.lookup_transform(
                self.map_frame,
                self.base_frame,
                rclpy.time.Time(),
            )
        except TransformException:
            return
        self.engine.update_pose_from_tf_transform(transform)
        snapshot = self.engine.emit_snapshot(source="ros_map_runtime")
        if snapshot is not None:
            self.get_logger().info(
                f"Map snapshot #{snapshot.sequence} updated from {snapshot.pose_source} and {snapshot.path_source}"
            )


def _downsample_grid(
    *,
    width: int,
    height: int,
    cells: list[int] | tuple[int, ...],
    target_cols: int = 24,
    target_rows: int = 10,
) -> tuple[str, ...]:
    rows: list[str] = []
    for row_index in range(target_rows):
        chars: list[str] = []
        y_start = int(row_index * height / target_rows)
        y_end = max(y_start + 1, int((row_index + 1) * height / target_rows))
        for col_index in range(target_cols):
            x_start = int(col_index * width / target_cols)
            x_end = max(x_start + 1, int((col_index + 1) * width / target_cols))
            region: list[int] = []
            for y_pos in range(y_start, min(y_end, height)):
                start = y_pos * width
                region.extend(cells[start + x_start : start + min(x_end, width)])
            if not region:
                chars.append("?")
                continue
            if any(value > 50 for value in region):
                chars.append("#")
            elif sum(1 for value in region if value < 0) > (len(region) // 2):
                chars.append("?")
            else:
                chars.append(".")
        rows.append("".join(chars))
    return tuple(rows)


def _normalize_point(meta: _MapMeta, *, x: float, y: float) -> tuple[float, float]:
    norm_x = (x - meta.origin_x) / max(meta.world_width, 1e-6)
    norm_y = 1.0 - ((y - meta.origin_y) / max(meta.world_height, 1e-6))
    return (_clamp01(norm_x), _clamp01(norm_y))


def _normalize_pose(meta: _MapMeta, *, x: float, y: float, yaw_deg: float) -> tuple[float, float, float]:
    point = _normalize_point(meta, x=x, y=y)
    return (point[0], point[1], yaw_deg)


def _yaw_from_quaternion(*, x: float, y: float, z: float, w: float) -> float:
    siny_cosp = 2.0 * (w * z + x * y)
    cosy_cosp = 1.0 - 2.0 * (y * y + z * z)
    return math.degrees(math.atan2(siny_cosp, cosy_cosp))


def _clamp01(value: float) -> float:
    return max(0.0, min(1.0, value))


def _demo_cells() -> list[int]:
    rows = [
        "..................",
        "....##............",
        "....##....####....",
        "..........####....",
        "..................",
        "..#####...........",
        "..#####...........",
        "..................",
        "............###...",
        "..................",
    ]
    cells: list[int] = []
    for row in rows:
        for char in row:
            cells.append(100 if char == "#" else 0)
    return cells


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="ROS sidecar that converts /map, /plan, and TF pose into compact map snapshots.",
    )
    parser.add_argument(
        "--snapshot-path",
        default=str(default_map_snapshot_path()),
        help="Shared JSON snapshot path consumed by the Tk shell map panel.",
    )
    parser.add_argument(
        "--map-topic",
        default=DEFAULT_MAP_SOURCE,
        help="ROS topic carrying nav_msgs/OccupancyGrid.",
    )
    parser.add_argument(
        "--plan-topic",
        default=DEFAULT_PLAN_SOURCE,
        help="ROS topic carrying nav_msgs/Path.",
    )
    parser.add_argument(
        "--map-frame",
        default="map",
        help="TF parent frame for robot pose lookup.",
    )
    parser.add_argument(
        "--base-frame",
        default="base_footprint_link",
        help="TF child frame for robot pose lookup.",
    )
    parser.add_argument(
        "--demo-sequence",
        action="store_true",
        help="Run a local map/pose/route proof sequence without ROS.",
    )
    parser.add_argument(
        "--step-delay-ms",
        type=int,
        default=0,
        help="Delay between demo sequence pose updates.",
    )
    parser.add_argument(
        "--print-snapshots",
        action="store_true",
        help="Print emitted snapshots as JSON during demo mode.",
    )
    return parser.parse_args()


def main() -> None:
    args = _parse_args()
    engine = MapRuntimeEngine(
        snapshot_store=MapRuntimeSnapshotStore(path=pathlib.Path(args.snapshot_path).resolve()),
        map_source=args.map_topic,
        pose_source=f"TF {args.map_frame} -> {args.base_frame}",
        path_source=args.plan_topic,
    )
    if args.demo_sequence:
        engine.run_demo_sequence(
            step_delay_ms=max(0, args.step_delay_ms),
            print_snapshots=args.print_snapshots,
        )
        return
    if rclpy is None or OccupancyGrid is None or NavPath is None or Buffer is None:
        raise SystemExit(
            "rclpy, nav_msgs, and tf2_ros are required for ROS map runtime mode. "
            "Use --demo-sequence for local proof without ROS."
        )
    rclpy.init()
    node = MapRuntimeBridgeNode(
        engine,
        map_topic=args.map_topic,
        plan_topic=args.plan_topic,
        map_frame=args.map_frame,
        base_frame=args.base_frame,
    )
    signal.signal(signal.SIGINT, lambda *_args: rclpy.shutdown())
    signal.signal(signal.SIGTERM, lambda *_args: rclpy.shutdown())
    try:
        rclpy.spin(node)
    finally:  # pragma: no cover - ROS shutdown path
        node.destroy_node()
        rclpy.shutdown()


if __name__ == "__main__":
    main()
