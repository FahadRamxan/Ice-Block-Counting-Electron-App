"""
Run ice-block counting on a video file. Returns total unique block count.
Uses same logic as Solution.py (YOLO segment + slot registry).
"""
import os
import sys

# Add project root for shared model path
_backend = os.path.dirname(os.path.abspath(__file__))
_root = os.path.dirname(_backend)
if _root not in sys.path:
    sys.path.insert(0, _root)

import cv2
from collections import deque
from collections import Counter

ICE_BLOCK_CLASS_ID = 0
PLATFORM_CLASS_ID = 1
ON_PLATFORM_THRESHOLD = 0.35
LEAVING_CONFIRM_FRAMES = 15
MIN_CONFIRM_FRAMES = 3
CONF_THRESHOLD = 0.75
DUPLICATE_DISTANCE_PX = 80
REID_DISTANCE_PX = 120
SLOT_MEMORY_FRAMES = 500
SMOOTH_WINDOW = 15


def overlap_ratio(boxA, boxB):
    xA = max(boxA[0], boxB[0]); yA = max(boxA[1], boxB[1])
    xB = min(boxA[2], boxB[2]); yB = min(boxA[3], boxB[3])
    inter = max(0, xB - xA) * max(0, yB - yA)
    aA = (boxA[2] - boxA[0]) * (boxA[3] - boxA[1])
    return inter / aA if aA > 0 else 0.0


def centroid(box):
    return ((box[0] + box[2]) / 2, (box[1] + box[3]) / 2)


def dist(c1, c2):
    return ((c1[0] - c2[0]) ** 2 + (c1[1] - c2[1]) ** 2) ** 0.5


def box_area(b):
    return (b[2] - b[0]) * (b[3] - b[1])


def mode_count(d):
    return Counter(d).most_common(1)[0][0] if d else 0


class SlotRegistry:
    def __init__(self):
        self.slots = {}
        self.tid_to_slot = {}
        self.total_count = 0
        self._next_slot = 1

    def update(self, confirmed_detections, frame_idx):
        seen_tids = set()
        for tid, box in confirmed_detections:
            c = centroid(box)
            seen_tids.add(tid)
            if tid in self.tid_to_slot:
                sid = self.tid_to_slot[tid]
                s = self.slots[sid]
                s["centroid"] = c
                s["active"] = True
                s["frames_gone"] = 0
                s["expired"] = False
            else:
                near_active_sid, near_active_dist = None, float("inf")
                near_inactive_sid, near_inactive_dist = None, float("inf")
                for sid, slot in self.slots.items():
                    if slot["expired"]:
                        continue
                    d = dist(c, slot["centroid"])
                    if slot["active"]:
                        if d < near_active_dist:
                            near_active_dist = d
                            near_active_sid = sid
                    else:
                        if d < near_inactive_dist:
                            near_inactive_dist = d
                            near_inactive_sid = sid
                if near_active_sid is not None and near_active_dist < DUPLICATE_DISTANCE_PX:
                    self.tid_to_slot[tid] = near_active_sid
                elif near_inactive_sid is not None and near_inactive_dist < REID_DISTANCE_PX:
                    old_tid = self.slots[near_inactive_sid]["tid"]
                    self.slots[near_inactive_sid]["tid"] = tid
                    self.slots[near_inactive_sid]["centroid"] = c
                    self.slots[near_inactive_sid]["active"] = True
                    self.slots[near_inactive_sid]["frames_gone"] = 0
                    self.slots[near_inactive_sid]["expired"] = False
                    self.tid_to_slot.pop(old_tid, None)
                    self.tid_to_slot[tid] = near_inactive_sid
                else:
                    sid = self._next_slot
                    self._next_slot += 1
                    self.slots[sid] = {
                        "tid": tid, "centroid": c, "active": True,
                        "frames_gone": 0, "expired": False, "first_frame": frame_idx,
                    }
                    self.tid_to_slot[tid] = sid
                    self.total_count += 1
        for sid, slot in self.slots.items():
            if slot["tid"] not in seen_tids and not slot["expired"]:
                slot["frames_gone"] += 1
                if slot["frames_gone"] >= LEAVING_CONFIRM_FRAMES:
                    slot["active"] = False
                if slot["frames_gone"] >= SLOT_MEMORY_FRAMES:
                    slot["expired"] = True
                    self.tid_to_slot.pop(slot["tid"], None)
        current_on = sum(1 for s in self.slots.values() if s["active"])
        return self.total_count, current_on


class BlockTrack:
    def __init__(self):
        self.frames_on = 0
        self.confirmed = False
        self.last_box = None

    def update(self, box, ratio):
        self.last_box = box
        if ratio >= ON_PLATFORM_THRESHOLD:
            self.frames_on += 1
        if self.frames_on >= MIN_CONFIRM_FRAMES:
            self.confirmed = True


def run_count(video_path: str, model_path: str, start_second: float = 0, end_second: float | None = None):
    """
    Run ice-block counting on video. Returns dict with total_count and optional error.
    """
    if not os.path.isfile(video_path):
        return {"error": f"Video file not found: {video_path}", "total_count": 0}
    if not os.path.isfile(model_path):
        return {"error": f"Model file not found: {model_path}", "total_count": 0}
    try:
        from ultralytics import YOLO
    except ImportError:
        return {"error": "ultralytics not installed", "total_count": 0}

    cap = cv2.VideoCapture(video_path)
    if not cap.isOpened():
        return {"error": "Could not open video", "total_count": 0}
    fps = cap.get(cv2.CAP_PROP_FPS)
    total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    start_frame = int(start_second * fps)
    end_frame = int(end_second * fps) if end_second is not None else total_frames
    end_frame = min(end_frame, total_frames)

    model = YOLO(model_path, task="segment")
    block_tracks = {}
    registry = SlotRegistry()
    last_plat_box = None
    frame_idx = start_frame
    cap.set(cv2.CAP_PROP_POS_FRAMES, start_frame)

    while cap.isOpened() and frame_idx < end_frame:
        success, im0 = cap.read()
        if not success:
            break
        results = model.track(im0, persist=True, verbose=False)
        r = results[0]
        ice_detections = {}
        platform_boxes = []
        if r.boxes is not None and len(r.boxes) > 0:
            for box in r.boxes:
                cls = int(box.cls[0])
                conf = float(box.conf[0])
                b = list(map(int, box.xyxy[0].tolist()))
                tid = int(box.id[0]) if box.id is not None else None
                if cls == PLATFORM_CLASS_ID:
                    platform_boxes.append(b)
                elif cls == ICE_BLOCK_CLASS_ID and tid is not None and conf >= CONF_THRESHOLD:
                    if tid not in ice_detections or conf > ice_detections[tid][1]:
                        ice_detections[tid] = (b, conf)
        if platform_boxes:
            last_plat_box = max(platform_boxes, key=box_area)
        confirmed = []
        if last_plat_box is not None:
            for tid, (b, conf) in ice_detections.items():
                if tid not in block_tracks:
                    block_tracks[tid] = BlockTrack()
                ratio = overlap_ratio(b, last_plat_box)
                block_tracks[tid].update(b, ratio)
                if block_tracks[tid].confirmed:
                    confirmed.append((tid, b))
        registry.update(confirmed, frame_idx)
        frame_idx += 1

    cap.release()
    return {"total_count": registry.total_count, "error": None}


if __name__ == "__main__":
    import json
    if len(sys.argv) < 3:
        print(json.dumps({"error": "Usage: model_runner.py <video_path> <model_path>", "total_count": 0}))
        sys.exit(1)
    out = run_count(sys.argv[1], sys.argv[2])
    print(json.dumps(out))
