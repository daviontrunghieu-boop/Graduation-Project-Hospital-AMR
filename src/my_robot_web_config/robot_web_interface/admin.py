#!/usr/bin/env python3
from __future__ import annotations

import json
import math
import os
from datetime import datetime
from pathlib import Path

from nicegui import ui

try:
    from wed_server.web.appointments import (
        AppointmentStore,
        RobotStateStore,
        SymptomRoomRuleStore,
        format_appointments,
        format_symptom_room_rules,
    )
except ModuleNotFoundError:
    from appointments import (
        AppointmentStore,
        RobotStateStore,
        SymptomRoomRuleStore,
        format_appointments,
        format_symptom_room_rules,
    )


ACCOUNT_STORE_PATH = Path(
    os.getenv(
        "ROBOT_HOSPITAL_ACCOUNT_PATH",
        Path(__file__).resolve().parents[1] / "patient_accounts.json",
    )
)
ROBOT_PATIENT_PROFILE_PATH = Path(
    os.getenv(
        "ROBOT_HOSPITAL_ROBOT_PATIENT_PATH",
        Path(__file__).resolve().parents[1] / "robot_patient_profiles.json",
    )
)
ROBOT_COMMAND_PATH = Path(
    os.getenv(
        "ROBOT_HOSPITAL_COMMAND_PATH",
        Path(__file__).resolve().parents[1] / "robot_command.json",
    )
)
PATIENT_INFORMATION_PATH = Path(
    os.getenv(
        "ROBOT_HOSPITAL_PATIENT_INFORMATION_PATH",
        "/home/hieu/ros2_ws/src/my_robot_web_config/robot_web_interface/user_information/patient_information.json",
    )
)

DEFAULT_HOME_POSE = {
    "x": 0.0,
    "y": 0.0,
    "z": 0.0,
    "w": 1.0,
}

ROSBRIDGE_PORT = int(os.getenv("ROSBRIDGE_PORT", "9090"))
ROS_MAP_TOPIC = os.getenv("ROS_MAP_TOPIC", "/map")
ROS_POSE_TOPIC = os.getenv("ROS_POSE_TOPIC", "/amcl_pose")
ROS_PLAN_TOPIC = os.getenv("ROS_PLAN_TOPIC", "/plan")

store = AppointmentStore()
robot_store = RobotStateStore()
symptom_rule_store = SymptomRoomRuleStore()


def list_registered_patient_phones() -> list[str]:
    try:
        if not ACCOUNT_STORE_PATH.exists():
            return []
        data = json.loads(ACCOUNT_STORE_PATH.read_text(encoding="utf-8"))
        if not isinstance(data, list):
            return []
        cleaned = sorted({str(phone).strip() for phone in data if str(phone).strip()})
        return cleaned
    except (OSError, json.JSONDecodeError):
        return []


def load_robot_patient_profiles() -> dict[str, dict]:
    try:
        if not ROBOT_PATIENT_PROFILE_PATH.exists():
            return {}
        data = json.loads(ROBOT_PATIENT_PROFILE_PATH.read_text(encoding="utf-8"))
        if not isinstance(data, dict):
            return {}
        patients = data.get("patients", {})
        if isinstance(patients, dict):
            return patients
        return data
    except (OSError, json.JSONDecodeError):
        return {}


def format_robot_patient_profiles(profiles: dict[str, dict]) -> list[dict[str, str | int]]:
    rows: list[dict[str, str | int]] = []
    for phone, profile in profiles.items():
        appointment = profile.get("latest_appointment", {})
        if not isinstance(appointment, dict):
            appointment = {}
        rows.append(
            {
                "patient_name": str(profile.get("patient_name", "")),
                "phone": str(profile.get("phone", phone)),
                "face_capture_count": int(profile.get("face_capture_count", 0) or 0),
                "latest_capture_at": str(profile.get("latest_capture_at", "")),
                "queue_number": str(appointment.get("queue_number", "")),
                "department": str(appointment.get("department", "")),
                "room_label": str(appointment.get("room_label", "")),
                "appointment_date": str(appointment.get("appointment_date", "")),
                "appointment_time": str(appointment.get("appointment_time", "")),
                "updated_at": str(profile.get("updated_at", "")),
            }
        )
    rows.sort(key=lambda row: (str(row["updated_at"]), str(row["phone"])), reverse=True)
    return rows


def load_patient_information() -> dict:
    """Read the JSON file used by the voice navigation node."""
    if not PATIENT_INFORMATION_PATH.exists():
        return {
            "updated_at": datetime.now().isoformat(timespec="seconds"),
            "patient_count": 0,
            "queue_count": 0,
            "room_destinations": {},
            "patients": {},
            "queue_index": {},
        }

    try:
        data = json.loads(PATIENT_INFORMATION_PATH.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise ValueError(f"Không thể đọc patient_information.json: {error}") from error

    if not isinstance(data, dict):
        raise ValueError("patient_information.json không đúng định dạng đối tượng JSON.")

    if not isinstance(data.get("room_destinations"), dict):
        data["room_destinations"] = {}
    if not isinstance(data.get("patients"), dict):
        data["patients"] = {}
    if not isinstance(data.get("queue_index"), dict):
        data["queue_index"] = {}
    return data


def write_patient_information(data: dict) -> None:
    """Write atomically so the voice node never reads a half-written JSON file."""
    PATIENT_INFORMATION_PATH.parent.mkdir(parents=True, exist_ok=True)
    temporary_path = PATIENT_INFORMATION_PATH.with_suffix(PATIENT_INFORMATION_PATH.suffix + ".tmp")
    try:
        temporary_path.write_text(
            json.dumps(data, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        temporary_path.replace(PATIENT_INFORMATION_PATH)
    except OSError as error:
        try:
            temporary_path.unlink(missing_ok=True)
        except OSError:
            pass
        raise ValueError(f"Không thể ghi patient_information.json: {error}") from error


def save_room_destination(room_label: str, x: float, y: float, theta_rad: float) -> None:
    room_label = str(room_label or "").strip()
    if not room_label:
        raise ValueError("Vui lòng nhập số phòng trước khi lưu tọa độ.")

    # Người vận hành nhập theta trực tiếp theo radian. ROS 2/Nav2 nhận hướng
    # dưới dạng quaternion, nên tự động chuyển theta sang orientation.z và orientation.w.
    theta_rad = float(theta_rad)
    orientation_z = math.sin(theta_rad / 2.0)
    orientation_w = math.cos(theta_rad / 2.0)

    pose = {
        "x": float(x),
        "y": float(y),
        "theta": theta_rad,
        "z": orientation_z,
        "w": orientation_w,
    }

    data = load_patient_information()
    data["room_destinations"][room_label] = pose
    data["updated_at"] = datetime.now().isoformat(timespec="seconds")

    # Đồng bộ destination_pose để dữ liệu bệnh nhân và hàng đợi không bị lệch.
    synced_pose = {**pose, "configured": True}
    for section_name in ("patients", "queue_index"):
        section = data.get(section_name, {})
        if not isinstance(section, dict):
            continue
        for record in section.values():
            if not isinstance(record, dict):
                continue
            if str(record.get("room_label", "")).strip() == room_label:
                record["destination_pose"] = dict(synced_pose)

    write_patient_information(data)


def delete_room_destination(room_label: str) -> None:
    """Delete one room pose and mark linked patient destinations as unconfigured."""
    room_label = str(room_label or "").strip()
    if not room_label:
        raise ValueError("Vui lòng nhập số phòng cần xóa.")

    data = load_patient_information()
    room_destinations = data.get("room_destinations", {})
    if not isinstance(room_destinations, dict) or room_label not in room_destinations:
        raise ValueError(f"Không tìm thấy tọa độ phòng {room_label}.")

    del room_destinations[room_label]
    data["updated_at"] = datetime.now().isoformat(timespec="seconds")

    # Không xóa hồ sơ bệnh nhân hoặc hàng đợi. Chỉ đánh dấu điểm đến của
    # các bản ghi liên quan là chưa được cấu hình để robot không dùng tọa độ cũ.
    unconfigured_pose = {
        "x": 0.0,
        "y": 0.0,
        "theta": 0.0,
        "z": 0.0,
        "w": 1.0,
        "configured": False,
    }
    for section_name in ("patients", "queue_index"):
        section = data.get(section_name, {})
        if not isinstance(section, dict):
            continue
        for record in section.values():
            if not isinstance(record, dict):
                continue
            if str(record.get("room_label", "")).strip() == room_label:
                record["destination_pose"] = dict(unconfigured_pose)

    write_patient_information(data)


def format_room_destinations() -> list[dict[str, str | float]]:
    try:
        data = load_patient_information()
    except ValueError:
        return []

    rows: list[dict[str, str | float]] = []
    for room_label, pose in data.get("room_destinations", {}).items():
        if not isinstance(pose, dict):
            continue
        orientation_z = float(pose.get("z", 0.0) or 0.0)
        orientation_w = float(pose.get("w", 1.0) or 1.0)
        if pose.get("theta") is not None:
            theta_rad = float(pose.get("theta", 0.0) or 0.0)
        else:
            # Hỗ trợ các phòng cũ chỉ có z và w.
            theta_rad = 2.0 * math.atan2(orientation_z, orientation_w)

        rows.append(
            {
                "room_label": str(room_label),
                "x": round(float(pose.get("x", 0.0) or 0.0), 6),
                "y": round(float(pose.get("y", 0.0) or 0.0), 6),
                "theta_deg": round(math.degrees(theta_rad), 3),
                "theta_rad": round(theta_rad, 6),
                "z": round(orientation_z, 6),
                "w": round(orientation_w, 6),
            }
        )
    rows.sort(key=lambda row: str(row["room_label"]))
    return rows


def build_live_map_panel() -> None:
    """Display the ROS 2 occupancy grid, AMCL pose, and Nav2 global path."""
    with ui.card().classes("admin-panel p-7"):
        with ui.row().classes("w-full items-start justify-between gap-4 max-[800px]:flex-col"):
            with ui.column().classes("gap-1"):
                ui.label("Bản đồ giám sát robot").classes("text-2xl font-black text-slate-900")
                ui.label(
                    "Dữ liệu thời gian thực từ ROS 2: /map, /amcl_pose và /plan."
                ).classes("text-sm leading-6 text-slate-600")
            ui.html(
                """
                <div class="flex flex-wrap items-center gap-2 text-xs font-bold">
                    <span id="aurora-ros-status" class="rounded-full bg-amber-100 px-3 py-2 text-amber-700">
                        ROS: Đang kết nối
                    </span>
                    <span id="aurora-map-status" class="rounded-full bg-slate-100 px-3 py-2 text-slate-600">
                        Map: Chưa nhận
                    </span>
                </div>
                """,
                sanitize=False,
            )

        ui.html(
            """
            <div class="mt-5 w-full overflow-hidden rounded-3xl border border-slate-200 bg-slate-950 p-3">
                <canvas id="aurora-map-canvas"
                        style="display:block;width:100%;height:560px;border-radius:20px;background:#0f172a;"></canvas>
            </div>
            <div class="mt-4 grid grid-cols-2 gap-3 max-[700px]:grid-cols-1">
                <div class="rounded-2xl bg-slate-50 px-4 py-3 ring-1 ring-slate-200">
                    <div class="text-xs font-bold uppercase tracking-[0.16em] text-slate-500">Vị trí robot</div>
                    <div id="aurora-pose-text" class="mt-1 font-black text-slate-900">Chưa nhận /amcl_pose</div>
                </div>
                <div class="rounded-2xl bg-slate-50 px-4 py-3 ring-1 ring-slate-200">
                    <div class="text-xs font-bold uppercase tracking-[0.16em] text-slate-500">Thông tin bản đồ</div>
                    <div id="aurora-map-info" class="mt-1 font-black text-slate-900">Chưa nhận /map</div>
                </div>
            </div>
            <div class="mt-3 text-xs leading-5 text-slate-500">
                Tam giác màu cyan là robot; đường màu xanh dương là global path khi topic /plan có dữ liệu.
            </div>
            """,
            sanitize=False,
        ).classes("w-full")

    config = {
        "port": ROSBRIDGE_PORT,
        "mapTopic": ROS_MAP_TOPIC,
        "poseTopic": ROS_POSE_TOPIC,
        "planTopic": ROS_PLAN_TOPIC,
    }

    script = r"""
    (() => {
        const config = __AURORA_CONFIG__;

        if (window.__auroraLiveMap && window.__auroraLiveMap.destroy) {
            window.__auroraLiveMap.destroy();
        }

        const canvas = document.getElementById('aurora-map-canvas');
        const rosStatus = document.getElementById('aurora-ros-status');
        const mapStatus = document.getElementById('aurora-map-status');
        const poseText = document.getElementById('aurora-pose-text');
        const mapInfo = document.getElementById('aurora-map-info');

        if (!canvas || !rosStatus || !mapStatus || !poseText || !mapInfo) {
            return;
        }

        const ctx = canvas.getContext('2d');
        const state = {
            destroyed: false,
            socket: null,
            reconnectTimer: null,
            map: null,
            mapBitmap: null,
            pose: null,
            path: [],
        };

        function setBadge(element, text, cssClasses) {
            element.textContent = text;
            element.className = `rounded-full px-3 py-2 ${cssClasses}`;
        }

        function websocketUrl() {
            const scheme = window.location.protocol === 'https:' ? 'wss' : 'ws';
            return `${scheme}://${window.location.hostname}:${config.port}`;
        }

        function quaternionYaw(q) {
            if (!q) return 0;
            const siny = 2 * ((q.w || 0) * (q.z || 0) + (q.x || 0) * (q.y || 0));
            const cosy = 1 - 2 * ((q.y || 0) * (q.y || 0) + (q.z || 0) * (q.z || 0));
            return Math.atan2(siny, cosy);
        }

        function decodeMapData(data, expectedLength) {
            if (Array.isArray(data)) return data;
            if (ArrayBuffer.isView(data)) return Array.from(data);
            if (data instanceof ArrayBuffer) return Array.from(new Int8Array(data));
            if (typeof data === 'string') {
                try {
                    const raw = atob(data);
                    const values = new Array(raw.length);
                    for (let i = 0; i < raw.length; i += 1) {
                        const value = raw.charCodeAt(i);
                        values[i] = value > 127 ? value - 256 : value;
                    }
                    return values;
                } catch (error) {
                    console.error('Không thể giải mã dữ liệu /map:', error);
                }
            }
            return new Array(expectedLength).fill(-1);
        }

        function buildMapBitmap(message) {
            const width = Number(message.info.width || 0);
            const height = Number(message.info.height || 0);
            if (!width || !height) return null;

            const values = decodeMapData(message.data, width * height);
            const offscreen = document.createElement('canvas');
            offscreen.width = width;
            offscreen.height = height;
            const offCtx = offscreen.getContext('2d');
            const image = offCtx.createImageData(width, height);

            for (let y = 0; y < height; y += 1) {
                for (let x = 0; x < width; x += 1) {
                    const sourceIndex = y * width + x;
                    const destinationY = height - 1 - y;
                    const destinationIndex = (destinationY * width + x) * 4;
                    const occupancy = Number(values[sourceIndex] ?? -1);

                    let shade;
                    if (occupancy < 0) {
                        shade = 196;
                    } else {
                        shade = Math.round(255 - Math.min(100, Math.max(0, occupancy)) * 2.55);
                    }

                    image.data[destinationIndex] = shade;
                    image.data[destinationIndex + 1] = shade;
                    image.data[destinationIndex + 2] = shade;
                    image.data[destinationIndex + 3] = 255;
                }
            }

            offCtx.putImageData(image, 0, 0);
            return offscreen;
        }

        function worldToMapPixel(x, y) {
            if (!state.map) return null;
            const origin = state.map.info.origin || {};
            const originPosition = origin.position || {};
            const originYaw = quaternionYaw(origin.orientation || {});
            const resolution = Number(state.map.info.resolution || 0.05);
            const dx = x - Number(originPosition.x || 0);
            const dy = y - Number(originPosition.y || 0);
            const cosYaw = Math.cos(originYaw);
            const sinYaw = Math.sin(originYaw);

            const mapX = (cosYaw * dx + sinYaw * dy) / resolution;
            const mapY = (-sinYaw * dx + cosYaw * dy) / resolution;

            return {
                x: mapX,
                y: Number(state.map.info.height) - mapY,
                originYaw,
            };
        }

        function prepareCanvas() {
            const rect = canvas.getBoundingClientRect();
            const width = Math.max(320, Math.floor(rect.width));
            const height = Math.max(320, Math.floor(rect.height));
            const dpr = window.devicePixelRatio || 1;
            const targetWidth = Math.floor(width * dpr);
            const targetHeight = Math.floor(height * dpr);

            if (canvas.width !== targetWidth || canvas.height !== targetHeight) {
                canvas.width = targetWidth;
                canvas.height = targetHeight;
            }
            ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
            return {width, height};
        }

        function render() {
            if (state.destroyed) return;
            const size = prepareCanvas();
            ctx.clearRect(0, 0, size.width, size.height);
            ctx.fillStyle = '#0f172a';
            ctx.fillRect(0, 0, size.width, size.height);

            if (!state.map || !state.mapBitmap) {
                ctx.fillStyle = '#cbd5e1';
                ctx.font = '700 18px sans-serif';
                ctx.textAlign = 'center';
                ctx.fillText('Đang chờ dữ liệu bản đồ từ /map ...', size.width / 2, size.height / 2);
                return;
            }

            const mapWidth = Number(state.map.info.width);
            const mapHeight = Number(state.map.info.height);
            const margin = 18;
            const scale = Math.min(
                (size.width - margin * 2) / mapWidth,
                (size.height - margin * 2) / mapHeight,
            );
            const drawWidth = mapWidth * scale;
            const drawHeight = mapHeight * scale;
            const offsetX = (size.width - drawWidth) / 2;
            const offsetY = (size.height - drawHeight) / 2;

            ctx.imageSmoothingEnabled = false;
            ctx.drawImage(state.mapBitmap, offsetX, offsetY, drawWidth, drawHeight);
            ctx.strokeStyle = '#475569';
            ctx.lineWidth = 1;
            ctx.strokeRect(offsetX, offsetY, drawWidth, drawHeight);

            if (state.path && state.path.length > 1) {
                ctx.beginPath();
                let started = false;
                for (const poseStamped of state.path) {
                    const position = poseStamped.pose?.position;
                    if (!position) continue;
                    const mapPoint = worldToMapPixel(Number(position.x), Number(position.y));
                    if (!mapPoint) continue;
                    const px = offsetX + mapPoint.x * scale;
                    const py = offsetY + mapPoint.y * scale;
                    if (!started) {
                        ctx.moveTo(px, py);
                        started = true;
                    } else {
                        ctx.lineTo(px, py);
                    }
                }
                ctx.strokeStyle = '#2563eb';
                ctx.lineWidth = 3;
                ctx.lineJoin = 'round';
                ctx.lineCap = 'round';
                ctx.stroke();
            }

            if (state.pose) {
                const position = state.pose.pose?.pose?.position;
                const orientation = state.pose.pose?.pose?.orientation;
                if (position && orientation) {
                    const mapPoint = worldToMapPixel(Number(position.x), Number(position.y));
                    if (mapPoint) {
                        const px = offsetX + mapPoint.x * scale;
                        const py = offsetY + mapPoint.y * scale;
                        const relativeYaw = quaternionYaw(orientation) - mapPoint.originYaw;
                        const canvasYaw = -relativeYaw;
                        const markerSize = 15;

                        ctx.save();
                        ctx.translate(px, py);
                        ctx.rotate(canvasYaw);
                        ctx.beginPath();
                        ctx.moveTo(markerSize, 0);
                        ctx.lineTo(-markerSize * 0.75, markerSize * 0.65);
                        ctx.lineTo(-markerSize * 0.75, -markerSize * 0.65);
                        ctx.closePath();
                        ctx.fillStyle = '#06b6d4';
                        ctx.fill();
                        ctx.strokeStyle = '#083344';
                        ctx.lineWidth = 2;
                        ctx.stroke();
                        ctx.restore();

                        ctx.beginPath();
                        ctx.arc(px, py, markerSize + 5, 0, Math.PI * 2);
                        ctx.strokeStyle = 'rgba(6, 182, 212, 0.45)';
                        ctx.lineWidth = 3;
                        ctx.stroke();
                    }
                }
            }
        }

        function processMapMessage(message) {
            state.map = message;
            state.mapBitmap = buildMapBitmap(message);
            const widthMeters = Number(message.info.width) * Number(message.info.resolution);
            const heightMeters = Number(message.info.height) * Number(message.info.resolution);
            mapInfo.textContent = `${widthMeters.toFixed(2)} × ${heightMeters.toFixed(2)} m | ${message.info.resolution} m/cell`;
            setBadge(mapStatus, `Map: ${message.info.width} × ${message.info.height}`, 'bg-emerald-100 text-emerald-700');
            render();
        }

        function processPoseMessage(message) {
            state.pose = message;
            const position = message.pose?.pose?.position;
            const orientation = message.pose?.pose?.orientation;
            if (position && orientation) {
                const yawDegrees = quaternionYaw(orientation) * 180 / Math.PI;
                poseText.textContent = `x = ${Number(position.x).toFixed(2)} m | y = ${Number(position.y).toFixed(2)} m | θ = ${yawDegrees.toFixed(1)}°`;
            }
            render();
        }

        function processPlanMessage(message) {
            state.path = Array.isArray(message.poses) ? message.poses : [];
            render();
        }

        function sendRosbridge(payload) {
            if (state.socket && state.socket.readyState === WebSocket.OPEN) {
                state.socket.send(JSON.stringify(payload));
            }
        }

        function subscribeTopics() {
            sendRosbridge({
                op: 'subscribe',
                id: 'aurora_map_subscription',
                topic: config.mapTopic,
                type: 'nav_msgs/msg/OccupancyGrid',
                queue_length: 1,
                qos: {
                    history: 'keep_last',
                    depth: 1,
                    reliability: 'reliable',
                    durability: 'transient_local',
                },
            });

            sendRosbridge({
                op: 'subscribe',
                id: 'aurora_pose_subscription',
                topic: config.poseTopic,
                type: 'geometry_msgs/msg/PoseWithCovarianceStamped',
                throttle_rate: 100,
                queue_length: 1,
            });

            sendRosbridge({
                op: 'subscribe',
                id: 'aurora_plan_subscription',
                topic: config.planTopic,
                type: 'nav_msgs/msg/Path',
                throttle_rate: 200,
                queue_length: 1,
            });
        }

        function unsubscribeTopics() {
            sendRosbridge({op: 'unsubscribe', id: 'aurora_map_subscription', topic: config.mapTopic});
            sendRosbridge({op: 'unsubscribe', id: 'aurora_pose_subscription', topic: config.poseTopic});
            sendRosbridge({op: 'unsubscribe', id: 'aurora_plan_subscription', topic: config.planTopic});
        }

        function handleRosbridgeMessage(event) {
            if (typeof event.data !== 'string') return;

            let packet;
            try {
                packet = JSON.parse(event.data);
            } catch (error) {
                console.error('Không thể đọc dữ liệu rosbridge:', error);
                return;
            }

            if (packet.op === 'publish') {
                if (packet.topic === config.mapTopic) processMapMessage(packet.msg);
                if (packet.topic === config.poseTopic) processPoseMessage(packet.msg);
                if (packet.topic === config.planTopic) processPlanMessage(packet.msg);
                return;
            }

            if (packet.op === 'status' && packet.level === 'error') {
                console.error('Rosbridge status:', packet.msg);
                setBadge(rosStatus, 'ROS: Rosbridge báo lỗi', 'bg-rose-100 text-rose-700');
            }
        }

        function scheduleReconnect() {
            if (state.destroyed || state.reconnectTimer) return;
            state.reconnectTimer = window.setTimeout(() => {
                state.reconnectTimer = null;
                connect();
            }, 2000);
        }

        function connect() {
            if (state.destroyed) return;
            setBadge(rosStatus, 'ROS: Đang kết nối', 'bg-amber-100 text-amber-700');

            const socket = new WebSocket(websocketUrl());
            state.socket = socket;

            socket.onopen = () => {
                setBadge(rosStatus, `ROS: Đã kết nối ${websocketUrl()}`, 'bg-emerald-100 text-emerald-700');
                subscribeTopics();
            };

            socket.onmessage = handleRosbridgeMessage;

            socket.onerror = (error) => {
                console.error('Rosbridge WebSocket error:', error);
                setBadge(rosStatus, 'ROS: Lỗi kết nối', 'bg-rose-100 text-rose-700');
            };

            socket.onclose = () => {
                setBadge(rosStatus, 'ROS: Mất kết nối - đang thử lại', 'bg-rose-100 text-rose-700');
                scheduleReconnect();
            };
        }

        const resizeObserver = new ResizeObserver(() => render());
        resizeObserver.observe(canvas);

        window.__auroraLiveMap = {
            destroy() {
                state.destroyed = true;
                if (state.reconnectTimer) window.clearTimeout(state.reconnectTimer);
                unsubscribeTopics();
                resizeObserver.disconnect();
                try {
                    state.socket?.close();
                } catch (error) {
                    console.debug(error);
                }
            },
        };

        render();
        connect();
    })();
    """
    ui.run_javascript(script.replace("__AURORA_CONFIG__", json.dumps(config)))


def build_admin_dashboard() -> None:
    ui.add_head_html(
        """
        <style>
            body {
                margin: 0;
                background:
                    radial-gradient(circle at top left, rgba(14, 165, 233, 0.18), transparent 25%),
                    linear-gradient(135deg, #e0f2fe 0%, #f8fafc 42%, #ecfeff 100%);
            }
            .admin-shell {
                width: 100%;
                max-width: 1680px;
            }
            .admin-stat-card {
                border-radius: 28px;
                background: rgba(255, 255, 255, 0.92);
                box-shadow: 0 22px 40px rgba(15, 23, 42, 0.10);
            }
            .admin-panel {
                border-radius: 32px;
                background: rgba(255, 255, 255, 0.94);
                box-shadow: 0 26px 48px rgba(15, 23, 42, 0.12);
            }
        </style>
        """
    )

    state = robot_store.load()

    def battery_tone(level: int) -> str:
        if level >= 70:
            return "text-emerald-600"
        if level >= 40:
            return "text-amber-500"
        return "text-rose-500"

    def status_tone(status: str) -> str:
        mapping = {
            "Sẵn sàng": "bg-emerald-100 text-emerald-700",
            "Đang dẫn bệnh nhân": "bg-cyan-100 text-cyan-700",
            "Đang về HOME": "bg-emerald-100 text-emerald-700",
            "Đang sạc": "bg-amber-100 text-amber-700",
            "Tạm dừng": "bg-rose-100 text-rose-700",
            "Bảo trì": "bg-slate-200 text-slate-700",
        }
        return mapping.get(status, "bg-slate-100 text-slate-700")

    with ui.column().classes("w-full items-center px-6 py-8 md:px-10 xl:px-16"):
        with ui.column().classes("admin-shell gap-6"):
            with ui.row().classes("items-center justify-between gap-4 max-[900px]:flex-col max-[900px]:items-start"):
                with ui.column().classes("gap-2"):
                    ui.label("Admin Robot AURORA").classes("text-4xl font-black text-slate-900")
                    ui.label("Trang quản trị nhận dữ liệu từ web đặt lịch và quản lý robot hỗ trợ.").classes(
                        "text-base text-slate-600"
                    )
                with ui.row().classes("gap-3"):
                    ui.button(
                        "Mở trang web bệnh nhân",
                        on_click=lambda: ui.navigate.to("/"),
                    ).props("outline no-caps").classes(
                        "rounded-full border-cyan-500 px-5 py-3 font-bold text-cyan-600"
                    )
                    ui.button(
                        "Làm mới",
                        on_click=lambda: ui.navigate.to("/admin"),
                    ).props("unelevated no-caps icon=refresh").classes(
                        "rounded-full bg-cyan-500 px-5 py-3 font-bold text-white"
                    )

            with ui.row().classes("w-full gap-5 max-[1000px]:flex-col"):
                with ui.card().classes("admin-stat-card flex-1 p-6"):
                    ui.label("Lịch hẹn từ web").classes("text-sm font-bold uppercase tracking-[0.2em] text-cyan-600")
                    ui.label(str(store.count_appointments())).classes("mt-3 text-4xl font-black text-slate-900")
                    ui.label("Các lịch bệnh nhân đặt trên web sẽ tự động hiển thị tại admin.").classes(
                        "mt-2 text-sm leading-6 text-slate-600"
                    )
                with ui.card().classes("admin-stat-card flex-1 p-6"):
                    ui.label("Tài khoản bệnh nhân").classes("text-sm font-bold uppercase tracking-[0.2em] text-cyan-600")
                    ui.label(str(len(list_registered_patient_phones()))).classes("mt-3 text-4xl font-black text-slate-900")
                    ui.label("Danh sách số điện thoại đã tạo tài khoản để admin đối soát.").classes(
                        "mt-2 text-sm leading-6 text-slate-600"
                    )
                with ui.card().classes("admin-stat-card flex-1 p-6"):
                    ui.label("Robot hiện tại").classes("text-sm font-bold uppercase tracking-[0.2em] text-cyan-600")
                    ui.label(state.robot_name).classes("mt-3 text-4xl font-black text-slate-900")
                    ui.label(state.status).classes(
                        f"mt-3 inline-flex rounded-full px-4 py-2 text-sm font-black {status_tone(state.status)}"
                    )

            with ui.row().classes("w-full items-start gap-6 max-[1200px]:flex-col"):
                with ui.card().classes("admin-panel w-[440px] max-w-full shrink-0 p-7"):
                    ui.label("Quản lý robot").classes("text-2xl font-black text-slate-900")
                    ui.label("Cập nhật thông số robot để đội vận hành theo dõi trên một trang riêng.").classes(
                        "mt-2 text-sm leading-6 text-slate-600"
                    )

                    robot_name_input = ui.input("Tên robot", value=state.robot_name).props("outlined dense").classes("mt-5 w-full")
                    robot_status_input = ui.select(
                        ["Sẵn sàng", "Đang dẫn bệnh nhân", "Đang về HOME", "Đang sạc", "Tạm dừng", "Bảo trì"],
                        value=state.status,
                        label="Trạng thái",
                    ).props("outlined dense options-dense").classes("w-full")
                    robot_zone_input = ui.input("Khu vực hiện tại", value=state.current_zone).props("outlined dense").classes("w-full")
                    robot_battery_input = ui.number("Pin (%)", value=state.battery_level, min=0, max=100).props("outlined dense").classes(
                        "w-full"
                    )
                    queue_limit_input = ui.number(
                        "Số bệnh nhân robot có thể nhận",
                        value=state.queue_limit,
                        min=1,
                        max=99,
                    ).props("outlined dense").classes("w-full")
                    auto_dispatch_switch = ui.switch("Tự động nhận bệnh nhân mới", value=state.auto_dispatch).classes("mt-2")
                    robot_note_input = ui.textarea("Ghi chú vận hành", value=state.note).props("outlined").classes("w-full")

                    def save_robot_state() -> None:
                        robot_store.update(
                            robot_name=str(robot_name_input.value or ""),
                            status=str(robot_status_input.value or ""),
                            current_zone=str(robot_zone_input.value or ""),
                            battery_level=int(robot_battery_input.value or 0),
                            queue_limit=int(queue_limit_input.value or 1),
                            auto_dispatch=bool(auto_dispatch_switch.value),
                            note=str(robot_note_input.value or ""),
                        )
                        ui.notify("Đã lưu trạng thái robot.", color="positive")
                        ui.navigate.to("/admin")

                    ui.button("Lưu robot", on_click=save_robot_state).props("unelevated no-caps").classes(
                        "mt-4 w-full rounded-full bg-cyan-500 py-3 font-bold text-white"
                    )

                    ui.separator().classes("my-6")
                    ui.label("Lệnh điều hướng robot").classes("text-2xl font-black text-slate-900")
                    ui.label(
                        "Nhập tọa độ HOME trên map. Khi bấm HOME, admin sẽ ghi lệnh vào robot_command.json để node ROS2 đọc và publish /goal_pose."
                    ).classes("mt-2 text-sm leading-6 text-slate-600")
                    ui.label(f"File lệnh: {ROBOT_COMMAND_PATH}").classes("mt-2 text-xs leading-5 text-slate-500")

                    home_x_input = ui.number("Home x", value=DEFAULT_HOME_POSE["x"]).props("outlined dense").classes("mt-4 w-full")
                    home_y_input = ui.number("Home y", value=DEFAULT_HOME_POSE["y"]).props("outlined dense").classes("w-full")
                    home_z_input = ui.number("Home orientation z", value=DEFAULT_HOME_POSE["z"]).props("outlined dense").classes("w-full")
                    home_w_input = ui.number("Home orientation w", value=DEFAULT_HOME_POSE["w"]).props("outlined dense").classes("w-full")

                    def send_robot_home() -> None:
                        pose = {
                            "x": float(home_x_input.value or 0.0),
                            "y": float(home_y_input.value or 0.0),
                            "z": float(home_z_input.value or 0.0),
                            "w": float(home_w_input.value or 1.0),
                        }

                        command_payload = {
                            "command": "go_home",
                            "target": "home",
                            "source": "web_admin",
                            "status": "pending",
                            "created_at": datetime.now().isoformat(timespec="seconds"),
                            "pose": pose,
                        }

                        try:
                            ROBOT_COMMAND_PATH.parent.mkdir(parents=True, exist_ok=True)
                            ROBOT_COMMAND_PATH.write_text(
                                json.dumps(command_payload, ensure_ascii=False, indent=2),
                                encoding="utf-8",
                            )
                        except OSError as error:
                            ui.notify(f"Không thể ghi robot_command.json: {error}", color="negative")
                            return

                        robot_store.update(
                            robot_name=str(robot_name_input.value or ""),
                            status="Đang về HOME",
                            current_zone="Đang di chuyển về HOME",
                            battery_level=int(robot_battery_input.value or 0),
                            queue_limit=int(queue_limit_input.value or 1),
                            auto_dispatch=bool(auto_dispatch_switch.value),
                            note=f"Admin đã gửi lệnh HOME cho robot. File: {ROBOT_COMMAND_PATH}",
                        )

                        robot_status_input.set_value("Đang về HOME")
                        robot_zone_input.set_value("Đang di chuyển về HOME")
                        robot_note_input.set_value(f"Admin đã gửi lệnh HOME cho robot. File: {ROBOT_COMMAND_PATH}")

                        ui.notify("Đã gửi lệnh HOME cho robot.", color="positive")

                        # QUAN TRỌNG:
                        # Không dùng ui.navigate.to("/admin") ở đây,
                        # vì dòng đó làm trang admin load lại sau khi bấm HOME.

                    ui.button("HOME - Gọi robot quay về", on_click=send_robot_home).props(
                        "unelevated no-caps icon=home"
                    ).classes(
                        "mt-4 w-full rounded-full bg-emerald-500 py-3 font-bold text-white"
                    )

                with ui.column().classes("min-w-0 flex-1 gap-6"):
                    build_live_map_panel()

                    with ui.card().classes("admin-panel p-7"):
                        ui.label("Tình trạng robot").classes("text-2xl font-black text-slate-900")
                        with ui.grid(columns=2).classes("mt-5 w-full gap-4 max-[800px]:grid-cols-1"):
                            with ui.card().classes("rounded-3xl bg-slate-950 p-5 text-white shadow-none"):
                                ui.label("Khu vực hiện tại").classes("text-sm uppercase tracking-[0.18em] text-cyan-200")
                                ui.label(state.current_zone).classes("mt-3 text-2xl font-black")
                            with ui.card().classes("rounded-3xl bg-white p-5 shadow-none ring-1 ring-slate-200"):
                                ui.label("Pin").classes("text-sm uppercase tracking-[0.18em] text-slate-500")
                                ui.label(f"{state.battery_level}%").classes(
                                    f"mt-3 text-3xl font-black {battery_tone(state.battery_level)}"
                                )
                            with ui.card().classes("rounded-3xl bg-white p-5 shadow-none ring-1 ring-slate-200"):
                                ui.label("Giới hạn tiếp nhận").classes("text-sm uppercase tracking-[0.18em] text-slate-500")
                                ui.label(str(state.queue_limit)).classes("mt-3 text-3xl font-black text-slate-900")
                            with ui.card().classes("rounded-3xl bg-white p-5 shadow-none ring-1 ring-slate-200"):
                                ui.label("Tự động điều phối").classes("text-sm uppercase tracking-[0.18em] text-slate-500")
                                ui.label("Bật" if state.auto_dispatch else "Tắt").classes("mt-3 text-3xl font-black text-slate-900")
                        ui.label(state.note or "Chưa có ghi chú vận hành.").classes("mt-5 text-base leading-7 text-slate-600")
                        ui.label(f"Cập nhật lần cuối: {state.updated_at}").classes("mt-2 text-sm font-semibold text-cyan-700")

                    with ui.card().classes("admin-panel p-7"):
                        ui.label("Dữ liệu web gửi sang admin").classes("text-2xl font-black text-slate-900")
                        ui.label("Mỗi lịch hẹn đặt trên web sẽ được đọc từ cùng cơ sở dữ liệu ở đây.").classes(
                            "mt-2 text-sm leading-6 text-slate-600"
                        )
                        appointments_table_admin = ui.table(
                            columns=[
                                {"name": "id", "label": "STT", "field": "id", "align": "left"},
                                {"name": "patient_name", "label": "Bệnh nhân", "field": "patient_name", "align": "left"},
                                {"name": "phone", "label": "Điện thoại", "field": "phone", "align": "left"},
                                {"name": "department", "label": "Khoa", "field": "department", "align": "left"},
                                {"name": "appointment_date", "label": "Ngày khám", "field": "appointment_date", "align": "left"},
                                {"name": "appointment_time", "label": "Giờ khám", "field": "appointment_time", "align": "left"},
                                {"name": "symptoms", "label": "Triệu chứng", "field": "symptoms", "align": "left"},
                                {"name": "created_at", "label": "Tạo lúc", "field": "created_at", "align": "left"},
                            ],
                            rows=format_appointments(store.list_appointments(limit=100)),
                            row_key="id",
                        ).classes("mt-5 w-full overflow-hidden rounded-3xl bg-white")
                        appointments_table_admin.props("flat bordered wrap-cells")

                    with ui.card().classes("admin-panel p-7"):
                        ui.label("Danh sách tài khoản").classes("text-2xl font-black text-slate-900")
                        accounts_table_admin = ui.table(
                            columns=[
                                {"name": "phone", "label": "Số điện thoại", "field": "phone", "align": "left"},
                            ],
                            rows=[{"phone": phone} for phone in list_registered_patient_phones()],
                            row_key="phone",
                        ).classes("mt-5 w-full overflow-hidden rounded-3xl bg-white")
                        accounts_table_admin.props("flat bordered")

                    with ui.card().classes("admin-panel p-7"):
                        ui.label("Hồ sơ khuôn mặt cho robot").classes("text-2xl font-black text-slate-900")
                        ui.label(
                            "Mỗi lần bệnh nhân chụp ảnh trong web, hệ thống sẽ lưu hồ sơ chung để web admin theo dõi và robot dùng lại khi xác minh."
                        ).classes("mt-2 text-sm leading-6 text-slate-600")
                        robot_patient_table = ui.table(
                            columns=[
                                {"name": "patient_name", "label": "Bệnh nhân", "field": "patient_name", "align": "left"},
                                {"name": "phone", "label": "Điện thoại", "field": "phone", "align": "left"},
                                {"name": "face_capture_count", "label": "Số ảnh", "field": "face_capture_count", "align": "left"},
                                {"name": "latest_capture_at", "label": "Chụp gần nhất", "field": "latest_capture_at", "align": "left"},
                                {"name": "queue_number", "label": "STT", "field": "queue_number", "align": "left"},
                                {"name": "department", "label": "Khoa", "field": "department", "align": "left"},
                                {"name": "room_label", "label": "Phòng", "field": "room_label", "align": "left"},
                                {"name": "appointment_date", "label": "Ngày khám", "field": "appointment_date", "align": "left"},
                                {"name": "appointment_time", "label": "Giờ", "field": "appointment_time", "align": "left"},
                            ],
                            rows=format_robot_patient_profiles(load_robot_patient_profiles()),
                            row_key="phone",
                        ).classes("mt-5 w-full overflow-hidden rounded-3xl bg-white")
                        robot_patient_table.props("flat bordered wrap-cells")

                    with ui.card().classes("admin-panel p-7"):
                        ui.label("Bảng triệu chứng - phòng khám").classes("text-2xl font-black text-slate-900")
                        ui.label(
                            "Nhập quy tắc triệu chứng, khoa, phòng khám và tọa độ đích trong cùng một biểu mẫu. "
                            "Khi lưu, mapping được thêm vào hệ thống và tọa độ phòng được cập nhật trong patient_information.json."
                        ).classes("mt-2 text-sm leading-6 text-slate-600")
                        ui.label(f"File tọa độ: {PATIENT_INFORMATION_PATH}").classes(
                            "mt-2 break-all text-xs leading-5 text-slate-500"
                        )

                        symptom_input = ui.textarea("Triệu chứng / từ khóa").props("outlined").classes("mt-5 w-full")
                        department_input = ui.input("Khoa khám").props("outlined dense").classes("w-full")
                        room_input = ui.input("Phòng khám", placeholder="Ví dụ: 101").props(
                            "outlined dense"
                        ).classes("w-full")

                        with ui.grid(columns=3).classes("w-full gap-3 max-[900px]:grid-cols-1"):
                            coordinate_x_input = ui.number(
                                "Tọa độ x (m)", value=None, step=0.01
                            ).props("outlined dense clearable").classes("w-full")
                            coordinate_y_input = ui.number(
                                "Tọa độ y (m)", value=None, step=0.01
                            ).props("outlined dense clearable").classes("w-full")
                            coordinate_theta_input = ui.number(
                                "Góc θ (rad)", value=None, step=0.01
                            ).props("outlined dense clearable").classes("w-full")

                        ui.label(
                            "Điền đủ X, Y và θ để lưu hoặc cập nhật tọa độ phòng. Nếu chỉ muốn thêm mapping mà không đổi tọa độ hiện có, "
                            "hãy để trống cả ba ô tọa độ. θ được nhập trực tiếp theo radian và tự chuyển sang orientation z, w."
                        ).classes("mt-1 text-xs leading-5 text-slate-500")

                        symptom_note_input = ui.textarea("Ghi chú").props("outlined").classes("w-full")
                        delete_rule_id_input = ui.number("ID mapping cần xóa", min=1, step=1).props(
                            "outlined dense"
                        ).classes("w-full")

                        ui.label("Danh sách mapping triệu chứng - phòng khám").classes(
                            "mt-5 text-base font-black text-slate-800"
                        )
                        symptom_rules_table = ui.table(
                            columns=[
                                {"name": "id", "label": "ID", "field": "id", "align": "left"},
                                {"name": "symptom_keywords", "label": "Triệu chứng", "field": "symptom_keywords", "align": "left"},
                                {"name": "department", "label": "Khoa", "field": "department", "align": "left"},
                                {"name": "room_label", "label": "Phòng khám", "field": "room_label", "align": "left"},
                                {"name": "note", "label": "Ghi chú", "field": "note", "align": "left"},
                            ],
                            rows=format_symptom_room_rules(symptom_rule_store.list_rules()),
                            row_key="id",
                        ).classes("mt-3 w-full overflow-hidden rounded-3xl bg-white")
                        symptom_rules_table.props("flat bordered wrap-cells")

                        ui.label("Danh sách tọa độ phòng khám").classes(
                            "mt-6 text-base font-black text-slate-800"
                        )
                        room_destinations_table = ui.table(
                            columns=[
                                {"name": "room_label", "label": "Phòng", "field": "room_label", "align": "left"},
                                {"name": "x", "label": "X", "field": "x", "align": "left"},
                                {"name": "y", "label": "Y", "field": "y", "align": "left"},
                                {"name": "theta_rad", "label": "Theta (rad)", "field": "theta_rad", "align": "left"},
                                {"name": "theta_deg", "label": "Theta (°)", "field": "theta_deg", "align": "left"},
                                {"name": "z", "label": "Orientation Z", "field": "z", "align": "left"},
                                {"name": "w", "label": "Orientation W", "field": "w", "align": "left"},
                            ],
                            rows=format_room_destinations(),
                            row_key="room_label",
                        ).classes("mt-3 w-full overflow-hidden rounded-3xl bg-white")
                        room_destinations_table.props("flat bordered wrap-cells")

                        def refresh_symptom_rules_table() -> None:
                            symptom_rules_table.rows = format_symptom_room_rules(symptom_rule_store.list_rules())
                            symptom_rules_table.update()

                        def refresh_room_destinations_table() -> None:
                            room_destinations_table.rows = format_room_destinations()
                            room_destinations_table.update()

                        def clear_mapping_form() -> None:
                            symptom_input.set_value("")
                            department_input.set_value("")
                            room_input.set_value("")
                            coordinate_x_input.set_value(None)
                            coordinate_y_input.set_value(None)
                            coordinate_theta_input.set_value(None)
                            symptom_note_input.set_value("")

                        def save_mapping_and_coordinates() -> None:
                            symptom_keywords = str(symptom_input.value or "").strip()
                            department = str(department_input.value or "").strip()
                            room_label = str(room_input.value or "").strip()
                            note = str(symptom_note_input.value or "").strip()

                            if not symptom_keywords:
                                ui.notify("Vui lòng nhập triệu chứng hoặc từ khóa.", color="negative")
                                return
                            if not department:
                                ui.notify("Vui lòng nhập khoa khám.", color="negative")
                                return
                            if not room_label:
                                ui.notify("Vui lòng nhập phòng khám.", color="negative")
                                return

                            coordinate_values = (
                                coordinate_x_input.value,
                                coordinate_y_input.value,
                                coordinate_theta_input.value,
                            )
                            has_any_coordinate = any(value is not None for value in coordinate_values)
                            has_all_coordinates = all(value is not None for value in coordinate_values)

                            if has_any_coordinate and not has_all_coordinates:
                                ui.notify("Muốn lưu tọa độ, bạn phải nhập đủ X, Y và θ.", color="negative")
                                return

                            try:
                                # Lưu tọa độ trước để kiểm tra dữ liệu số và đường dẫn JSON.
                                if has_all_coordinates:
                                    save_room_destination(
                                        room_label=room_label,
                                        x=float(coordinate_x_input.value),
                                        y=float(coordinate_y_input.value),
                                        theta_rad=float(coordinate_theta_input.value),
                                    )

                                symptom_rule_store.create_rule(
                                    symptom_keywords=symptom_keywords,
                                    department=department,
                                    room_label=room_label,
                                    note=note,
                                )
                            except (TypeError, ValueError) as error:
                                ui.notify(str(error), color="negative")
                                refresh_room_destinations_table()
                                return

                            refresh_symptom_rules_table()
                            refresh_room_destinations_table()
                            clear_mapping_form()

                            if has_all_coordinates:
                                ui.notify(
                                    f"Đã lưu mapping và tọa độ phòng {room_label}.",
                                    color="positive",
                                )
                            else:
                                ui.notify(
                                    f"Đã lưu mapping cho phòng {room_label}; tọa độ hiện có được giữ nguyên.",
                                    color="positive",
                                )

                        def delete_symptom_rule() -> None:
                            rule_id = int(delete_rule_id_input.value or 0)
                            if rule_id <= 0:
                                ui.notify("Vui lòng nhập ID mapping hợp lệ để xóa.", color="negative")
                                return
                            if not symptom_rule_store.delete_rule(rule_id):
                                ui.notify(f"Không tìm thấy mapping có ID {rule_id}.", color="negative")
                                return
                            delete_rule_id_input.set_value(None)
                            refresh_symptom_rules_table()
                            ui.notify(f"Đã xóa mapping ID {rule_id}.", color="positive")

                        def delete_room_coordinates() -> None:
                            room_label = str(room_input.value or "").strip()
                            try:
                                delete_room_destination(room_label)
                            except (TypeError, ValueError) as error:
                                ui.notify(str(error), color="negative")
                                return

                            refresh_room_destinations_table()
                            coordinate_x_input.set_value(None)
                            coordinate_y_input.set_value(None)
                            coordinate_theta_input.set_value(None)
                            ui.notify(f"Đã xóa tọa độ phòng {room_label}.", color="positive")

                        with ui.row().classes("mt-4 w-full flex-wrap gap-3"):
                            ui.button("Lưu mapping và tọa độ", on_click=save_mapping_and_coordinates).props(
                                "unelevated no-caps icon=save"
                            ).classes("rounded-full bg-cyan-500 px-5 py-3 font-bold text-white")
                            ui.button("Xóa mapping theo ID", on_click=delete_symptom_rule).props(
                                "outline no-caps icon=delete"
                            ).classes("rounded-full border-rose-300 px-5 py-3 font-bold text-rose-600")
                            ui.button("Xóa tọa độ phòng", on_click=delete_room_coordinates).props(
                                "unelevated no-caps icon=location_off"
                            ).classes("rounded-full bg-red-500 px-5 py-3 font-bold text-white")


@ui.page("/admin")
def admin_page() -> None:
    build_admin_dashboard()


@ui.page("/")
def patient_page() -> None:
    with ui.column().classes("w-full h-screen items-center justify-center bg-slate-50 gap-6"):
        ui.label("Đây là Trang Web Bệnh Nhân (Đang xây dựng)").classes("text-3xl font-black text-slate-800")
        ui.label("Bấm vào nút bên dưới để vào trang quản trị nhé!").classes("text-base text-slate-600")

        ui.button(
            "Vào trang Admin ngay",
            on_click=lambda: ui.navigate.to("/admin"),
        ).props("unelevated no-caps").classes(
            "rounded-full bg-cyan-500 px-8 py-4 font-bold text-white text-lg shadow-lg hover:bg-cyan-600"
        )


if __name__ in {"__main__", "__mp_main__"}:
    ui.run(
        host=os.getenv("NICEGUI_HOST", "0.0.0.0"),
        port=int(os.getenv("NICEGUI_PORT", "8081")),
        title="Robot Hospital Booking",
        show=True,
        reload=False,
    )