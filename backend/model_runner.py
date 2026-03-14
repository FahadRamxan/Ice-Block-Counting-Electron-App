"""
Same counting logic as Solution.py. Returns everything Solution prints + output file paths.
Prerequisites: opencv-python, numpy, pandas, ultralytics; YOLO .pt model; readable video file.
"""
import os
import sys
from collections import deque
from datetime import datetime

import cv2
import numpy as np
import pandas as pd
from ultralytics import YOLO

ICE_BLOCK_CLASS_ID = 0
PLATFORM_CLASS_ID = 1
START_SECOND = 0
END_SECOND = None
ON_PLATFORM_THRESHOLD = 0.35
LEAVING_CONFIRM_FRAMES = 15
MIN_CONFIRM_FRAMES = 3
CONF_THRESHOLD = 0.75
DUPLICATE_DISTANCE_PX = 80
REID_DISTANCE_PX = 120
SLOT_MEMORY_FRAMES = 500
SMOOTH_WINDOW = 15


def overlap_ratio(boxA, boxB):
    xA, yA = max(boxA[0], boxB[0]), max(boxA[1], boxB[1])
    xB, yB = min(boxA[2], boxB[2]), min(boxA[3], boxB[3])
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
    from collections import Counter
    return Counter(d).most_common(1)[0][0] if d else 0


class SlotRegistry:
    def __init__(self):
        self.slots = {}
        self.tid_to_slot = {}
        self.total_count = 0
        self._next_slot = 1
        self._logged = set()

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
                for sid, s in self.slots.items():
                    if s["expired"]:
                        continue
                    d = dist(c, s["centroid"])
                    if s["active"] and d < near_active_dist:
                        near_active_dist, near_active_sid = d, sid
                    if not s["active"] and d < near_inactive_dist:
                        near_inactive_dist, near_inactive_sid = d, sid
                if near_active_sid is not None and near_active_dist < DUPLICATE_DISTANCE_PX:
                    self.tid_to_slot[tid] = near_active_sid
                    s = self.slots[near_active_sid]
                    s["centroid"] = c
                    s["active"] = True
                    s["frames_gone"] = 0
                elif near_inactive_sid is not None and near_inactive_dist < REID_DISTANCE_PX:
                    self.tid_to_slot[tid] = near_inactive_sid
                    s = self.slots[near_inactive_sid]
                    s["centroid"] = c
                    s["active"] = True
                    s["frames_gone"] = 0
                    s["expired"] = False
                else:
                    sid = self._next_slot
                    self._next_slot += 1
                    self.slots[sid] = {
                        "centroid": c, "active": True, "frames_gone": 0, "expired": False,
                    }
                    self.tid_to_slot[tid] = sid
                    self.total_count += 1
        for tid in list(self.tid_to_slot.keys()):
            if tid not in seen_tids:
                sid = self.tid_to_slot[tid]
                s = self.slots[sid]
                s["active"] = False
                s["frames_gone"] = s.get("frames_gone", 0) + 1
                if s["frames_gone"] > LEAVING_CONFIRM_FRAMES:
                    s["expired"] = True
        current_on = sum(1 for s in self.slots.values() if s["active"] and not s["expired"])
        return self.total_count, current_on


class BlockTrack:
    def __init__(self):
        self.frames_on = 0
        self.confirmed = False

    def update(self, box, ratio_on_platform):
        if ratio_on_platform >= ON_PLATFORM_THRESHOLD:
            self.frames_on += 1
        else:
            self.frames_on = 0
        if self.frames_on >= MIN_CONFIRM_FRAMES:
            self.confirmed = True


def run_solution_style(
    video_path: str,
    model_path: str,
    out_dir: str | None = None,
    progress_callback=None,
    max_frames: int | None = None,
):
    """
    Run full Solution.py pipeline. Returns dict for API/UI.
    Local file path only (not Google Drive URLs — download first).
    """
    logs = []
    def L(msg):
        logs.append(msg)

    if not os.path.isfile(model_path):
        return {"error": f"Model not found: {model_path}", "logs": logs}
    if not os.path.isfile(video_path):
        return {"error": f"Video not found: {video_path}", "logs": logs}
    try:
        cap = cv2.VideoCapture(video_path)
        if not cap.isOpened():
            return {"error": "Could not open video", "logs": logs}
    except Exception as e:
        return {"error": str(e), "logs": logs}

    fps = cap.get(cv2.CAP_PROP_FPS) or 25.0
    total = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    w = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    h = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    start_frame = int(START_SECOND * fps)
    end_frame = min(int(END_SECOND * fps) if END_SECOND is not None else total, total)
    if max_frames is not None and max_frames > 0:
        end_frame = min(end_frame, start_frame + max_frames)
        L(f"LIMITED RUN: first {max_frames} frames only (faster preview)")

    L(f"Video : {w}x{h} @ {fps:.1f}fps")
    L(f"Range : {start_frame/fps:.1f}s → {end_frame/fps:.1f}s ({end_frame - start_frame} frames)")
    L(f"Dup   : merge into active slot within {DUPLICATE_DISTANCE_PX}px")
    L(f"Re-ID : reclaim inactive slot within {REID_DISTANCE_PX}px")
    L(f"Memory: {SLOT_MEMORY_FRAMES} frames ({SLOT_MEMORY_FRAMES/fps:.1f}s)")
    L("=" * 65)

    if out_dir is None:
        out_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data", "outputs")
    os.makedirs(out_dir, exist_ok=True)
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    output_video = os.path.join(out_dir, f"ice_block_total_count_{ts}.avi")
    output_csv = os.path.join(out_dir, f"ice_block_events_{ts}.csv")

    cap.set(cv2.CAP_PROP_POS_FRAMES, start_frame)
    vw = cv2.VideoWriter(output_video, cv2.VideoWriter_fourcc(*"mp4v"), fps, (w, h))
    try:
        model = YOLO(model_path, task="segment")
    except Exception as e:
        cap.release()
        return {"error": f"YOLO load failed: {e}", "logs": logs}

    block_tracks = {}
    registry = SlotRegistry()
    last_plat_box = None
    count_history = deque(maxlen=SMOOTH_WINDOW)
    frame_log = []
    frame_idx = start_frame
    total_to_process = max(1, end_frame - start_frame)

    while cap.isOpened() and frame_idx < end_frame:
        success, im0 = cap.read()
        if not success:
            break
        done = frame_idx - start_frame + 1
        if progress_callback and (done == 1 or done % 15 == 0 or frame_idx == end_frame - 1):
            try:
                progress_callback(done, total_to_process, frame_idx / fps)
            except Exception:
                pass
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
        t_sec = frame_idx / fps
        confirmed = []
        if last_plat_box is not None:
            for tid, (b, conf) in ice_detections.items():
                if tid not in block_tracks:
                    block_tracks[tid] = BlockTrack()
                ratio = overlap_ratio(b, last_plat_box)
                block_tracks[tid].update(b, ratio)
                if block_tracks[tid].confirmed:
                    confirmed.append((tid, b))
                frame_log.append({
                    "frame": frame_idx, "time_sec": round(t_sec, 3),
                    "track_id": tid, "overlap_ratio": round(ratio, 4), "conf": round(conf, 3),
                })
        total_count, current_on = registry.update(confirmed, frame_idx)
        count_history.append(current_on)
        smooth_now = mode_count(count_history)
        vis = im0.copy()
        if last_plat_box:
            cv2.rectangle(vis, (last_plat_box[0], last_plat_box[1]), (last_plat_box[2], last_plat_box[3]), (0, 200, 255), 2)
        for sid, slot in registry.slots.items():
            if slot["expired"]:
                continue
            cx, cy = int(slot["centroid"][0]), int(slot["centroid"][1])
            if slot["active"]:
                cv2.circle(vis, (cx, cy), 16, (0, 255, 100), -1)
            else:
                cv2.circle(vis, (cx, cy), 16, (100, 100, 255), 2)
        for tid, (b, conf) in ice_detections.items():
            track = block_tracks.get(tid)
            ok = track and track.confirmed
            ratio = overlap_ratio(b, last_plat_box) if last_plat_box else 0
            color = (0, 255, 0) if ok else (180, 180, 180)
            cv2.rectangle(vis, (b[0], b[1]), (b[2], b[3]), color, 2)
        active_s = sum(1 for s in registry.slots.values() if s["active"])
        inactive_s = sum(1 for s in registry.slots.values() if not s["active"] and not s["expired"])
        cv2.rectangle(vis, (10, 10), (520, 165), (0, 0, 0), -1)
        cv2.rectangle(vis, (10, 10), (520, 165), (0, 255, 100), 2)
        cv2.putText(vis, f"On Platform Now : {smooth_now}", (20, 55), cv2.FONT_HERSHEY_SIMPLEX, 1.0, (200, 200, 200), 2)
        cv2.putText(vis, f"TOTAL EVER      : {total_count}", (20, 110), cv2.FONT_HERSHEY_SIMPLEX, 1.2, (0, 255, 100), 3)
        cv2.putText(vis, f"slots active={active_s} mem={inactive_s} tracks={len(ice_detections)}", (20, 148), cv2.FONT_HERSHEY_SIMPLEX, 0.55, (150, 150, 150), 1)
        cv2.putText(vis, f"t={t_sec:.1f}s", (10, h - 15), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (180, 180, 180), 1)
        vw.write(vis)
        if frame_idx % max(1, int(fps)) == 0:
            L(f"t={t_sec:6.1f}s | on:{smooth_now:2d} | TOTAL:{total_count:3d} | active:{active_s:2d} mem:{inactive_s:2d} | tracks:{len(ice_detections):2d}")
        frame_idx += 1

    cap.release()
    vw.release()
    pd.DataFrame(frame_log).to_csv(output_csv, index=False)
    active_end = sum(1 for s in registry.slots.values() if s["active"])
    L("")
    L("=" * 65)
    L(f"  TOTAL UNIQUE BLOCKS ON PLATFORM : {registry.total_count}")
    L(f"  Still on platform at end           : {active_end}")
    L(f"  Left platform                      : {registry.total_count - active_end}")
    L("=" * 65)
    L(f"  Log   → {output_csv}")
    L(f"  Video → {output_video}")

    return {
        "error": None,
        "logs": logs,
        "total_unique_blocks": registry.total_count,
        "still_on_platform_end": active_end,
        "left_platform": registry.total_count - active_end,
        "output_csv": output_csv,
        "output_video": output_video,
        "video_width": w,
        "video_height": h,
        "fps": round(fps, 2),
        "frames_processed": frame_idx - start_frame,
        "frames_total": total_to_process,
        "max_frames_limit": max_frames,
    }


if __name__ == "__main__":
    import json
    if len(sys.argv) < 3:
        print(json.dumps({"error": "Usage: model_runner.py <video_path> <model_path>"}))
        sys.exit(1)
    print(json.dumps(run_solution_style(sys.argv[1], sys.argv[2]), default=str))
