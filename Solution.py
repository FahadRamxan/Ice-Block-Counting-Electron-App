import cv2
import numpy as np
import pandas as pd
from ultralytics import YOLO
from collections import deque

# ─────────────────────────────────────────────────────────────
# CONFIG
# Override with env VIDEO_PATH and MODEL_PATH to run with any path without editing.
# ─────────────────────────────────────────────────────────────
import os as _os
VIDEO_PATH       = _os.environ.get("VIDEO_PATH") or "/20251226114733851.MP4"
MODEL_PATH       = _os.environ.get("MODEL_PATH") or "/best_9_3_2026.pt"
OUTPUT_VIDEO     = "ice_block_total_count.avi"
OUTPUT_CSV       = "ice_block_events.csv"

ICE_BLOCK_CLASS_ID = 0
PLATFORM_CLASS_ID  = 1

START_SECOND = 0
END_SECOND   = None

ON_PLATFORM_THRESHOLD  = 0.35
LEAVING_CONFIRM_FRAMES = 15
MIN_CONFIRM_FRAMES     = 3
CONF_THRESHOLD         = 0.75

# Two different distance thresholds:
DUPLICATE_DISTANCE_PX = 80   # new tid within this of an ACTIVE slot = duplicate detection
REID_DISTANCE_PX      = 120  # new tid within this of an INACTIVE slot = re-ID after occlusion

SLOT_MEMORY_FRAMES = 500
SMOOTH_WINDOW      = 15


# ─────────────────────────────────────────────────────────────
# HELPERS
# ─────────────────────────────────────────────────────────────

def overlap_ratio(boxA, boxB):
    xA = max(boxA[0], boxB[0]);  yA = max(boxA[1], boxB[1])
    xB = min(boxA[2], boxB[2]);  yB = min(boxA[3], boxB[3])
    inter = max(0, xB - xA) * max(0, yB - yA)
    aA = (boxA[2]-boxA[0]) * (boxA[3]-boxA[1])
    return inter / aA if aA > 0 else 0.0

def centroid(box):
    return ((box[0]+box[2])/2, (box[1]+box[3])/2)

def dist(c1, c2):
    return ((c1[0]-c2[0])**2 + (c1[1]-c2[1])**2) ** 0.5

def box_area(b):
    return (b[2]-b[0]) * (b[3]-b[1])

def mode_count(d):
    from collections import Counter
    return Counter(d).most_common(1)[0][0] if d else 0


# ─────────────────────────────────────────────────────────────
# SLOT REGISTRY
#
# Three cases for a new (unseen) tid:
#   1. Within DUPLICATE_DISTANCE_PX of ACTIVE slot
#      → duplicate detection of same block → absorb, no count++
#   2. Within REID_DISTANCE_PX of INACTIVE slot
#      → block reappeared after occlusion → reclaim slot, no count++
#   3. Neither → genuinely new block → new slot, count++
# ─────────────────────────────────────────────────────────────

class SlotRegistry:
    def __init__(self):
        self.slots       = {}
        self.tid_to_slot = {}
        self.total_count = 0
        self._next_slot  = 1
        self._logged     = set()

    def update(self, confirmed_detections, frame_idx):
        seen_tids = set()

        for tid, box in confirmed_detections:
            c = centroid(box)
            seen_tids.add(tid)

            if tid in self.tid_to_slot:
                # ── Known tid: update position ─────────────────
                sid = self.tid_to_slot[tid]
                s   = self.slots[sid]
                s["centroid"]    = c
                s["active"]      = True
                s["frames_gone"] = 0
                s["expired"]     = False

            else:
                # ── New tid — find nearest active and inactive slots ──
                near_active_sid,   near_active_dist   = None, float("inf")
                near_inactive_sid, near_inactive_dist = None, float("inf")

                for sid, slot in self.slots.items():
                    if slot["expired"]:
                        continue
                    d = dist(c, slot["centroid"])
                    if slot["active"]:
                        if d < near_active_dist:
                            near_active_dist = d
                            near_active_sid  = sid
                    else:
                        if d < near_inactive_dist:
                            near_inactive_dist = d
                            near_inactive_sid  = sid

                if near_active_sid is not None and near_active_dist < DUPLICATE_DISTANCE_PX:
                    # Case 1: Duplicate detection of an already-tracked block
                    self.tid_to_slot[tid] = near_active_sid
                    key = (tid, near_active_sid)
                    if key not in self._logged:
                        self._logged.add(key)
                        print(f"  ⊕ Dup: tid={tid} → slot={near_active_sid} "
                              f"dist={near_active_dist:.0f}px (same block)")

                elif near_inactive_sid is not None and near_inactive_dist < REID_DISTANCE_PX:
                    # Case 2: Re-ID — block reappeared after occlusion
                    old_tid = self.slots[near_inactive_sid]["tid"]
                    self.slots[near_inactive_sid]["tid"]         = tid
                    self.slots[near_inactive_sid]["centroid"]    = c
                    self.slots[near_inactive_sid]["active"]      = True
                    self.slots[near_inactive_sid]["frames_gone"] = 0
                    self.slots[near_inactive_sid]["expired"]     = False
                    self.tid_to_slot.pop(old_tid, None)
                    self.tid_to_slot[tid] = near_inactive_sid
                    key = (tid, near_inactive_sid)
                    if key not in self._logged:
                        self._logged.add(key)
                        print(f"  ↩ Re-ID: tid={tid} reclaimed slot={near_inactive_sid} "
                              f"dist={near_inactive_dist:.0f}px")

                else:
                    # Case 3: Genuinely new block
                    sid = self._next_slot
                    self._next_slot += 1
                    self.slots[sid] = {
                        "tid"        : tid,
                        "centroid"   : c,
                        "active"     : True,
                        "frames_gone": 0,
                        "expired"    : False,
                        "first_frame": frame_idx,
                    }
                    self.tid_to_slot[tid] = sid
                    self.total_count += 1
                    print(f"  ★ NEW block! slot={sid} tid={tid} "
                          f"centroid=({c[0]:.0f},{c[1]:.0f})  "
                          f"TOTAL={self.total_count}")

        # ── Age unseen slots ──────────────────────────────────
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


# ─────────────────────────────────────────────────────────────
# PER-TRACK CONFIRMATION
# ─────────────────────────────────────────────────────────────

class BlockTrack:
    def __init__(self):
        self.frames_on = 0
        self.confirmed = False
        self.last_box  = None

    def update(self, box, ratio):
        self.last_box = box
        if ratio >= ON_PLATFORM_THRESHOLD:
            self.frames_on += 1
        if self.frames_on >= MIN_CONFIRM_FRAMES:
            self.confirmed = True


# ─────────────────────────────────────────────────────────────
# MAIN
# ─────────────────────────────────────────────────────────────

cap = cv2.VideoCapture(VIDEO_PATH)
assert cap.isOpened(), "Error reading video file"

fps   = cap.get(cv2.CAP_PROP_FPS)
total = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
w     = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
h     = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))

start_frame = int(START_SECOND * fps)
end_frame   = int(END_SECOND * fps) if END_SECOND is not None else total
end_frame   = min(end_frame, total)

print(f"Video : {w}x{h} @ {fps:.1f}fps")
print(f"Range : {start_frame/fps:.1f}s → {end_frame/fps:.1f}s")
print(f"Dup   : merge into active slot within {DUPLICATE_DISTANCE_PX}px")
print(f"Re-ID : reclaim inactive slot within {REID_DISTANCE_PX}px")
print(f"Memory: {SLOT_MEMORY_FRAMES} frames ({SLOT_MEMORY_FRAMES/fps:.1f}s)")
print("=" * 65)

cap.set(cv2.CAP_PROP_POS_FRAMES, start_frame)
vw    = cv2.VideoWriter(OUTPUT_VIDEO, cv2.VideoWriter_fourcc(*"mp4v"), fps, (w, h))
model = YOLO(MODEL_PATH, task="segment")

block_tracks  = {}
registry      = SlotRegistry()
last_plat_box = None
count_history = deque(maxlen=SMOOTH_WINDOW)
frame_log     = []
frame_idx     = start_frame

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
            cls  = int(box.cls[0])
            conf = float(box.conf[0])
            b    = list(map(int, box.xyxy[0].tolist()))
            tid  = int(box.id[0]) if box.id is not None else None

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
                "track_id": tid, "overlap_ratio": round(ratio, 4),
                "conf": round(conf, 3),
            })

    total_count, current_on = registry.update(confirmed, frame_idx)
    count_history.append(current_on)
    smooth_now = mode_count(count_history)

    # ── Draw ─────────────────────────────────────────────────
    vis = im0.copy()
    if last_plat_box:
        cv2.rectangle(vis,
                      (last_plat_box[0], last_plat_box[1]),
                      (last_plat_box[2], last_plat_box[3]),
                      (0, 200, 255), 2)

    for sid, slot in registry.slots.items():
        if slot["expired"]: continue
        cx, cy = int(slot["centroid"][0]), int(slot["centroid"][1])
        if slot["active"]:
            cv2.circle(vis, (cx, cy), 16, (0,255,100), -1)
            cv2.putText(vis, f"S{sid}", (cx-14, cy+6),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.55, (0,0,0), 2)
        else:
            cv2.circle(vis, (cx, cy), 16, (100,100,255), 2)
            cv2.putText(vis, f"S{sid}", (cx-14, cy+6),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.45, (100,100,255), 1)

    for tid, (b, conf) in ice_detections.items():
        track = block_tracks.get(tid)
        ok    = track and track.confirmed
        ratio = overlap_ratio(b, last_plat_box) if last_plat_box else 0
        color = (0,255,0) if ok else (180,180,180)
        cv2.rectangle(vis, (b[0],b[1]), (b[2],b[3]), color, 2)
        cv2.putText(vis, f"ID:{tid} {ratio:.2f}",
                    (b[0], b[1]-6), cv2.FONT_HERSHEY_SIMPLEX, 0.45, color, 1)

    cv2.rectangle(vis, (10,10), (520,165), (0,0,0), -1)
    cv2.rectangle(vis, (10,10), (520,165), (0,255,100), 2)
    cv2.putText(vis, f"On Platform Now : {smooth_now}",
                (20,55), cv2.FONT_HERSHEY_SIMPLEX, 1.0, (200,200,200), 2)
    cv2.putText(vis, f"TOTAL EVER      : {total_count}",
                (20,110), cv2.FONT_HERSHEY_SIMPLEX, 1.2, (0,255,100), 3)
    active_s   = sum(1 for s in registry.slots.values() if s["active"])
    inactive_s = sum(1 for s in registry.slots.values()
                     if not s["active"] and not s["expired"])
    cv2.putText(vis,
                f"slots active={active_s} mem={inactive_s} tracks={len(ice_detections)}",
                (20,148), cv2.FONT_HERSHEY_SIMPLEX, 0.55, (150,150,150), 1)
    cv2.putText(vis, f"t={t_sec:.1f}s",
                (10, h-15), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (180,180,180), 1)

    vw.write(vis)

    if frame_idx % max(1, int(fps)) == 0:
        print(f"t={t_sec:6.1f}s | on:{smooth_now:2d} | "
              f"TOTAL:{total_count:3d} | "
              f"active:{active_s:2d} mem:{inactive_s:2d} | "
              f"tracks:{len(ice_detections):2d}")

    frame_idx += 1

cap.release()
vw.release()
pd.DataFrame(frame_log).to_csv(OUTPUT_CSV, index=False)

active_end = sum(1 for s in registry.slots.values() if s["active"])
print("\n" + "=" * 65)
print(f"  ✅ TOTAL UNIQUE BLOCKS ON PLATFORM : {registry.total_count}")
print(f"  Still on platform at end           : {active_end}")
print(f"  Left platform                      : {registry.total_count - active_end}")
print("=" * 65)
print(f"\n  Log   → {OUTPUT_CSV}")
print(f"  Video → {OUTPUT_VIDEO}")