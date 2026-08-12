import time
import math
SCRIPT_START_TIME = time.time()

import warnings
warnings.filterwarnings("ignore")
import logging
logging.getLogger("ultralytics").setLevel(logging.ERROR)

import sys
import cv2
import numpy as np
import pandas as pd
import torch
import threading
import queue
import os
from ultralytics import YOLO
from ultralytics.trackers.byte_tracker import BYTETracker
from ultralytics.trackers.bot_sort import BOTSORT
from ultralytics.utils import IterableSimpleNamespace, YAML
from ultralytics.utils.checks import check_yaml
from collections import deque

try:
    from ultralytics.trackers.fast_tracker import FASTTracker
except ImportError as e:
    raise ImportError(
        "Could not import FASTTracker — run: pip install -U ultralytics"
    ) from e

TRACKER_MAP = {"bytetrack": BYTETracker, "botsort": BOTSORT, "fasttrack": FASTTracker}

                                                     
                                                            
                                                                    
                                                                         
                                                                         
                           
VIDEO_PATH   = sys.argv[1] if len(sys.argv) > 1 else "20260312103845210.mp4"
MODEL_PATH_PT = "best (1).pt"
_video_stem  = os.path.splitext(os.path.basename(VIDEO_PATH))[0]
OUTPUT_VIDEO = f"ice_block_total_count_batched_fasttrack_{_video_stem}.avi"
OUTPUT_CSV   = f"ice_block_events_batched_fasttrack_{_video_stem}.csv"
OUTPUT_LOG   = f"ice_block_console_log_batched_fasttrack_{_video_stem}.txt"


class _Tee:
    """Mirrors everything written to it out to multiple streams (e.g. the
    real console plus a log file), so all the existing print() calls end up
    saved to disk with no changes needed anywhere else in the script."""
    def __init__(self, *streams):
        self.streams = streams

    def write(self, data):
        for s in self.streams:
            s.write(data)
            s.flush()

    def flush(self):
        for s in self.streams:
            s.flush()


_log_file = open(OUTPUT_LOG, "a", buffering=1, encoding="utf-8", errors="replace")
# Windows' console defaults to the cp1252 codepage, which cannot encode
# characters like the narrow no-break space (\u202f) that Windows itself
# inserts into AM/PM timestamps in filenames (e.g. "...102937 PM.mp4").
# Reconfigure stdout/stderr to UTF-8 with errors="replace" BEFORE wrapping
# them in _Tee, so any such character is substituted instead of crashing
# the whole run mid-print.
sys.stdout.reconfigure(encoding="utf-8", errors="replace")
sys.stderr.reconfigure(encoding="utf-8", errors="replace")
sys.stdout = _Tee(sys.stdout, _log_file)
sys.stderr = _Tee(sys.stderr, _log_file)
print(f"\n===== NEW RUN: {time.strftime('%Y-%m-%d %H:%M:%S')} | video={VIDEO_PATH} =====")

ICE_BLOCK_CLASS_ID = 0
PLATFORM_CLASS_ID  = 1

PERSON_MODEL_PATH = "yolo11n.pt"
PERSON_CONF_THRESHOLD = 0.4
PERSON_OCCLUSION_MARGIN_PX = 20

TRACKER_YAML = "fasttrack.yaml"

START_SECOND = 0
END_SECOND   = None

CONF_THRESHOLD         = 0.75

ENTRY_SIDE = None

ENTRY_SIDE_VOTES_NEEDED = 1
ENTRY_SIDE_TIMEOUT_SECONDS = 60
ENTRY_SIDE_FALLBACK = "bottom"
ENTRY_CORRIDOR_DEPTH_PX = 150
VISIBLE_MATCH_DIST_PX = 80
OCCLUDED_MATCH_DIST_PX = 400
WORKER_BIND_MARGIN_PX = 120
OCCLUSION_MARGIN_PX = 30
MIN_DRAG_DISPLACEMENT_PX = 40
EXIT_MARGIN_PX = -30
DIRECT_EXIT_MARGIN_PX = 10
DEPARTURE_DEDUP_WINDOW_SECONDS = 12.5
DEPARTURE_DEDUP_DIST_PX = 250
MIN_SETTLING_SECONDS = 5.0
EXIT_GRACE_SECONDS = 1.0
NO_REAPPEAR_GRACE_SECONDS = 1.0
MAX_BOUND_OCCLUSION_SECONDS = 120
MIN_RATIO_EVER_FOR_REAL_BLOCK = 0.35
MIN_HIGH_RATIO_FRAMES = 5
STATIONARY_REID_DIST_PX = 100
PENDING_LOAD_CONFIRM_FRAMES = 45
ROLLBACK_WINDOW_FRAMES = 90
# [Fix -- stale orphaned sibling never reconciled] _check_prior_split's
# candidate search used to reuse ROLLBACK_WINDOW_FRAMES (90f / ~3.6s) --
# a window sized for its OTHER, unrelated purpose (undoing a false-
# positive commit that reappears moments later), not for this one
# (finding a sibling fragment slot that split off from the SAME
# physical block potentially much earlier in a long carry -- e.g. a
# worker slowly climbing a staircase with the block occluded/re-
# fragmented repeatedly over many seconds). A sibling created more than
# 3.6s before the final commit was silently excluded from candidacy
# entirely (see the frame_idx - first_created_frame <= window check),
# guaranteeing it could never be merged back and would sit as a
# permanently stranded slot -- a green circle that never clears even
# after its actual physical block has already departed under a
# different, later id. _check_prior_split now reuses the existing
# self.max_bound_occlusion_frames (fps-scaled at construction, see
# MAX_BOUND_OCCLUSION_FRAMES below) instead of rollback_window_frames --
# the same ceiling already trusted elsewhere in this class for "how
# long may a slot plausibly stay explained by ongoing occlusion" is the
# physically correct scale for this search too, rather than inventing a
# third, separate timing constant.
RECENT_MERGE_WINDOW_FRAMES = 30
RECENT_MERGE_DIST_PX = 150
ROLLBACK_REAPPEAR_DIST_PX = 200
MIN_SUSTAINED_CONTACT_FRAMES = 8
# [Fix -- terminal decision for provisional identities] Consecutive
# times the identity resolver has actually evaluated a real detection
# against a still-provisional slot -- via its own elimination and
# continuity-validation logic in _resolve_via_candidates, not a
# separate lookup -- and rejected it. Reset to 0 the moment that same
# slot IS claimed. A frame with no detection to test at all (occlusion,
# a missed detector frame, genuine absence) produces no evidence either
# way and leaves this untouched. NOT an elapsed-age/timeout/movement/
# ratio/contact/occlusion/seen_slots heuristic -- driven only by
# repeated, genuine resolver rejection of this exact identity.
RESOLVER_EXHAUSTED_FRAMES = 5

                                                                      
                                                                         
                                                                      
                                                                          
                                                                      
                                                                   
                                                                    
                                                                  
                                                                        
                                                                     
                                                                         
                                                    
DETECTION_CONF_FLOOR = 0.1

                                                                    
                                                                          
                                                                       
                                                                         
                                                                       
                                                                         
                                                                        
                                                                      
                                                       
DUPLICATE_DISTANCE_PX = 80                                                    
                                                                           
                                                                           
                                                                        
                                                                              
DUPLICATE_GAP_PX = 120
                                                                         
                                                                         
                                                                  
REID_DISTANCE_PX      = 150
                                                                          
                                                                        
                                                                    
                                                                           
                                                                      
                                                                
                                                               

SLOT_MEMORY_MINUTES = 2                                                     
                                                                             
                                                                            
                                                                       
                                                                           
                                                                    

                                                                         
                                                                        
                                                                           
                                                                          
                                                                    
                                                                     
                                                                        
                                                                  
                                                                          
                                                                         
                                                                      
                                                                           
                                                                         
PRESUMED_DEPARTED_SECONDS = 45
SMOOTH_WINDOW = 15

                                                                         
                                                                        
                                                                 
                                                                   
                                                                       
                                                                         
                                                                        
                                                                   
                                                                    
                                                                      
MIN_DEPART_SPEED_PX_PER_FRAME = 3.0

                                                                    
                                                                         
                                                                         
                                                                   
                                                                 
                                                                      
                                                                        
                                                                     
                                                                     
                                                                       
                                                                         
                                                                            
MIN_NET_DISPLACEMENT_PX = 15
POS_HISTORY_LEN = 6

                                                                     
                                                                          
                                                                         
                                                                        
                                                                   
                                                                   
                                                                         
                                                                         
                                                                         
                                                             
LOW_RATIO_DEPART_THRESHOLD = 0.15

                                                                     
                                                                          
                                                                         
                                                                       
                                                                      
                                                                       
                                                                          
                                                                       
                                                                     
                                                                  
                             

                                                                        
                                                                      
                                                                     
                                                           

INPUT_W, INPUT_H = 1280, 720
INFER_SIZE       = 640
USE_HALF         = True
PROCESS_EVERY_N  = 2
OUT_W, OUT_H     = 1280, 720

BATCH_SIZE = 8

print("=" * 60)
print(f"CUDA available     : {torch.cuda.is_available()}")
if torch.cuda.is_available():
    print(f"GPU name           : {torch.cuda.get_device_name(0)}")
DEVICE = "cuda:0" if torch.cuda.is_available() else "cpu"
print(f"Using device       : {DEVICE}")
print(f"BATCH_SIZE         : {BATCH_SIZE}")
if DEVICE != "cpu":
    torch.backends.cudnn.benchmark = True
print("=" * 60)


# ======================================================================
# Geometry Utilities
# ======================================================================
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

def union_box(boxA, boxB):
    return (min(boxA[0], boxB[0]), min(boxA[1], boxB[1]),
            max(boxA[2], boxB[2]), max(boxA[3], boxB[3]))

def union_boxes(boxes):
    result = boxes[0]
    for b in boxes[1:]:
        result = union_box(result, b)
    return result

def boxes_close(boxA, boxB, gap_px=40):
    ax1, ay1, ax2, ay2 = boxA
    bx1, by1, bx2, by2 = boxB
    gap_x = max(bx1 - ax2, ax1 - bx2, 0)
    gap_y = max(by1 - ay2, ay1 - by2, 0)
    return gap_x <= gap_px and gap_y <= gap_px

def box_distance(boxA, boxB):
    ax1, ay1, ax2, ay2 = boxA
    bx1, by1, bx2, by2 = boxB
    gap_x = max(bx1 - ax2, ax1 - bx2, 0)
    gap_y = max(by1 - ay2, ay1 - by2, 0)
    return (gap_x ** 2 + gap_y ** 2) ** 0.5

def nearest_edge_side(pos, plat_box):
    if plat_box is None:
        return None
    px, py = pos
    x1, y1, x2, y2 = plat_box
    distances = {
        "left":   px - x1,
        "right":  x2 - px,
        "top":    py - y1,
        "bottom": y2 - py,
    }
    return min(distances, key=distances.get)

def mode_count(d):
    from collections import Counter
    return Counter(d).most_common(1)[0][0] if d else 0

def format_duration(seconds):
    h = int(seconds // 3600)
    m = int((seconds % 3600) // 60)
    s = seconds % 60
    if h > 0:
        return f"{h}h {m}m {s:.1f}s"
    elif m > 0:
        return f"{m}m {s:.1f}s"
    return f"{s:.2f}s"


# ======================================================================
# Motion Prediction Utilities (currently unused elsewhere in the
# pipeline -- kept as-is, not wired into EventBasedRegistry)
# ======================================================================
class KalmanCentroid:
                                                                         
                                                              
    def __init__(self, cx, cy, frame_idx):
        self.kf = cv2.KalmanFilter(4, 2)
        self.kf.measurementMatrix = np.array([[1, 0, 0, 0], [0, 1, 0, 0]], dtype=np.float32)
        self.kf.processNoiseCov = np.diag([1e-2, 1e-2, 5.0, 5.0]).astype(np.float32)
        self.kf.measurementNoiseCov = np.eye(2, dtype=np.float32) * 1.0
        self.kf.statePost = np.array([[cx], [cy], [0], [0]], dtype=np.float32)
        self.last_frame = frame_idx

    def _set_dt(self, dt):
        self.kf.transitionMatrix = np.array([
            [1, 0, dt, 0], [0, 1, 0, dt], [0, 0, 1, 0], [0, 0, 0, 1]], dtype=np.float32)

    def predict(self, frame_idx):
        dt = max(frame_idx - self.last_frame, 0)
        x, y, vx, vy = self.kf.statePost.ravel()
        return float(x + vx * dt), float(y + vy * dt)

    def velocity(self):
        _, _, vx, vy = self.kf.statePost.ravel()
        return float(vx), float(vy)

    def correct(self, cx, cy, frame_idx):
        dt = max(frame_idx - self.last_frame, 1)
        self._set_dt(dt)
        self.kf.predict()
        self.kf.correct(np.array([[np.float32(cx)], [np.float32(cy)]]))
        self.last_frame = frame_idx


class EventBasedRegistry:

    # ==================================================================
    # Registry Orchestrator -- Construction & Shared State
    # All tunable thresholds and mutable state live here. Every other
    # section below is a focused helper that this state is threaded
    # through; nothing here makes decisions on its own.
    # ==================================================================

    def __init__(self, entry_side, platform_box,
                 entry_corridor_depth_px=150,
                 visible_match_dist_px=80,
                 occluded_match_dist_px=200,
                 worker_bind_margin_px=30,
                 occlusion_margin_px=30,
                 min_drag_displacement_px=40,
                 exit_grace_frames=30,
                 no_reappear_grace_frames=30,
                 min_ratio_ever_for_real_block=0.35,
                 min_sustained_contact_frames=8,
                 entry_side_votes_needed=3,
                 entry_side_timeout_frames=None,
                 entry_side_fallback="bottom",
                 max_bound_occlusion_frames=1500,
                 exit_margin_px=-30,
                 direct_exit_margin_px=10,
                 departure_dedup_window_frames=300,
                 departure_dedup_dist_px=250,
                 min_settling_frames=100,
                 min_high_ratio_frames=5,
                 stationary_reid_dist_px=100,
                 pending_load_confirm_frames=45,
                 rollback_window_frames=90,
                 recent_merge_window_frames=30,
                 recent_merge_dist_px=150,
                 rollback_reappear_dist_px=200,
                 fps=25.0,
                 resolver_exhausted_frames=5,
                 oversized_freeze_max_frames=None):
        self.entry_side = entry_side
        self.platform_box = platform_box
        self.entry_corridor_depth_px = entry_corridor_depth_px
        self.visible_match_dist_px = visible_match_dist_px
        self.occluded_match_dist_px = occluded_match_dist_px
        self.worker_bind_margin_px = worker_bind_margin_px
        self.occlusion_margin_px = occlusion_margin_px
        self.min_drag_displacement_px = min_drag_displacement_px
        self.exit_grace_frames = exit_grace_frames
        self.no_reappear_grace_frames = no_reappear_grace_frames
        self.min_ratio_ever_for_real_block = min_ratio_ever_for_real_block
        self.min_sustained_contact_frames = min_sustained_contact_frames
        self.entry_side_votes_needed = entry_side_votes_needed
        self.entry_side_timeout_frames = entry_side_timeout_frames
        self.entry_side_fallback = entry_side_fallback
        self.max_bound_occlusion_frames = max_bound_occlusion_frames
        self.exit_margin_px = exit_margin_px
        self.direct_exit_margin_px = direct_exit_margin_px
        self.departure_dedup_window_frames = departure_dedup_window_frames
        self.departure_dedup_dist_px = departure_dedup_dist_px
        self.min_settling_frames = min_settling_frames
        self.min_high_ratio_frames = min_high_ratio_frames
        self.stationary_reid_dist_px = stationary_reid_dist_px
        self.pending_load_confirm_frames = pending_load_confirm_frames
        self.rollback_window_frames = rollback_window_frames
        self.recent_merge_window_frames = recent_merge_window_frames
        self.recent_merge_dist_px = recent_merge_dist_px
        self.rollback_reappear_dist_px = rollback_reappear_dist_px
        # [Fix -- terminal decision for provisional identities] Number of
        # CONSECUTIVE times the identity resolver must actually evaluate
        # a real detection against a provisional slot -- via its own
        # elimination/continuity-validation logic in
        # _resolve_via_candidates -- and reject it, before that slot is
        # PERMANENTLY decided. Tracked on the slot's own persistent
        # self.slots entry using the resolver's own verdict
        # (rejected_sids); a frame with no detection to test at all
        # (occlusion, a missed detector frame, etc.) produces no
        # evidence and does not move this count. This is deliberately
        # small and is not an age/timeout/movement/ratio/contact/
        # occlusion/seen_slots heuristic.
        self.resolver_exhausted_frames = resolver_exhausted_frames
        # fps is needed to convert a hidden candidate's elapsed frame gap
        # into real elapsed seconds -- the unit the reconnect-candidate
        # system's reachability/time-decay scoring is expressed in, so
        # that its constants stay camera-invariant instead of being
        # tuned in raw frame counts for one particular capture rate.
        self.fps = fps if fps and fps > 0 else 25.0
        # [Fix -- indefinite geometry freeze under sustained oversized/
        # fused detections] See _update_matched_slot_geometry's own
        # oversized_likely_fused branch for the full mechanism this
        # closes (20260310225553131, slot=7): that branch has no expiry
        # by design (protecting against a single fused frame should
        # never require "waiting it out"), but a detector that stays
        # fused for many CONSECUTIVE seconds -- a worker genuinely
        # handling a block for a while -- leaves the slot's stored
        # geometry frozen at wherever it was before the fusing started,
        # while the real, still-fully-visible block keeps moving. By
        # the time the detection separates back to a believable single-
        # block size, it can have drifted far enough that it no longer
        # matches its OWN frozen reference (Fast Association and even
        # ordinary reconnect both reject it as SIZE_MISMATCH), so the
        # still-continuously-tracked block gets kicked out to a brand
        # new UnknownObservation and its real slot is orphaned. Default
        # of 2.0s (fps-scaled, camera-invariant like every other timing
        # constant here) chosen to comfortably outlast an ordinary
        # single fused frame or two while still being far short of a
        # multi-second occlusion.
        self.oversized_freeze_max_frames = (
            oversized_freeze_max_frames if oversized_freeze_max_frames is not None
            else max(1, round(2.0 * self.fps))
        )
        # Running estimate of "what does one block look like in pixels
        # right now, on this camera" -- an exponential moving average
        # over every confidently-matched detection's box, seeded by the
        # first real observation. This is what lets the reconnect
        # candidate system reason in block-relative units (e.g. "half a
        # block-width of drift") instead of fixed pixel constants that
        # only happen to suit one camera's distance/zoom.
        self._block_size_ema = None
        self._entry_votes = []
        self._recent_departures = []
        self._recent_worker_loads = []

        self.slots = {}
        self.workers = {}
        self._next_slot_id = 1
        self._next_worker_id = 1
        self.loaded_count = 0
        self.entered_count = 0

        # [Architecture -- observation buffer, NOT an identity stage]
        # Deliberately a separate dict, never merged into self.slots.
        # An UnknownObservation never receives a slot id, never
        # participates in reconnect as a candidate, never appears in
        # any slot-registry pass (draw layer, lifecycle, exit
        # subsystem, counting), and carries no counting state at all --
        # see the Observation Buffer section below for the full
        # reasoning and the single place (_create_slot_from_observation)
        # that is allowed to turn one into a real slot.
        self._unknown_observations = {}
        self._next_observation_id = 1

    # ==================================================================
    # Departure / Exit Reasoning -- Dedup & Boundary Helpers
    # ==================================================================

    def _prune_recent_departures(self, frame_idx):
        self._recent_departures = [
            (f, p) for f, p in self._recent_departures
            if frame_idx - f <= self.departure_dedup_window_frames
        ]
        aged_out = [
            entry for entry in self._recent_worker_loads
            if frame_idx - entry["frame"] > self.rollback_window_frames
        ]
        self._recent_worker_loads = [
            entry for entry in self._recent_worker_loads
            if frame_idx - entry["frame"] <= self.rollback_window_frames
        ]
        # [Fix] Confirmed bug: a slot left in "departed" state (see
        # _try_rollback_match's outside-platform branch) never
        # transitioned back to "gone" once its ledger entry aged out of
        # this same pruning pass -- its frozen last-known position stayed
        # eligible for the stable_id display lookup indefinitely,
        # mislabeling any later, unrelated block that happened to drift
        # within visible_match_dist_px of that stale point with the old,
        # already-counted identity. The instant this entry ages out, the
        # slot's brief continuity-tracking privilege is over -- from here
        # it should behave exactly like any other retired slot.
        for entry in aged_out:
            s = self.slots.get(entry["sid"])
            if s is not None and s["state"] == "departed":
                s["state"] = "gone"

    def _is_recent_departure(self, pos):
        for f, p in self._recent_departures:
            if dist(pos, p) <= self.departure_dedup_dist_px:
                return True
        return False

    def _past_exit_boundary(self, pos, margin=None):
        x, y = pos
        x1, y1, x2, y2 = self.platform_box
        if margin is None:
            margin = self.exit_margin_px
        return x < x1 - margin or x > x2 + margin or y < y1 - margin or y > y2 + margin

    # ==================================================================
    # Semantic Identity Resolution
    # Given a single detection that did NOT match an already-visible
    # slot on simple proximity (see Fast Association below), this
    # section resolves it to an existing hidden slot identity instead
    # of minting a new one -- via a candidate-based scorer (every
    # physically-possible hidden slot evaluated on the same footing,
    # see the constants and scoring methods below) rather than a
    # sequential rule chain. Rollback:Tight remains separate: it's not
    # about which slot a detection belongs to, it's about reversing an
    # already-COUNTED slot that was a false-positive departure. See
    # _resolve_detection_identity() at the bottom of this section for
    # how the pieces are sequenced.
    # ==================================================================

    def _try_rollback_match(self, pos, box, frame_idx, verbose=False):
        """Rollback safety net: a worker-based load may already have been
        committed and counted, but if a block then genuinely reappears
        near where it was last seen within a short window, the earlier
        departure determination was a false positive. Undo the count --
        but do NOT resurrect the old slot id. The old identity stays
        permanently retired; this detection gets a brand-new slot
        instead (see the accept branch below for why: proximity+timing
        alone don't prove it's the SAME physical block, only that
        something showed up nearby, and reusing the id let a genuinely
        different block silently inherit a stale identity's whole
        history). Anchored to the block's OWN last-known position/box
        (frozen at the moment it stopped being tracked), not the
        worker's box — a delayed commit means the worker may have moved
        on to something else entirely by the time this fires, so the
        worker's current or recorded position is not a reliable
        indicator of where the block itself will reappear. The worker ID
        is checked only as a secondary signal -- specifically, as a
        contradiction check: if a different, currently-live worker is
        demonstrably delivering this detection with no handoff evidence
        from the original worker, that's treated as proof this is a
        different block, not the one that departed (see the
        DIFFERENT_WORKER_NO_HANDOFF check below)."""
        if verbose and self._recent_worker_loads:
            print(f"    [rollback-check] frame={frame_idx} detection at "
                  f"({pos[0]:.0f},{pos[1]:.0f}) box={tuple(round(v) for v in box)} against "
                  f"{len(self._recent_worker_loads)} recent worker-load(s) in ledger")

        for entry in self._recent_worker_loads:
            age = frame_idx - entry["frame"]
            bbox = entry.get("block_box")
            bpos = entry.get("block_pos", pos)
            d = dist(pos, bpos)
            gap_x = max(bbox[0] - box[2], box[0] - bbox[2], 0) if bbox else 0
            gap_y = max(bbox[1] - box[3], box[1] - bbox[3], 0) if bbox else 0

            if age > self.rollback_window_frames:
                if verbose:
                    print(f"      - slot={entry['sid']} REJECTED: TOO_OLD "
                          f"(age={age}f > window={self.rollback_window_frames}f, "
                          f"loaded_at_frame={entry['frame']})")
                continue

            # [Fix] Confirmed bug: this method previously had zero
            # awareness of the entry corridor at all, unlike the scored
            # candidate system (which at least DAMPS a candidate's score
            # when the new detection sits in the entry corridor -- see
            # ENTRY_CORRIDOR_RECONNECT_DAMPING). At a busy loading/exit
            # choke point, a brand-new, physically DIFFERENT block can
            # arrive at the entry within the same rollback_window_frames
            # and within rollback_reappear_dist_px of where the previous
            # block was last recorded (e.g. both routed through the same
            # staging spot) -- proximity and timing alone satisfy this
            # check by construction, and the new arrival's own ID gets
            # silently discarded in favor of reusing the stale departed
            # slot's identity. A genuine reappearance of the SAME block
            # (the one this ledger entry is about) is, almost by
            # definition, not indistinguishable from a fresh arrival --
            # it was already on the platform, mid-departure, not walking
            # back in through the entry. So a detection inside the entry
            # corridor is never eligible for this tight, unscored
            # rollback match; it's treated as what it looks like -- a new
            # arrival -- and gets its own identity instead.
            if self._in_entry_corridor(pos):
                if verbose:
                    print(f"      - slot={entry['sid']} REJECTED: DETECTION_IN_ENTRY_CORRIDOR "
                          f"(age={age}f, pos=({pos[0]:.0f},{pos[1]:.0f}) looks like a fresh "
                          f"arrival, not the same block reappearing mid-departure)")
                continue

            near_block_pos = bbox is not None and boxes_close(box, bbox, self.rollback_reappear_dist_px)
            if not near_block_pos:
                if verbose:
                    print(f"      - slot={entry['sid']} REJECTED: TOO_FAR_FROM_BLOCK_LAST_POS "
                          f"(age={age}f, detection_center=({pos[0]:.0f},{pos[1]:.0f}), "
                          f"recorded_block_box={tuple(round(v) for v in bbox) if bbox else None}, "
                          f"centroid_dist={d:.0f}px, gap_x={gap_x:.0f}px, gap_y={gap_y:.0f}px, "
                          f"margin={self.rollback_reappear_dist_px}px)")
                continue

            snap_hit = self._matches_snapshot(box, pos, entry["snapshot_boxes"])
            if snap_hit:
                if verbose:
                    print(f"      - slot={entry['sid']} REJECTED: MATCHES_SNAPSHOT "
                          f"(age={age}f, this detection looks like one of the "
                          f"{len(entry['snapshot_boxes'])} pre-existing block(s) recorded at "
                          f"bind time, not the hidden block itself)")
                continue

            # [Fix] Confirmed bug: this method had zero awareness of WHO is
            # currently delivering this detection. At a genuine busy
            # loading/exit chokepoint (a fixed spot where every block gets
            # staged for pickup -- not the entry corridor, which the check
            # above already covers), proximity+timing+snapshot alone cannot
            # tell "the same block was picked back up" apart from "a
            # different worker just walked a brand-new block up to the same
            # staging spot" -- both look identical to every check above,
            # because the spot itself is reused by design. If a currently
            # LIVE worker is right on top of this detection, and that
            # worker is NOT the one recorded as having carried the
            # departing block (entry['worker_id']), that is direct evidence
            # a different person delivered a different block here -- unless
            # the original worker (if still live) was ever physically near
            # this new one, which would explain a genuine hand-off rather
            # than two independent deliveries. Mirrors the same
            # worker-ownership-contradiction reasoning already used in
            # _validate_reconnect_continuity, applied here to the one path
            # that never had it. Absence of a nearby live worker (the more
            # common case -- most reappearances aren't caught mid-handoff)
            # is not itself suspicious and does not block the rollback.
            current_wid = None
            for wid, w in self.workers.items():
                if w.get("expired"):
                    continue
                if boxes_close(box, w["box"], self.worker_bind_margin_px):
                    current_wid = wid
                    break
            orig_wid = entry.get("worker_id")
            age_sec = age / self.fps
            # Only trusted past WORKER_REPOSITION_MAX_GAP_SEC: a worker's
            # own tracked id can itself churn from a single missed/jittery
            # person-detection within a couple of raw frames (a new id
            # minted for the same physical person), which would otherwise
            # make this check misfire on exactly the near-instant, genuine
            # reappearances the rest of this method is designed to accept.
            # A real hand-off-to-a-different-worker-and-block takes
            # meaningfully longer than that to physically happen.
            if (current_wid is not None and orig_wid is not None and current_wid != orig_wid
                    and age_sec > self.WORKER_REPOSITION_MAX_GAP_SEC):
                orig_w = self.workers.get(orig_wid)
                handoff_evidence = (
                    orig_w is not None and not orig_w.get("expired")
                    and boxes_close(orig_w["box"], self.workers[current_wid]["box"],
                                     self.worker_bind_margin_px)
                )
                if not handoff_evidence:
                    if verbose:
                        print(f"      - slot={entry['sid']} REJECTED: DIFFERENT_WORKER_NO_HANDOFF "
                              f"(age={age}f/{age_sec:.1f}s, this detection is right at live "
                              f"worker={current_wid}, "
                              f"but the departing block was carried by worker={orig_wid}, and "
                              f"there's no evidence the two workers were ever near each other -- "
                              f"looks like a different worker delivering a different block to the "
                              f"same busy staging spot, not the original block being picked back up)")
                    continue

            sid = entry["sid"]
            s = self.slots.get(sid)
            if s is None:
                if verbose:
                    print(f"      - slot={sid} REJECTED: SLOT_NO_LONGER_EXISTS (age={age}f)")
                continue
            if not s["counted"]:
                if verbose:
                    print(f"      - slot={sid} REJECTED: SLOT_ALREADY_UNCOUNTED "
                          f"(age={age}f, state={s['state']}, counted={s['counted']} — "
                          f"already rolled back or otherwise reset)")
                continue

            # [Fix] Location-aware resolution: a detection that reappears
            # genuinely OUTSIDE the platform outline is, physically, the
            # SAME departed block still visible as it's carried off --
            # the departure call stands, there is nothing to roll back,
            # and forcing a brand-new id onto it would make the exported
            # log/track lose continuity on a block that never stopped
            # being the same object. Only a reappearance back INSIDE the
            # platform is genuinely ambiguous (false-positive departure
            # vs. a different block arriving at the same spot) -- that
            # case keeps the existing count-reversal + brand-new-id
            # behavior, so an exited id can never be handed to something
            # sitting back on the platform.
            outside_platform = self._past_exit_boundary(pos, margin=self.exit_margin_px)
            age_sec = age / self.fps

            if outside_platform and age_sec > self.OUTSIDE_TRACK_MAX_AGE_SEC:
                if verbose:
                    print(f"      - slot={sid} REJECTED: OUTSIDE_BUT_TOO_LONG_AGO "
                          f"(age={age}f/{age_sec:.1f}s > {self.OUTSIDE_TRACK_MAX_AGE_SEC}s -- "
                          f"too long for this to still be the same block visibly leaving frame; "
                          f"looks like a different block delivered to the same spot, e.g. the "
                          f"same worker returning with a new one through a shared doorway)")
                continue

            if outside_platform:
                if verbose:
                    print(f"      - slot={sid} ACCEPTED (outside platform): age={age}f "
                          f"dist_from_last_pos={d:.0f}px near_block_pos={near_block_pos} "
                          f"snapshot_hit={snap_hit} worker_id={entry.get('worker_id')} -> "
                          f"CONTINUING TO TRACK UNDER ORIGINAL IDENTITY, NO COUNT CHANGE")
                s["pos"] = pos
                s["box"] = box
                s["last_seen_frame"] = frame_idx
                # Distinct from "gone" -- still visible/trackable (e.g. in
                # the CSV's nearest-slot stable_id lookup) under its own
                # original id, but excluded from every active-on-platform
                # count and from every re-matching path (Fast Association,
                # candidate reconnect, this same rollback ledger) exactly
                # like any other counted slot, so it can never be
                # double-counted or its identity handed to something else.
                s["state"] = "departed"
                print(f"  [Rollback:OutsideTrack] slot={sid} reappeared {frame_idx - entry['frame']}f "
                      f"after departure, but at ({pos[0]:.0f},{pos[1]:.0f}) which is past the "
                      f"platform outline -- this is the same block still leaving, not a false "
                      f"positive. Count stands at TOTAL={self.loaded_count}, still tracked as "
                      f"slot={sid}.")
                return sid

            if verbose:
                print(f"      - slot={sid} ACCEPTED (inside platform): age={age}f "
                      f"dist_from_last_pos={d:.0f}px near_block_pos={near_block_pos} "
                      f"snapshot_hit={snap_hit} worker_id={entry.get('worker_id')} -> "
                      f"ROLLING BACK COUNT, NEW IDENTITY")

            self.loaded_count -= 1
            self._recent_worker_loads.remove(entry)

            # [Fix] Confirmed bug: this used to resurrect the OLD slot id
            # -- writing this detection's pos/box straight into it,
            # clearing counted/state, and handing it right back into
            # live tracking under the SAME identity. That conflates two
            # separate claims: (1) "this earlier LOADED commit was
            # premature" -- which the age/position/snapshot checks above
            # genuinely support -- and (2) "this new detection is
            # provably THAT SAME physical block" -- which they do NOT
            # support, only that something showed up nearby in time.
            # Busy staging/handoff spots (see the DragExit
            # positional-plausibility fix elsewhere in this class, same
            # underlying chokepoint failure mode) repeatedly proved
            # claim (2) unreliable: a genuinely different, newly-arriving
            # block passing through the same spot would silently inherit
            # the old slot's entire history (bound_worker cross-refs,
            # contact_frames, established_pos, snapshot_boxes) purely
            # from proximity + timing.
            #
            # Now: the old slot id is explicitly retired here -- counted,
            # gone -- permanently, never revived again. The count
            # correction (claim 1) still happens, since that part has
            # real evidence behind it. This detection instead mints a
            # brand-new slot, exactly like any other fresh arrival, so
            # no part of the old identity's history leaks into whatever
            # block is actually here now. The caller (update_blocks)
            # runs _update_matched_slot_geometry on the returned sid
            # immediately after this, which fills in pos/box/ratio/
            # high_ratio_frames for real -- the zeroed placeholders
            # below only need to be structurally valid.
            #
            # [Fix -- confirmed bug: assumed rather than enforced] This
            # used to just ASSUME the old slot was already "state=gone,
            # counted=True" from its original commit, and left
            # self.slots[sid] completely untouched -- the comment even
            # said so explicitly. That assumption doesn't always hold:
            # if anything else touched this slot between its original
            # commit and this rollback (the merge-back mechanism
            # reviving it out of "gone" state is one confirmed way this
            # can happen), state would silently be something other than
            # "gone" at this exact point, and this function would never
            # notice or correct it -- the slot then sits there,
            # rendered, forever, since nothing else was ever going to
            # touch it again either. Confirmed directly from user
            # screenshot: a slot this exact rollback path printed
            # "stays permanently retired" for was still drawn as an
            # active green circle deep into the video. Now sets state
            # and counted explicitly here instead of trusting they were
            # already right.
            if sid in self.slots:
                self.slots[sid]["state"] = "gone"
                self.slots[sid]["counted"] = True
            new_sid = self._next_slot_id
            self._next_slot_id += 1
            self.slots[new_sid] = {
                "pos": pos, "box": box, "last_seen_frame": frame_idx,
                "state": "visible", "max_ratio_ever": 0.0, "last_ratio": 0.0,
                "counted": False,
                # [Architecture -- worker evidence, not ownership]
                # occluded_by is a dict of {wid: last_overlap_frame} --
                # every worker currently (or recently) corroborating
                # this slot's disappearance. No exclusivity, no single
                # "owning" worker. last_worker_ids persists across
                # release (unlike occluded_by) purely for continuation/
                # logging -- see _release_worker_binding.
                "occluded_by": {},
                "bind_start_pos": None, "bind_start_frame": None,
                "drag_confirmed": False, "entry_meaningful": False,
                "frames_since_seen": 0, "contact_frames": 0,
                "last_worker_ids": set(),
                "created_frame": frame_idx,
                "first_created_frame": frame_idx,
                "high_ratio_frames": 0,
                "established_pos": pos,
                "velocity": (0.0, 0.0),
            }
            print(f"  [Rollback:Tight] ROLLBACK: old slot={sid} worker-load count reversed — a block "
                  f"genuinely reappeared {frame_idx - entry['frame']}f after that commit (within "
                  f"{self.rollback_window_frames}f rollback window), so the commit was a false "
                  f"positive -> TOTAL={self.loaded_count}. Reassigned to NEW slot={new_sid} instead "
                  f"of resurrecting slot={sid} -- proximity/timing alone don't prove it's the same "
                  f"physical block, so slot={sid} stays permanently retired.")
            return new_sid

        if verbose and self._recent_worker_loads:
            print(f"    [rollback-check] frame={frame_idx} no candidate accepted -> "
                  f"proceeding as a new/unrelated detection")
        return None

    # ------------------------------------------------------------------
    # Reconnect candidate system -- replaces the old sequential
    # Reveal -> RecentMerge -> Stationary rule chain. A sequential chain
    # means the FIRST rule that happens to pass wins, regardless of
    # whether a better-fitting candidate existed. That produced two
    # opposite failure modes across the validation batch: rules loose
    # enough to steal an unrelated slot (undercount) and rules strict
    # enough to reject a real reconnect and fragment one physical block
    # into several slots (overcount). This system instead asks "which
    # hidden slot -- if any -- is the most likely identity for this
    # detection?" once, across every slot simultaneously.
    #
    # Scoring is deliberately expressed in NORMALIZED, camera-invariant
    # units (elapsed seconds, block-widths, cosine similarity) rather
    # than fixed pixel constants tied to one camera's distance/zoom --
    # the batch spans videos shot at different scales, and fixed-pixel
    # tolerances were independently too loose for some and too strict
    # for others. Two constants below are the only absolute anchors
    # left, and both are physically-motivated ratios (not raw pixels):
    # a walking-with-a-load speed cap, and a confidence half-life for
    # how long a gap in detection is still trusted at face value.
    # ------------------------------------------------------------------

    # Bounded-exponential reachability model (fixes confirmed bug #1: the
    # old linear model produced 100,000+ px "reachable" radii for
    # long-hidden slots, at which point reachability stopped
    # discriminating anything). max_reach approaches, but never exceeds,
    # MAX_REACH_BLOCK_WIDTHS block-widths -- "could plausibly have moved
    # anywhere on the platform," not "moved an arbitrary distance."
    # REACHABILITY_SATURATION_TAU_SEC governs how fast it gets there:
    # within a few tau it's essentially at the cap, so extra hidden time
    # beyond that stops being able to manufacture extra reach.
    # Ceiling on how long ago a slot must have last been seen for
    # _reconnect_reachability_score's "recently carried" allowance
    # (below) to still apply. That allowance exists for one specific,
    # narrow physical event: a worker repositioning a block from one
    # side of their own body to the other INSTANTLY, in essentially a
    # single frame -- not for "the block reappeared somewhere near this
    # worker at some point in the last several seconds." Confirmed bug: the
    # original implementation applied the allowance unconditionally,
    # with no regard for how long the slot had actually been hidden,
    # so a worker who set the original block down and picked up a
    # completely different one within the same box span -- seconds
    # later -- got that different block silently reattached to the old
    # slot's identity purely because it was still touching the same
    # worker. Kept short and separate from TIME_HIDDEN_HALFLIFE_SEC
    # (that constant governs a continuous confidence decay used in
    # scoring; this one gates a binary allowance used in a
    # deterministic, unscored shortcut, so it needs its own much
    # tighter ceiling rather than sharing a number tuned for a
    # different purpose).
    WORKER_REPOSITION_MAX_GAP_SEC = 0.5
    # [Fix] Confirmed bug: the outside-platform rollback branch (see
    # _try_rollback_match's "CONTINUING TO TRACK UNDER ORIGINAL IDENTITY"
    # case) was reusing the full rollback_window_frames (~3.6s) as its
    # age tolerance -- the same window used for the genuinely different
    # "was this departure a false positive" question. But "the block is
    # still visibly leaving the frame" is a physically brief condition --
    # a couple of frames, not several seconds. Once entry and exit share
    # the same doorway (a common loading-dock layout), a worker who
    # drops off block A, walks back out, and returns with a brand-new
    # block B produces a reappearance at that exact same spot, with the
    # same worker, well within the old 3.6s window -- every signal this
    # branch checks says "same block", and it isn't. The entry-corridor
    # check is the only other thing guarding against this, and it only
    # covers a narrow band and depends on entry-side auto-detection
    # having gotten the right edge. This much tighter ceiling closes the
    # gap directly: past it, a reappearance outside the platform is no
    # longer assumed to be the same departing block, regardless of how
    # well position/worker/timing otherwise line up.
    OUTSIDE_TRACK_MAX_AGE_SEC = 1.0
    # Fixes confirmed bug #2 (zombie slots): a slot's own frozen, stale
    # box can coincidentally overlap some unrelated worker or block box
    # anywhere on a busy platform, and the lifecycle loop was treating
    # that as "still genuinely occluded," resetting its give-up clock to
    # zero indefinitely -- slots were observed surviving 200+ seconds
    # this way. Overlap is only trusted as REAL occlusion (i.e. allowed
    # to keep resetting the give-up clock) within this many seconds of
    # true elapsed time since the slot was last a genuine detection
    # match -- generous enough to cover any legitimate single
    # occlusion/carry, but finite. Anchored to last_seen_frame, which
    # coincidental overlap can never touch (only an actual re-match can).
    #
    # [Doc fix] This paragraph used to claim the constant was "reused
    # for a second purpose in Tier A of _generate_reconnect_candidates:
    # candidate ELIGIBILITY aging" -- describing a hidden-time cutoff
    # that doesn't exist in that method as actually implemented
    # (predates this file's current candidate-generation code; the
    # claim was already stale before this file's current
    # _generate_reconnect_candidates was written). It does NOT age
    # candidates out by ABSOLUTE_MAX_HIDDEN_SEC or any other
    # elapsed-time threshold -- a slot is eligible for as long as
    # _update_slot_lifecycle's own occlusion-credibility logic (which
    # DOES use this constant, see occlusion_still_credible below) keeps
    # it in "occluded" state at all.
    ABSOLUTE_MAX_HIDDEN_SEC = 60.0
    # [Architecture -- candidate ranking margin, NOT validated against
    # data] Used by _try_deterministic_reconnect to decide whether the
    # best-ranked candidate is "materially better" than the runner-up
    # (per the agreed architecture: "if one candidate is materially
    # better according to existing physical evidence, use it; otherwise
    # FIFO") or whether the two are close enough to count as a genuine
    # tie. Expressed as a MULTIPLE of _block_size_estimate() -- the same
    # existing, already-trusted camera-normalized unit the prediction-
    # region radius itself uses (radius = block_size * 1.5) -- rather
    # than a new absolute pixel constant, so it stays meaningful across
    # cameras at different distances/zoom the same way every other
    # ranking-relevant threshold in this class already does.
    #
    # The value 1.0 is a first-cut, NOT an empirically validated number:
    # the prediction gate itself already treats anything within 1.5x
    # block-width of the predicted position as "physically plausible,"
    # so two candidates separated by LESS than a full block-width are
    # closer to each other than the system's own noise floor for that
    # judgment -- a defensible starting point, not a measured one. This
    # is exactly the kind of constant that should be tuned against real
    # footage (does 1.0 actually separate genuine near-misses from
    # genuine ties on this camera setup?) before being trusted in
    # production; it is named and isolated here specifically so that
    # tuning is a one-line change, not a hunt through the ranking logic.
    RECONNECT_RANK_MATERIAL_MARGIN_BLOCK_WIDTHS = 1.0
    # [Architecture -- slot state estimates the block, not the last
    # detection] Governs _looks_like_whole_block, the test that decides
    # whether this frame's observation(s) should RESET the slot's
    # estimated extent (a fresh, trustworthy full view) or MERGE into
    # it (a partial fragment, extending what's already known -- see
    # _update_matched_slot_geometry). Deliberately NOT reused from
    # _box_size_similar's own 0.5 (50%) tolerance: that compares two
    # boxes' width and height ratios independently, which is the wrong
    # test here -- a left/right split typically halves WIDTH while
    # leaving height unchanged, so the average-dimension ratio for a
    # clean half-fragment undershoots how partial it actually is
    # (roughly 0.75x, not 0.5x), and a 50% average-dimension tolerance
    # would wrongly classify it as "whole." AREA scales far closer to
    # linearly with how much of the block is actually visible for a
    # directional split, so this compares box_area against
    # _block_size_estimate()**2 instead. First-cut, NOT validated
    # against real footage -- named and isolated here, same as
    # RECONNECT_RANK_MATERIAL_MARGIN_BLOCK_WIDTHS above, so tuning it
    # is a one-line change once real fragment geometry is available to
    # check it against.
    WHOLE_BLOCK_AREA_FRACTION = 0.8
    # [Architectural fix -- see MERGE(partial) capping in
    # _update_matched_slot_geometry] How large the running partial-
    # observation union estimate may grow, as a multiple of one block's
    # own expected area, before it's treated as too stale to keep
    # trusting and reset to the current frame's direct observation
    # instead. >1.0 on purpose -- a genuine two-sided split (block seen
    # partly on the left, partly on the right, worker's body in between)
    # legitimately produces a union somewhat larger than one clean
    # whole-block detection, and this must not fight WHOLE_BLOCK_AREA_
    # FRACTION's own reset trigger for that ordinary case. Same
    # first-cut caveat as every other named constant in this class: not
    # empirically validated, a one-line tune once real footage confirms
    # the right ceiling.
    MAX_PARTIAL_ESTIMATE_AREA_FRACTION = 1.6
    # [Fix -- see the elongation cap in _update_matched_slot_geometry]
    # Sibling to MAX_PARTIAL_ESTIMATE_AREA_FRACTION: bounds how far the
    # running union estimate may stretch in a SINGLE dimension (width
    # or height alone), as a multiple of the block's own expected
    # single-dimension size. The area cap alone doesn't catch a box that
    # stays small in area but very long and thin (or short and wide) --
    # exactly the shape that lets boxes_close's edge-gap test accept a
    # detection whose centroid is hundreds of pixels away. >1.0 for the
    # same reason as the area cap: a genuine two-sided split legitimately
    # produces a union somewhat longer than a single clean detection in
    # the split direction.
    MAX_PARTIAL_ESTIMATE_ELONGATION_FRACTION = 1.8

    # [Fix -- see the centroid ceiling in _match_visible_slot and
    # _match_recently_occluded_slot] boxes_close (edge-to-edge gap) has
    # no upper bound on centroid distance by itself -- a naturally tall
    # or wide box (real camera-perspective geometry, not drift) can
    # have an edge sitting only a few pixels from a totally unrelated
    # detection's edge even when the two centroids are hundreds of
    # pixels apart. This caps how far a detection's centroid may sit
    # from a slot's own centroid, as a multiple of the block's own
    # estimated size, before boxes_close is even consulted -- a genuine
    # offset fragment's centroid displacement from the whole block's
    # center is physically bounded by the block's own extent, so this
    # doesn't fight the legitimate case that test exists for. Floored
    # at visible_match_dist_px so a degenerate/unset block-size estimate
    # never produces a ceiling tighter than the ordinary tolerance.
    MAX_FRAGMENT_CENTROID_OFFSET_BLOCK_WIDTHS = 1.2

    # [Fix -- see the staleness-forced reset in
    # _update_matched_slot_geometry] How many CONSECUTIVE MERGE(partial)
    # frames a slot's geometry estimate may go without ever hitting a
    # genuine RESET before the historical base is discarded regardless
    # of size. The area/elongation caps only catch a union that grew
    # too big or too stretched -- they do nothing for a union that's
    # simply the wrong SHAPE for _looks_like_whole_block's own
    # calibration (e.g. block_size_estimate running a little high) while
    # staying under both caps indefinitely -- confirmed directly from
    # log evidence: a completely stable, correctly-detected block sat in
    # MERGE(partial) for 200+ straight frames, permanently ~60px offset
    # from its own real, current detection the entire time. Deliberately
    # small (a well-under-one-second stretch at ordinary frame rates) --
    # a real fragment situation should resolve toward RESET(whole) or
    # genuine occlusion well before this many frames if the estimate
    # were tracking correctly at all; anything staying MERGE(partial)
    # this long has already proven itself untrustworthy regardless of
    # why.
    MAX_PARTIAL_ESTIMATE_STALE_FRAMES = 15

    # [Fix -- see the tightened window in _check_prior_split's candidate
    # search] What fraction of max_bound_occlusion_frames the merge-back
    # search may look back across. Reusing the full value let a
    # departing slot be matched as "the prior split" of an essentially
    # unrelated slot from much earlier in the video, wrongly reviving it
    # with nothing left to ever re-correct it -- confirmed directly from
    # user report (a wrongly-revived slot sitting solid, visible, for
    # the rest of the video). Kept proportional to max_bound_occlusion_
    # frames rather than a flat frame count so it still scales correctly
    # across different videos and frame rates -- just scaled down enough
    # that it no longer spans most of a shorter video.
    PRIOR_SPLIT_SEARCH_FRAMES_FRACTION = 0.35
    # [Temporary -- validation diagnostics] Gates _log_reconnect_
    # diagnostics, a per-reconnect dump of the full candidate pool, its
    # raw evidence, and which decision path (single candidate /
    # DOMINANCE / FIFO) produced the result. Purely observational --
    # reading self.slots/passed only, never influencing any decision.
    # Flip to False (or delete the one call site in
    # _try_deterministic_reconnect) to silence it once validation
    # against real footage is done; nothing else in the reconnect path
    # depends on this flag.
    RECONNECT_DIAGNOSTICS_ENABLED = True
    # Worker continuity is ordinarily SOFT evidence (see
    # _validate_reconnect_continuity) -- a single mismatched worker
    # shouldn't veto an otherwise-good reconnect. But a relationship that
    # has accumulated substantially MORE than the ordinary
    # min_sustained_contact_frames bar represents a strong continuity
    # constraint, not routine noise -- and a completely different worker
    # abruptly claiming that slot, with no evidence the previous worker
    # was ever physically near the new one (i.e. no plausible handoff),
    # is a deterministic contradiction rather than one vote among three.
    # Expressed as a MULTIPLE of the already-existing
    # min_sustained_contact_frames bar rather than an independent new
    # absolute number, so "ordinary substantial" and "long-established"
    # stay two points on the same existing scale.
    # Deliberately much tighter than both visible_match_dist_px (ordinary
    # "same object" Fast Association threshold, measured centroid-to-
    # centroid) and worker_bind_margin_px (used for worker-adjacent
    # fragments, appropriately loose since a worker's own silhouette can
    # span a wide box). This one is measured EDGE-to-edge between two
    # fragments' own boxes, and exists for exactly one purpose: catching
    # a single stationary, un-worked block that the detector splits into
    # two touching/overlapping boxes within the same frame (segmentation
    # noise, a seam, a shadow) -- true fragments of one physical split
    # detection sit directly against or on top of each other. It must
    # NEVER be loose enough to merge two genuinely distinct blocks that
    # simply happen to be sitting near one another -- that regression is
    # exactly what _match_visible_slot's own seen_slots exclusion already
    # exists to prevent (see its docstring) -- so this stays a small,
    # near-zero gap rather than reusing either of those wider thresholds.
    SAME_FRAME_DUPLICATE_GAP_PX = 15

    # [Fix -- persistent duplicate misclassified as a fragment] Geometric
    # proximity alone (SAME_FRAME_DUPLICATE_GAP_PX) cannot tell apart
    # "one physical block the detector split into two touching boxes"
    # from "two genuinely separate blocks placed touching each other" --
    # both look geometrically identical within a single frame (gap can
    # be exactly 0 either way). The one signal that DOES distinguish
    # them is persistence: a real detector-split fragment is a per-frame
    # artifact (shadow, seam, segmentation noise) that doesn't
    # necessarily recur at a stable position frame after frame, while a
    # genuinely separate second block sitting there produces the exact
    # same recurring detection, at the exact same position, indefinitely.
    # Confirmed via direct log evidence (20260310225553131): a detection
    # at a fixed position kept getting accepted as slot=1's "fragment"
    # for 1600+ consecutive frames (65+ real seconds) before ever being
    # allowed its own identity -- a single stationary block sitting that
    # long is exactly what this mechanism is supposed to recognize, not
    # suppress. Capped at a genuinely small number of consecutive frames
    # -- true single-frame detector noise is resolved almost immediately;
    # anything still recurring this many frames later has already proven
    # itself to be a real, separate, persistent object.
    SAME_FRAME_DUPLICATE_MAX_RECURRING_FRAMES = 5
    # How close two recurring detections' centroids must be to count as
    # "the same recurring duplicate" rather than a fresh, unrelated one --
    # deliberately tight (tighter than SAME_FRAME_DUPLICATE_GAP_PX itself)
    # since a genuinely stationary second block should barely move at all
    # frame to frame.
    SAME_FRAME_DUPLICATE_RECURRING_POS_TOLERANCE_PX = 10

    # [Architectural fix -- own-position priority over snapshot veto]
    # How close a detection must be to a slot's OWN last known position
    # to be treated as "definitely still this slot, unmoved" -- strong
    # enough evidence that it overrides the snapshot-match veto entirely
    # (see every _matches_snapshot call site below). The snapshot veto
    # exists to answer "is this detection actually a DIFFERENT, already-
    # known neighbor rather than this slot's own content" -- but a
    # neighbor's snapshot box is, structurally, often close to THIS
    # slot's own position in exactly the case that matters most: a
    # worker carrying a different block (the neighbor) brushing past a
    # stationary block is BOTH what triggers this slot's brief occlusion
    # AND what populates its snapshot with that neighbor's nearby box.
    # Without a self-position check, the slot's own near-instant,
    # near-zero-displacement reappearance can get vetoed by a snapshot
    # entry that only exists because the real neighbor was passing
    # close by at that exact moment -- confirmed directly from user
    # report (worker carrying a different block briefly touched a
    # stationary one; the stationary block was denied its own identity
    # and given a temp id, while the carried block's identity later
    # drifted onto the stationary one's old slot). Deliberately tighter
    # than visible_match_dist_px (the snapshot test's own tolerance) --
    # this needs to mean "essentially exactly where it was," not merely
    # "in the neighborhood," or it would defeat the snapshot veto's own
    # purpose for genuinely ambiguous cases.
    STATIONARY_SELF_RECLAIM_DIST_PX = 25

    # [Architectural fix -- ordinary single-frame detector jitter
    # treated as a full occlusion episode] Before this fix, the very
    # FIRST frame a worker's box happened to be near a slot's box (or,
    # with no worker at all, another block's box) AND the block's own
    # detection genuinely dropped for that one frame, the full "fresh
    # pickup" bookkeeping committed immediately and unconditionally:
    # state flipped from "visible" to "occluded", bind_start_pos/
    # drag_confirmed reset, contact_frames reseeded, and -- critically
    # -- snapshot_boxes captured. A single missed detection frame is
    # ordinary, common noise (motion blur, a momentary confidence dip,
    # the detector itself jittering) -- confirmed as common directly
    # from this codebase's own earlier log evidence (a single slot
    # flickering evidence-clear/re-establish roughly once every 2
    # processed frames, for hundreds of frames straight). Committing to
    # full occlusion machinery on frame one of that kind of noise is
    # what forces every genuinely-stationary block through the heavier,
    # more failure-prone occluded/reconnect apparatus (snapshot checks,
    # priority-reclaim, FIFO tie-breaks) for reasons that have nothing
    # to do with the block actually being occluded -- more surface area
    # for exactly the identity-swap bugs already fixed elsewhere in
    # this class, for no benefit. This is how many CONSECUTIVE frames a
    # detection must stay missing, with occlusion evidence (worker or
    # block proximity) persisting, before the slot actually commits to
    # "occluded" state and runs the fresh-pickup reset -- ordinary
    # single/double-frame jitter never reaches this threshold and the
    # slot simply stays "visible," to be picked back up by the next
    # frame's ordinary Fast Association exactly as if nothing happened.
    # Deliberately small and separate from no_reappear_grace_frames
    # (which governs a DIFFERENT decision -- how long a slot may wait
    # with NO occlusion evidence at all before giving up) -- this one
    # is a debounce on the ONSET of occlusion evidence, not a giving-up
    # timer.
    OCCLUSION_ONSET_DEBOUNCE_FRAMES = 3

    # [Architecture -- the block owns identity, the worker only bridges
    # occlusion] How far outside a live worker's own CURRENT box a
    # detection may still be considered "emerging from that worker" --
    # small on purpose: this is meant to capture a block's edge peeking
    # out from behind/beside the worker's silhouette, not "somewhere in
    # the general vicinity". See Tier B2 in _generate_reconnect_candidates
    # for the hard elimination this gates.
    EMERGENCE_CORRIDOR_MARGIN_PX = 20

    # [Fix -- unrelated new arrival silently absorbed into a long-idle
    # occluded slot] The "unified" reconnect redesign (see
    # _generate_reconnect_candidates' own docstring) deliberately made
    # worker corroboration RANKING evidence only, never a hard
    # eliminator -- correct for the ordinary case (a slot hidden a
    # second or two behind a worker's own silhouette, reappearing right
    # where predicted). But with NO time limit on that leniency, a slot
    # that's been sitting "occluded" for a long time (worker who
    # explained it has since expired/walked off, block genuinely
    # departed off-screen and was never confirmed) stays a fully valid
    # candidate purely on position+size proximity -- and a platform's
    # staging spots get reused constantly, so a completely different,
    # freshly-arrived block landing in that same spot satisfies both
    # hard eliminators by pure physical coincidence. Confirmed directly
    # from user report: a slot occluded by a worker who then left frame
    # for good stayed a live reconnect candidate for roughly HALF the
    # video (bounded only by max_bound_occlusion_frames), and silently
    # absorbed a later, unrelated block that arrived at that exact
    # spot -- one real block was never counted, a second real block's
    # own identity was erased into the first's.
    #
    # Past this many seconds hidden, position+size proximity alone is
    # no longer trusted -- genuine, CURRENTLY-active worker emergence
    # corroboration (see worker_emerging below) becomes a THIRD hard
    # eliminator, on top of prediction-region and size. Short enough to
    # never affect the ordinary flicker/short-occlusion case this
    # redesign was built for (a ratio-driven detection dropout while a
    # worker's own silhouette covers the block for a couple seconds
    # continues to reconnect exactly as before, since worker_emerging is
    # trivially true then); long enough not to punish a real, briefly-
    # longer-than-usual occlusion where the same worker is still
    # visibly the one revealing the block. Same first-cut caveat as
    # every other named-and-isolated constant in this class (see
    # RECONNECT_RANK_MATERIAL_MARGIN_BLOCK_WIDTHS, WHOLE_BLOCK_AREA_
    # FRACTION): not empirically validated against ground truth, a
    # one-line tune once real footage confirms the right cutoff.
    RECONNECT_REQUIRE_WORKER_EMERGENCE_AFTER_SEC = 3.0

    def _update_block_size_estimate(self, box):
        """Exponential moving average of block width/height in pixels,
        updated from every confidently-matched detection. This is the
        camera-specific "what does one block look like right now" scale
        factor the reconnect scorer normalizes distances against."""
        w, h = box[2] - box[0], box[3] - box[1]
        size = (w + h) / 2.0
        if size <= 0:
            return
        if self._block_size_ema is None:
            self._block_size_ema = size
        else:
            self._block_size_ema = 0.95 * self._block_size_ema + 0.05 * size

    def _block_size_estimate(self):
        return self._block_size_ema if self._block_size_ema else 80.0

    def _looks_like_whole_block(self, box):
        """[Architecture -- slot state estimates the block, not the
        last detection] True if box's area is consistent with being the
        WHOLE physical block rather than a partial fragment of it -- see
        WHOLE_BLOCK_AREA_FRACTION for why this is area-based rather than
        the average-dimension comparison _box_size_similar uses
        elsewhere. Used by _update_matched_slot_geometry to decide
        whether this frame's observation(s) should reset the slot's
        estimated extent or merge into it."""
        block_size = self._block_size_estimate()
        if block_size <= 0:
            return True
        expected_area = block_size ** 2
        return box_area(box) >= expected_area * self.WHOLE_BLOCK_AREA_FRACTION

    def _reconnect_movement_score(self, pos, candidate):
        """Does the direction from the candidate's establishment point
        toward its last known position agree with the direction from its
        last known position to this new detection? Neutral (no penalty,
        no bonus) when there isn't enough motion history to judge --
        this is corroborating evidence only, never a gate."""
        origin = candidate.get("bind_start_pos") or candidate.get("established_pos")
        last_pos = candidate["pos"]
        if origin is None or dist(origin, last_pos) < 1e-6:
            return 0.5
        v1 = (last_pos[0] - origin[0], last_pos[1] - origin[1])
        v2 = (pos[0] - last_pos[0], pos[1] - last_pos[1])
        n1 = (v1[0] ** 2 + v1[1] ** 2) ** 0.5
        n2 = (v2[0] ** 2 + v2[1] ** 2) ** 0.5
        if n1 < 1e-6 or n2 < 1e-6:
            return 0.5
        cos_sim = (v1[0] * v2[0] + v1[1] * v2[1]) / (n1 * n2)
        return (cos_sim + 1.0) / 2.0  # remap [-1,1] -> [0,1]

    def _check_prior_split(self, sid, block_box, snapshot_boxes, frame_idx, seen_slots,
                            verbose=False, committed_worker_id=None):
        """Failsafe for the moment a worker-based load commits: check
        whether this same physical block had already split off into a
        separate, already-existing slot before this commit happened (e.g.
        because a detection gap exceeded the recent-merge window). Anchored
        to the block's OWN last-known box, not the worker's -- the worker
        may have moved on to something else entirely by commit time. If
        found, merge that slot back into this one, reverse the count, and
        let the surviving slot -- revived as visible, using the other
        slot's current tracking -- be the sole authority for this block's
        eventual departure. Returns True if a merge happened.

        [Fix -- same-worker sibling fragments wrongly vetoed] committed_worker_id
        is the worker who was actually carrying/delivering `sid` at the moment
        of commit (captured by the caller from _primary_worker_id/
        _representative_worker_id before _release_worker_binding wipes it).
        independently_bound used to disqualify ANY candidate carrying ANY
        occluded_by evidence at all, on the theory that a candidate with its
        own worker relationship must be a distinct, separately-occluded
        object (see that field's own docstring). That theory only holds when
        the candidate's worker is a DIFFERENT worker than the one who just
        delivered `sid`. When a single block gets detector-split into two
        fragments (e.g. a worker's hand/hook crossing its middle), both
        fragment slots end up with occluded_by populated by that SAME worker
        -- their own silhouette overlaps both halves of the one block they're
        carrying. Under the old rule, that shared-worker evidence was
        misread as proof of two independent blocks, permanently vetoing the
        merge this whole method exists to perform -- the sibling fragment
        slot was left stranded: still "active" (a leftover green circle on
        screen), never retired, never reconciled, inflating on-platform/
        loaded counts and remaining available as a same-distance candidate
        for future Fast Association matches (see _match_visible_slot),
        which is what let a later frame's whole-block detection latch onto
        the wrong one of the two sibling slots. Now only occluded_by
        evidence from a worker OTHER than committed_worker_id counts as
        "independently bound" -- occlusion purely by the same worker who
        just delivered `sid` is exactly the corroborating signal that this
        candidate is that block's own stranded fragment, not proof against
        it.

        Candidacy is judged against first_created_frame (immutable, set
        once at slot birth), NOT created_frame (a settling clock that gets
        legitimately reset on every reveal/stationary-reid/recent-merge/
        rollback reconnect). Using the settling clock here would make an
        old, established slot that simply reconnected a moment ago look
        "just born" indefinitely -- letting a genuinely separate, later
        arrival get permanently absorbed into it purely for having landed
        near the same spot on the platform.

        A candidate already carrying its own bound worker is additionally
        excluded outright, regardless of timing or proximity: it is a
        distinct, independently-tracked object by the registry's own
        worker-binding logic, not an orphaned fragment. Without this, two
        real blocks converging on the same small staging/exit area at the
        same time -- each with its own worker -- satisfy proximity and
        timing by construction, and would otherwise get silently merged
        every time."""
        candidates = [
            (osid, o) for osid, o in self.slots.items()
            if osid != sid and not o["counted"] and o["state"] != "gone"
            # [Fix 4] A slot already resolved/claimed by a detection this
            # very frame is not an orphaned fragment available for
            # merge-back -- it already has its own current-frame identity
            # resolution and must not be silently absorbed out from
            # under it.
            and osid not in seen_slots
            # [Fix -- window widened too far, causing false-positive
            # revivals] Was rollback_window_frames (90f/~3.6s, sized for
            # a different problem -- see this method's own docstring),
            # then widened to the FULL max_bound_occlusion_frames
            # (routinely 1000+ frames, a large fraction or even most of
            # a shorter video) to fix a real, evidenced case of a
            # genuine sibling created far in the past never being found.
            # That fix traded one bug for another: confirmed directly
            # from user report, a slot could now be matched as "the
            # prior split" of an essentially unrelated, much-earlier
            # slot purely because it fell within that huge window and
            # passed the position/snapshot checks by coincidence --
            # wrongly reviving it out of "gone" state, with nothing to
            # ever re-correct it afterward, so it sat there, solid and
            # visible, for the rest of the video. PRIOR_SPLIT_SEARCH_
            # FRAMES_FRACTION keeps this fps-proportional (still scales
            # correctly across different videos/frame rates, since it's
            # derived from max_bound_occlusion_frames rather than a flat
            # frame count) while substantially cutting how far back a
            # merge-back may reach -- generous enough for the single-long
            # -carry case that motivated the original widening, without
            # spanning enough of the video to start matching against
            # slots that have nothing to do with each other.
            and frame_idx - o.get("first_created_frame", o.get("created_frame", frame_idx))
                <= self.max_bound_occlusion_frames * self.PRIOR_SPLIT_SEARCH_FRAMES_FRACTION
        ]
        if verbose and candidates:
            print(f"    [merge-back-check] frame={frame_idx} slot={sid} just committed -- "
                  f"checking {len(candidates)} other recently-created slot(s) for a prior split")

        merged_any = False
        for osid, o in candidates:
            box_ok = boxes_close(o["box"], block_box, self.rollback_reappear_dist_px)
            snap_hit = self._matches_snapshot(o["box"], o["pos"], snapshot_boxes)
            # A genuine "prior split" fragment is, by definition, an orphan --
            # a piece of the same physical block that never got its own
            # independent tracking history. The moment a candidate carries
            # its OWN worker evidence, that's a distinct, separately-
            # occluded object (see Worker Evidence). Two real blocks
            # converging on the same small staging/exit area at the same
            # time, each with their own worker, will satisfy proximity +
            # timing by construction -- that is not evidence they are the
            # same block, and must never be treated as grounds for a merge.
            other_workers = set(o.get("occluded_by", {}).keys())
            if committed_worker_id is not None:
                other_workers -= {committed_worker_id}
            independently_bound = bool(other_workers)
            if verbose:
                reasons = []
                exempt_note = ""
                if not box_ok:
                    bcx, bcy = centroid(block_box)
                    d = dist(o["pos"], (bcx, bcy))
                    reasons.append(f"TOO_FAR_FROM_BLOCK_LAST_POS (dist={d:.0f}px, "
                                    f"margin={self.rollback_reappear_dist_px}px)")
                if snap_hit:
                    reasons.append("MATCHES_SNAPSHOT")
                if independently_bound:
                    reasons.append(f"INDEPENDENTLY_WORKER_BOUND (worker(s)="
                                    f"{sorted(other_workers)}, excluding same-worker="
                                    f"{committed_worker_id})")
                elif o.get("occluded_by"):
                    exempt_note = (f" [SAME_WORKER_OCCLUSION_EXEMPTED: worker(s)="
                                    f"{sorted(o.get('occluded_by', {}).keys())} all == "
                                    f"committed_worker_id={committed_worker_id}]")
                status = ("REJECTED: " + ", ".join(reasons) if reasons else "ACCEPTED") + exempt_note
                print(f"      - slot={osid} first_created_frame="
                      f"{o.get('first_created_frame', o.get('created_frame'))} "
                      f"pos=({o['pos'][0]:.0f},{o['pos'][1]:.0f}) box_ok={box_ok} "
                      f"snapshot_hit={snap_hit} "
                      f"occluded_by={sorted(o.get('occluded_by', {}).keys())} -> {status}")
            if not box_ok or snap_hit or independently_bound:
                continue

            if not merged_any:
                # [Unchanged] The FIRST accepted candidate is treated as
                # THE prior split of this exact departure: absorb its
                # tracking into the surviving slot and reverse the count
                # this commit just added, since only one physical
                # departure actually happened.
                s = self.slots[sid]
                self.loaded_count -= 1
                s["counted"] = False
                s["state"] = o["state"]
                s["pos"] = o["pos"]
                s["box"] = o["box"]
                s["last_seen_frame"] = o["last_seen_frame"]
                s["max_ratio_ever"] = max(s.get("max_ratio_ever", 0), o.get("max_ratio_ever", 0))
                s["high_ratio_frames"] = max(s.get("high_ratio_frames", 0), o.get("high_ratio_frames", 0))
                self._release_worker_binding(sid)
                s["created_frame"] = frame_idx
                s["pending_load"] = False
                s["frames_since_seen"] = o.get("frames_since_seen", 0)
                s["established_pos"] = o.get("established_pos", o["pos"])
                o["state"] = "gone"
                o["counted"] = True
                self._recent_worker_loads = [e for e in self._recent_worker_loads if e["sid"] != sid]
                print(f"  [Rollback:Full] MERGE-BACK: slot={osid} (first_created_frame="
                      f"{o.get('first_created_frame', o.get('created_frame'))}) was a "
                      f"prior split of slot={sid} — merged back, worker-load count reversed "
                      f"-> TOTAL={self.loaded_count}")
                merged_any = True
            else:
                # [Fix -- multiple stranded siblings never cleared] A
                # block can detector-split into MORE than two pieces
                # over a long occluded carry (see this method's own
                # docstring on PRIOR_SPLIT_SEARCH_FRAMES) -- e.g. S4,
                # then S5, then S6, before the block finally departs
                # under yet another id. Only ONE of those siblings can
                # be "the" prior split that gets its count reversed
                # (reversing more than once for a single real departure
                # would undercount); every OTHER sibling that clears the
                # exact same box/worker evidence checks is just as
                # stale and just as much a fragment of this one block,
                # it simply isn't the one chosen to carry the count
                # correction. Retiring it here (gone, counted so it can
                # never later score its own phantom departure) is what
                # actually clears its leftover circle from the overlay
                # -- previously this loop returned after the FIRST
                # match, leaving every additional sibling permanently
                # "active" on screen even after its own physical block
                # had already departed under a different id.
                o["state"] = "gone"
                o["counted"] = True
                self._recent_worker_loads = [e for e in self._recent_worker_loads if e["sid"] != osid]
                print(f"  [Rollback:Full] STALE-SIBLING RETIRED: slot={osid} (first_created_frame="
                      f"{o.get('first_created_frame', o.get('created_frame'))}) was ANOTHER prior "
                      f"split of the same block already merged into slot={sid} this frame -- "
                      f"retired (gone, not counted again) so its leftover marker clears")

        if verbose and candidates and not merged_any:
            print(f"    [merge-back-check] frame={frame_idx} no prior split found")
        return merged_any

    def _matches_snapshot(self, box, pos, snapshot_boxes):
        for sbox in snapshot_boxes:
            spos = centroid(sbox)
            if dist(pos, spos) <= self.visible_match_dist_px and self._box_size_similar(box, sbox):
                return True
        return False

    def _commit_reconnect(self, sid, box, pos, frame_idx, same_frame=False, dup_streak=None):
        """Shared side effects of accepting a reconnect: release any
        stale worker lock, reset the settling clock, and cancel any
        in-progress pending-load.

        [Unification] There is no more carried_this_frame ledger. Under
        the old three-pipeline design, a slot claimed by one detection
        this frame was invisible to every other mechanism (seen_slots
        excluded it everywhere), so a second fragment of the same
        worker-carried block needed an out-of-band dict to find its way
        back to the slot the first fragment just claimed.
        _generate_reconnect_candidates no longer excludes seen_slots --
        an already-claimed slot with elapsed_frames == 0 is simply
        another valid candidate, found the exact same way a hidden slot
        is found after real elapsed time (prediction region + size).
        No side-channel bookkeeping needed.

        The one piece of state this still needs to commit explicitly:
        the same-frame stationary-duplicate recurrence streak
        (SAME_FRAME_DUPLICATE_MAX_RECURRING_FRAMES) -- deliberately left
        untouched by this unification, not removed or generalized (see
        that constant's own docstring for why a detection recurring at
        one position for too many consecutive frames stops being
        trusted as detector noise and is instead treated as a genuinely
        separate, persistent object). Generation only PEEKS at what the
        next streak value would be, to decide eligibility; the value is
        only actually written here, once, for whichever candidate is
        actually chosen -- so a slot's streak can't be bumped multiple
        times in one frame just because multiple detections considered
        it as a candidate."""
        s = self.slots[sid]
        was_pending = s.get("pending_load", False)
        if same_frame and not s.get("occluded_by") and dup_streak is not None:
            s["dup_recur_pos"] = pos
            s["dup_recur_streak"] = dup_streak
        self._release_worker_binding(sid)
        s["created_frame"] = frame_idx
        s["pending_load"] = False
        return " (cancelled a pending worker-load count)" if was_pending else ""

    # [Architecture -- one physical-plausibility margin used for both
    # ranking and generation] A candidate is "materially better" than
    # the next-best one only if its distance-to-prediction is closer by
    # at least one block-width -- reusing the same camera-normalized
    # unit already used for the reachability radius (_block_size_estimate),
    # not a new, arbitrary constant. This is deliberately the ONLY
    # ranking signal used: reintroducing a multi-factor weighted score
    # here is exactly what the deterministic AND-chain redesign replaced
    # in the first place (see _generate_reconnect_candidates' own
    # docstring) -- distance-to-prediction is the one continuous signal
    # already computed by generation, it's physically grounded (closer
    # to where the slot's own frozen trajectory predicts it should be
    # IS better evidence of continuity), and it doesn't resurrect the
    # old scored system's failure mode of ad-hoc weighted tie-breaking.

    def _generate_reconnect_candidates(self, pos, box, frame_idx, seen_slots, verbose=True):
        """[Unified candidate generation -- single physical model] This
        method used to be one of three separate identity-resolution
        pipelines in this class -- _try_same_frame_fragment_merge
        (worker-carried same-frame splits), _try_same_frame_duplicate_merge
        (stationary same-frame splits), and this method (cross-frame
        occlusion reconnect). All three were answering the exact same
        question -- "does this detection belong to an existing,
        not-yet-claimed physical slot?" -- with three different
        distance constants and three different elimination chains that
        could, and did, disagree with each other about the same
        detection. That disagreement, not any single threshold, was the
        root cause of slot explosion: a detection that failed one
        pipeline's narrow gate fell through to the next, which had no
        memory of what the first one already knew, and eventually fell
        through all of them into a brand-new slot.

        There is now exactly one candidate generator and exactly one
        physical model, used identically regardless of WHEN the
        candidate slot was last claimed:
          - elapsed_frames == 0 (sid already in seen_slots this exact
            frame) is a same-frame split -- a second detection fragment
            of a block another fragment already claimed this frame.
          - elapsed_frames > 0 is an ordinary hidden-slot reconnect
            after real occlusion.
        Both are the same physical claim ("this detection and that
        slot's last known state are the same object"), evaluated with
        the same prediction-region math -- at elapsed_frames == 0 the
        predicted position is simply the slot's own current position
        (no extrapolation needed yet), which is already generous enough
        (block-size-normalized, floored at occluded_match_dist_px) to
        cover a wide worker splitting one block into pieces on either
        side of their body -- exactly the case the old, separate
        worker-fragment pipeline existed for, now covered for free by
        the same radius every other candidate uses.

        Exactly two HARD ELIMINATORS -- physical impossibilities, not
        soft evidence -- decide whether a slot is even a candidate:
          1. PREDICTED EMERGENCE REGION -- the detection must lie close
             to the slot's own frozen last_pos, extrapolated by its own
             frozen velocity over the elapsed hidden time, within a
             bounded, camera-relative radius.
          2. SIZE COMPATIBILITY -- the detection's box must be a
             plausible size match for the slot's own last known box.

        Everything else that used to be a veto is now RANKING EVIDENCE
        ONLY, read by the caller's dominance/FIFO selection
        (_try_deterministic_reconnect / _dominates) but never able to
        eliminate a candidate that already passed the two hard checks
        above:
          - MOTION CONSISTENCY: no longer rejects on a contradiction: a
            candidate that survived prediction + size is physically
            plausible regardless of which way it was moving before.
          - WORKER CORROBORATION: no longer requires the detection to
            touch a corroborating worker's box to be considered at all;
            whether it does is now one more ranking signal, not a
            precondition for candidacy.

        One thing is deliberately NOT touched by this unification: the
        same-frame stationary-duplicate recurrence cap
        (SAME_FRAME_DUPLICATE_MAX_RECURRING_FRAMES). That constant
        solves a different, narrower problem (a persistent second
        object being wrongly absorbed as if it were one-off detector
        noise) than the slot-explosion problem this refactor targets,
        and folding the two together risks trading one bug for another.
        So it stays exactly as strict as before, just evaluated inline
        here instead of in a separate method: a same-frame candidate
        with no worker evidence that has already recurred at this same
        position for SAME_FRAME_DUPLICATE_MAX_RECURRING_FRAMES straight
        frames is excluded from candidacy, full stop -- this is a THIRD
        hard eliminator, but a narrowly-scoped one that only ever
        applies to that one specific case, not a general veto over
        ordinary reconnects.

        Returns (evaluated, passed): evaluated is every sid considered
        at all (regardless of outcome); passed is a list of
        (sid, s, elapsed_sec, d, move_score, worker_emerging, same_frame,
        dup_streak_preview) tuples for every slot that survived the hard
        eliminators. dup_streak_preview is the recurrence-streak value
        this candidate WOULD have if chosen -- only actually written to
        the slot by _commit_reconnect for whichever candidate wins, so
        a slot considered (but not chosen) by multiple detections in
        the same frame never has its streak bumped more than once."""
        evaluated = []
        passed = []
        for sid, s in self.slots.items():
            if s["counted"] or s["state"] not in ("visible", "occluded"):
                continue
            elapsed_frames = frame_idx - s.get("last_seen_frame", frame_idx)
            same_frame = sid in seen_slots
            if same_frame and elapsed_frames != 0:
                # Shouldn't happen (last_seen_frame is updated at the
                # moment a slot is claimed), but guards against acting
                # on stale accounting rather than assuming it.
                continue
            if not same_frame and elapsed_frames <= 0:
                continue
            elapsed_sec = elapsed_frames / self.fps
            evaluated.append(sid)

            # 0. [Architectural fix -- restored from the prior working
            # codebase] Entry-corridor exclusion. The old codebase
            # applied this check in its rollback-match path (a
            # detection back in the entry corridor is a fresh arrival,
            # never treated as a departed block reappearing -- see
            # _in_entry_corridor's other call site) and separately
            # DAMPED (not eliminated) entry-corridor candidates in its
            # scored reconnect ranking. The "unified" reconnect rewrite
            # kept _in_entry_corridor for rollback but never carried
            # ANY version of it into this method, the path that handles
            # ordinary occlusion reconnects -- so a slot hidden/occluded
            # anywhere on the platform stayed a fully valid reconnect
            # target for a detection sitting right in the entry
            # corridor, with nothing to say "that's structurally where
            # NEW blocks originate, not where an existing hidden one
            # would reappear." Confirmed directly from log evidence
            # (20260303205345842): six separate real, physically
            # distinct blocks all arrived at the identical entry pixel
            # position over one run; distinguishing "a new arrival at
            # the doorway" from "a hidden block reappearing there" is
            # not a tunable-threshold problem, it's a location the
            # domain itself defines as one or the other. This is a hard
            # eliminator, not a damping factor, at same_frame==0: a
            # detection in the corridor is categorically a new arrival,
            # full stop. Same_frame==0 only, not elapsed_frames==0 --
            # deliberately does not touch same-frame split-fragment
            # merging (elapsed_frames==0 same_frame candidates are a
            # different physical claim entirely, see this method's own
            # docstring on same_frame, and can legitimately occur inside
            # the corridor, e.g. a block detector-split right as it's
            # being carried in).
            if not same_frame and self._in_entry_corridor(pos):
                if verbose:
                    print(f"      - slot={sid} REJECTED: DETECTION_IN_ENTRY_CORRIDOR "
                          f"(pos=({pos[0]:.0f},{pos[1]:.0f}), elapsed={elapsed_sec:.1f}s) -- "
                          f"looks like a fresh arrival at the doorway, not an existing hidden "
                          f"slot reappearing")
                continue

            # 0b. [Architectural fix -- snapshot check never wired in
            # here] Same rationale as _match_visible_slot/_match_
            # recently_occluded_slot's own new snapshot checks (see
            # their docstrings): a detection matching one of sid's own
            # recorded snapshot_boxes is a different, already-known
            # block that happened to be sitting nearby when sid went
            # occluded -- never sid's own hidden content, no matter how
            # well it satisfies the prediction-region/size checks below.
            # Wiring this into all three matching stages (Fast
            # Association, recently-occluded ownership, and this unified
            # reconnect path) closes the stationary-neighbor identity
            # swap at every point detection resolution can happen, not
            # just one of them.
            if (dist(pos, s["pos"]) > self.STATIONARY_SELF_RECLAIM_DIST_PX
                    and self._matches_snapshot(box, pos, s.get("snapshot_boxes", []))):
                if verbose:
                    print(f"      - slot={sid} REJECTED: MATCHES_OWN_SNAPSHOT "
                          f"(this detection matches a block recorded in slot={sid}'s own "
                          f"snapshot_boxes -- a different, already-known neighbor, not this "
                          f"slot's own hidden content, same_frame={same_frame})")
                continue

            # 1. Predicted emergence region -- HARD ELIMINATOR for a
            # CROSS-FRAME candidate only. At elapsed_frames == 0 this is
            # simply distance-to-current-pos; no separate, tighter
            # same-frame constant is used.
            #
            # [Architectural fix -- same-frame siblings still forced
            # through hard eliminators built for cross-frame reconnect]
            # same_frame (== sid in seen_slots) already means something
            # very specific and very strong: ANOTHER detection THIS
            # EXACT FRAME already resolved to this exact slot. That is
            # not "geometrically plausible" evidence like the prediction
            # -region math below -- it's direct, frame-local proof this
            # physical block is currently claimed right here, right now.
            # Confirmed directly from repeated user report across
            # several rounds of narrower fixes (a same-frame ambiguity-
            # count workaround, then a tightened version of it) that
            # STILL let a genuine single-block occlusion's second
            # fragment fail this or the size check below and mint its
            # own duplicate slot -- the underlying problem was applying
            # hard-eliminator machinery designed for "did a slot hidden
            # for real elapsed time actually reappear here" to a
            # completely different question ("is this piece part of the
            # SAME frame's already-identified block"), which it was
            # never built to answer and kept getting wrong in new ways
            # each time it was patched narrower. The snapshot check
            # above is the one mechanism in this class actually built
            # and repeatedly proven, over many fix rounds this
            # conversation, to correctly separate "sibling fragment of
            # THIS block" from "a different, already-known neighboring
            # block" -- so for same_frame candidates the ordinary
            # cross-frame prediction-region radius (built for real
            # elapsed occlusion time, and effectively unbounded once
            # velocity extrapolation is added in) is NOT used as the
            # gate. But that does not mean same_frame candidates get NO
            # positional gate at all.
            #
            # [Fix -- unbounded same-frame merge] Confirmed directly
            # from log evidence (20260310225553131): with same_frame
            # candidates exempted from the prediction-region check
            # entirely and no replacement ceiling in its place, every
            # OTHER genuinely separate, physically distinct block
            # detected in the same frame as an already-claimed slot was
            # passing as a "same-frame sibling" of that slot regardless
            # of how far away it actually was -- one recorded run had 5
            # distinct blocks 100-400px apart all merged into a single
            # slot, every frame, for roughly 3000 frames straight; none
            # of them ever got their own slot id, and the platform's
            # true count (5) came out as 2. same_frame is still strong,
            # direct evidence that SOME fragment of a block was claimed
            # this frame, but it says nothing about how far away a
            # genuine second fragment of THAT SAME physical block can
            # plausibly be -- that's exactly the question
            # _fragment_centroid_ceiling() already answers elsewhere in
            # this class for worker-split fragment reunification,
            # deliberately hard-capped at 2*visible_match_dist_px
            # regardless of a possibly-inflated block_size_estimate (see
            # that method's own docstring). Reusing it here keeps the
            # "direct frame-local evidence, no size match required"
            # relaxation intact for genuine same-block splits while
            # closing off the case where same_frame is actually masking
            # several distinct objects.
            vx, vy = s.get("velocity", (0.0, 0.0))
            pred_pos = (s["pos"][0] + vx * elapsed_frames, s["pos"][1] + vy * elapsed_frames)
            block_size = self._block_size_estimate()
            radius = max(block_size * 1.5, self.occluded_match_dist_px)
            d = dist(pos, pred_pos)
            if same_frame:
                same_frame_ceiling = self._fragment_centroid_ceiling()
                if d > same_frame_ceiling:
                    # [Fix -- shared-worker override] Confirmed directly
                    # from user report + screenshot (20260312103845210,
                    # ~13:16:36): a single long block, carried low and
                    # spanning well past the worker's body on BOTH ends,
                    # gets segmented as two disconnected fragments whose
                    # centroids are legitimately farther apart than the
                    # fixed 160px ceiling allows -- exactly the case that
                    # ceiling was never meant to reject. The ceiling
                    # exists to tell "genuine split fragment of ONE
                    # block" apart from "two distinct objects that
                    # happen to be in the same frame" (see this branch's
                    # own comment above) -- centroid distance is a proxy
                    # for that question, not the question itself. A much
                    # more direct answer is available when it applies:
                    # if THIS detection and slot={sid}'s own
                    # already-claimed fragment (its current s["box"],
                    # updated by the first fragment already resolved
                    # this exact frame) are BOTH touching the same
                    # single live worker's box, that worker is
                    # physically holding both pieces right now -- direct
                    # evidence they're one object, independent of how
                    # far apart the two fragments' centroids happen to
                    # read. Checked here, as a narrow override on the
                    # ceiling specifically, rather than folded into the
                    # ceiling itself, so the ordinary (no-worker-evidence)
                    # case keeps exactly the same protection against
                    # genuinely distinct objects it already had.
                    shared_worker = any(
                        not w.get("expired")
                        and boxes_close(box, w["box"], self.worker_bind_margin_px)
                        and boxes_close(s["box"], w["box"], self.worker_bind_margin_px)
                        for w in self.workers.values()
                    )
                    if not shared_worker:
                        if verbose:
                            print(f"      - slot={sid} REJECTED: SAME_FRAME_TOO_FAR "
                                  f"(same-frame candidate but dist={d:.0f}px > "
                                  f"ceiling={same_frame_ceiling:.0f}px -- too far from slot's own "
                                  f"position to plausibly be a split fragment of THIS block, and "
                                  f"no single live worker's box touches both fragments; more "
                                  f"likely a separate, distinct object claimed the same frame)")
                        continue
                    elif verbose:
                        print(f"      - slot={sid} SAME_FRAME_TOO_FAR waived: dist={d:.0f}px > "
                              f"ceiling={same_frame_ceiling:.0f}px, but this detection and "
                              f"slot={sid}'s own already-claimed fragment this frame both touch "
                              f"the same live worker's box -- direct evidence this one worker is "
                              f"physically carrying both pieces right now")
            elif d > radius:
                if verbose:
                    print(f"      - slot={sid} REJECTED: OUTSIDE_PREDICTED_REGION "
                          f"(dist={d:.0f}px > radius={radius:.0f}px, "
                          f"pred=({pred_pos[0]:.0f},{pred_pos[1]:.0f}), elapsed={elapsed_sec:.1f}s, "
                          f"same_frame={same_frame}) -- prediction failure is fatal")
                continue

            # 2. Worker corroboration -- computed BEFORE the size check
            # below so real worker evidence can waive it (see that
            # check's own comment for why). Tests every worker currently
            # in occluded_by, not a single privileged one.
            #
            # [Fix -- worker handoff / worker-id churn] Also accepts any
            # CURRENTLY LIVE worker who is a recorded handoff_partner of
            # one of occ's worker ids, even if that worker's own id
            # never literally appears in occ -- see the handoff_partners
            # update in update_workers. Without this, a worker-id swap
            # during a brief mutual worker occlusion (person tracker
            # reassigning an id right as the two workers separate) makes
            # occ permanently point at a now-expired id, RECONNECT_
            # REQUIRE_WORKER_EMERGENCE_AFTER_SEC's hard elimination then
            # rejects the (physically legitimate) reconnect past that
            # threshold, and the block mints a brand-new slot instead of
            # continuing under its own -- a double count. Confirmed
            # directly from user report.
            occ = s.get("occluded_by")
            worker_emerging = False
            if occ:
                for wid in occ:
                    w = self.workers.get(wid)
                    if w is not None and not w.get("expired") and boxes_close(box, w["box"], self.EMERGENCE_CORRIDOR_MARGIN_PX):
                        worker_emerging = True
                        break
                if not worker_emerging:
                    for wid, w in self.workers.items():
                        if w.get("expired") or wid in occ:
                            continue
                        if (w.get("handoff_partners", set()) & set(occ.keys())
                                and boxes_close(box, w["box"], self.EMERGENCE_CORRIDOR_MARGIN_PX)):
                            worker_emerging = True
                            break

            # 3. Size compatibility -- HARD ELIMINATOR for both same-
            # frame and cross-frame candidates, using the SAME absolute,
            # EMA-calibrated reference either way -- UNLESS worker_
            # emerging is already True.
            #
            # [Fix -- comparing against the wrong reference] This used to
            # compare a cross-frame candidate against the SLOT's OWN last
            # recorded box (_box_size_similar(box, s["box"])) -- but a
            # block carried by a worker is visually unstable frame to
            # frame by nature: sometimes just a sliver peeks past an arm,
            # sometimes it sticks out past the worker on both ends and
            # reads as huge. Confirmed directly from log evidence
            # (20260312103845210, slot=4/slot=5): a slot's own last-
            # recorded box happened to be captured mid-protrusion (300-
            # 450px wide, category-different from a normal ~100-250px
            # block), and every subsequent, perfectly ordinary,
            # correctly-sized reappearance of the SAME physical block
            # then failed size comparison against that one bad snapshot,
            # every single frame, permanently -- minting a brand new
            # slot for a block that never actually left. Switching to
            # the running, many-observation EMA (_block_size_estimate)
            # fixed that specific failure, but introduced a new one,
            # also confirmed directly from log evidence on the very same
            # video: the EMA itself starts small (6,400px^2 at frame 446)
            # and climbs slowly across the whole run (still under
            # 100,000px^2 by frame 9770) -- so a genuinely large or
            # elongated block (this same long block, sticking out past
            # the worker on both ends) can have its OWN correct,
            # single-object detection rejected as "too big to be one
            # block" simply because the average hasn't caught up yet,
            # especially early in a video. Neither reference (one slot's
            # last box, or a slow-converging global average) is reliable
            # enough to hard-veto on alone for an object whose apparent
            # size varies this much by nature. Worker evidence is the
            # strongest available signal here and doesn't share this
            # weakness -- a worker directly touching this exact detection
            # (worker_emerging, just computed above) is direct physical
            # evidence regardless of absolute size, so it waives the size
            # gate entirely rather than being weighed against it. Only
            # a detection with NO worker evidence at all still needs to
            # clear the size gate -- exactly the case this check was
            # actually built for (an unrelated, worker-less object -- a
            # stray box, a shadow, noise -- reconnecting purely on
            # position).
            if not worker_emerging:
                expected_single_block_area = self._block_size_estimate() ** 2
                plausibly_one_block = (
                    expected_single_block_area <= 0
                    or box_area(box) <= expected_single_block_area * self.MAX_PARTIAL_ESTIMATE_AREA_FRACTION
                )
                if not plausibly_one_block:
                    if verbose:
                        print(f"      - slot={sid} REJECTED: SIZE_MISMATCH "
                              f"(this detection's own box is far too large to plausibly be one "
                              f"block, and no worker corroborates it -- likely a worker or other "
                              f"non-block object, same_frame={same_frame})")
                    continue
            elif verbose:
                print(f"      - slot={sid} SIZE_MISMATCH check waived: a live worker directly "
                      f"corroborates this detection -- trusted over the (possibly still-"
                      f"converging) average block size")

            # 4. [Fix -- unrelated new arrival absorbed into a stale
            # occluded slot] HARD ELIMINATOR, but only past
            # RECONNECT_REQUIRE_WORKER_EMERGENCE_AFTER_SEC of hidden
            # time -- see that constant's own docstring. A same-frame
            # candidate (elapsed_sec == 0, by construction a split
            # fragment of a block another fragment already claimed
            # THIS frame) is never subject to this: there's no
            # meaningful "hidden time" to distrust yet.
            if (not same_frame and elapsed_sec > self.RECONNECT_REQUIRE_WORKER_EMERGENCE_AFTER_SEC
                    and not worker_emerging):
                if verbose:
                    print(f"      - slot={sid} REJECTED: STALE_NO_WORKER_CORROBORATION "
                          f"(hidden {elapsed_sec:.1f}s > "
                          f"{self.RECONNECT_REQUIRE_WORKER_EMERGENCE_AFTER_SEC:.1f}s with no "
                          f"currently-active worker corroborating this exact detection -- "
                          f"position+size proximity alone is too weak evidence this is the same "
                          f"block reappearing rather than a new, unrelated arrival at the same "
                          f"spot)")
                continue

            # 3. Same-frame stationary-duplicate recurrence cap -- HARD
            # ELIMINATOR, but narrowly scoped (see docstring): only for
            # same-frame candidates with no worker evidence at all. A
            # worker-carried same-frame split never had this cap.
            dup_streak_preview = None
            if same_frame and not s.get("occluded_by"):
                recur_pos = s.get("dup_recur_pos")
                is_same_recurring = (
                    recur_pos is not None
                    and dist(pos, recur_pos) <= self.SAME_FRAME_DUPLICATE_RECURRING_POS_TOLERANCE_PX
                )
                dup_streak_preview = s.get("dup_recur_streak", 0) + 1 if is_same_recurring else 1
                if dup_streak_preview > self.SAME_FRAME_DUPLICATE_MAX_RECURRING_FRAMES:
                    if verbose:
                        print(f"      - slot={sid} REJECTED: PERSISTENT_SECOND_OBJECT "
                              f"(same detection has recurred at this position for "
                              f"{dup_streak_preview} consecutive frames > "
                              f"{self.SAME_FRAME_DUPLICATE_MAX_RECURRING_FRAMES} -- no longer "
                              f"treated as one-off detector noise)")
                    continue

            # 4. Motion consistency -- RANKING EVIDENCE ONLY (no longer
            # eliminates). Neutral (0.5) when there's no motion history
            # to judge.
            move_score = self._reconnect_movement_score(pos, s)

            passed.append((sid, s, elapsed_sec, d, move_score, worker_emerging, same_frame, dup_streak_preview))

        return evaluated, passed

    def _log_reconnect_diagnostics(self, frame_idx, pos, passed, decision, sid, reason):
        """[Temporary -- validation diagnostics, see
        RECONNECT_DIAGNOSTICS_ENABLED] For every committed reconnect,
        prints the detection itself, the full candidate pool exactly as
        generation handed it to ranking (i.e. every candidate that
        survived ALL FOUR generation gates -- prediction, motion, size,
        worker-emergence -- not a further-narrowed subset), each
        candidate's raw evidence (prediction distance, motion tier,
        worker corroboration), which decision path resolved it
        (SINGLE_CANDIDATE / DOMINANCE / FIFO), which slot was chosen,
        and why. Purely observational -- reads passed/self.slots only,
        never writes anything, never called anywhere except this one
        site in _try_deterministic_reconnect. Safe to delete entirely,
        or just flip RECONNECT_DIAGNOSTICS_ENABLED to False, once
        validation against real footage is done."""
        if not self.RECONNECT_DIAGNOSTICS_ENABLED:
            return
        lines = [
            "",
            f"[ReconnectDiag] Frame: {frame_idx}",
            "",
            "Detection:",
            f"  center=({pos[0]:.0f},{pos[1]:.0f})",
            "",
            "Generated candidates:",
        ]
        for cand_sid, _, _, _, _, _, _, _ in passed:
            lines.append(f"  S{cand_sid}")
        lines.append("")
        lines.append("Evidence:")
        for cand_sid, cand_s, _, cand_d, cand_move, cand_worker_emerging, cand_same_frame, _ in passed:
            motion_tier = 1 if cand_move > 0.5 else 0
            worker_corroborated = "yes" if cand_worker_emerging else "no"
            lines.append("")
            lines.append(f"  S{cand_sid}")
            lines.append(f"    same_frame = {cand_same_frame}")
            lines.append(f"    prediction distance = {cand_d:.0f}px")
            lines.append(f"    motion tier = {motion_tier} (raw motion_score={cand_move:.2f})")
            lines.append(f"    worker corroborated (emerging) = {worker_corroborated}")
        lines.append("")
        lines.append("Decision:")
        lines.append(f"  {decision}")
        lines.append("")
        lines.append("Chosen slot:")
        lines.append(f"  S{sid}")
        lines.append("")
        lines.append("Reason:")
        lines.append(f"  {reason}")
        lines.append("")
        print("\n".join(lines))

    def _dominates(self, a, b, material_margin_px):
        """[Ranking -- Pareto dominance, not a weighted score] a and b
        are (sid, s, elapsed_sec, d, move_score) candidate tuples from
        _generate_reconnect_candidates. Returns True if a is not worse
        than b on every evidence axis already computed during
        generation (within measurement-noise tolerance -- see below),
        and meaningfully better on at least one.

        Deliberately NOT a blended/weighted score (e.g. w1*distance +
        w2*motion + w3*worker). This file already tried, and removed,
        a mechanism where worker proximity alone could decide an
        identity (_try_worker_reveal_match -- see
        _try_deterministic_reconnect's own docstring history) precisely
        because a strong-but-wrong signal on one axis could rescue a
        candidate that had no real evidence on another. A weighted sum
        recreates that exact risk one level up: for the right weights,
        a strong worker term can always outvote a weak distance term.
        Dominance can't do that by construction -- a candidate with
        worker evidence but a worse distance or motion reading than its
        rival does NOT dominate; that's a genuine trade-off, and
        genuine trade-offs fall through to the FIFO tie-break rather
        than being resolved by an implicit, unstated weighting choice.

        [Fix -- noise tolerance on the "not worse" side] Confirmed bug:
        the "not worse" comparisons used strict `<=`/`>=` with zero
        tolerance, so a candidate could be blocked from dominating an
        otherwise-clearly-inferior rival purely because it was a single
        pixel of detector jitter "behind" on distance -- e.g. distance
        5px vs 4px, motion tier 1 vs 0 (a real, decisive difference):
        the 1px gap alone used to fail not_worse and force an
        unnecessary FIFO tie-break despite the motion evidence being
        completely one-sided. Distance now tolerates differences up to
        SAME_FRAME_DUPLICATE_RECURRING_POS_TOLERANCE_PX -- the same
        already-established, already-justified jitter tolerance this
        file uses elsewhere for "close enough to call the same position
        rather than a fresh one" (see _try_same_frame_duplicate_merge) --
        rather than inventing a new pixel constant for this method.

        [Known, disclosed limitation -- NOT fixed here] The motion tier
        boundary (0.5) has no equivalent tolerance: two candidates at
        0.499 and 0.501 land in different tiers despite the gap being
        pure noise. Unlike distance, there is no existing, independently
        -justified epsilon anywhere in this file for the movement-score
        scale to reuse -- inventing one now would be exactly the kind of
        unvalidated new number this whole exercise has been trying to
        avoid. Left as a known edge case rather than papered over;
        revisit only if empirical testing on real footage actually shows
        candidates flapping across this exact boundary, per the same
        "don't optimize the rare case pre-emptively" principle already
        applied to pool-exhaustion-at-exit earlier in this design.

        Three axes, each using only quantities/boundaries the AND-chain
        already established:
          - distance-to-prediction (d): lower is better. "Not worse"
            tolerates SAME_FRAME_DUPLICATE_RECURRING_POS_TOLERANCE_PX of
            jitter; "meaningfully better" reuses material_margin_px, the
            same block-width-normalized margin already used for the
            single-axis version of this ranking.
          - motion tier: _reconnect_movement_score's own documented
            meaning already splits it into "no real history" (0.5,
            neutral) versus "genuinely agrees with established travel
            direction" (>0.5) -- that boundary is reused as-is. (Below
            0.35 never reaches this method at all; that's gate 2's hard
            rejection.)
          - worker tier: whether this detection is actually touching one
            of the slot's corroborating workers' current boxes
            (worker_emerging, computed once during generation and
            carried through rather than re-derived or discarded). Now
            that worker corroboration is ranking evidence rather than a
            candidacy gate, this reads the emergence check's own result
            -- not just "does the slot happen to carry any worker
            evidence at all" -- so a slot with stale, non-corroborating
            occluded_by no longer gets an unearned edge over a rival
            with none. A tier, same as motion -- present/absent, not a
            magnitude, so it can contribute to dominance but can never
            outweigh a simultaneous loss on the other two axes."""
        _, a_s, _, a_d, a_move, a_worker_emerging, _, _ = a
        _, b_s, _, b_d, b_move, b_worker_emerging, _, _ = b
        a_motion_tier = 1 if a_move > 0.5 else 0
        b_motion_tier = 1 if b_move > 0.5 else 0
        a_worker_tier = 1 if a_worker_emerging else 0
        b_worker_tier = 1 if b_worker_emerging else 0
        distance_noise_px = self.SAME_FRAME_DUPLICATE_RECURRING_POS_TOLERANCE_PX

        not_worse = (
            a_d <= b_d + distance_noise_px
            and a_motion_tier >= b_motion_tier
            and a_worker_tier >= b_worker_tier
        )
        if not not_worse:
            return False
        return (
            a_d <= b_d - material_margin_px
            or a_motion_tier > b_motion_tier
            or a_worker_tier > b_worker_tier
        )

    def _try_deterministic_reconnect(self, pos, box, frame_idx, seen_slots, other_boxes, verbose=False):
        """[Candidate selection -- unified] Calls
        _generate_reconnect_candidates for the physically-plausible
        pool -- now covering same-frame splits and cross-frame
        occlusion reconnects identically, see that method's docstring
        -- then decides:

          0 candidates -> nothing to reconnect to.
          1 candidate  -> commit immediately, no ranking needed.
          2+ candidates -> RANK by the full evidence vector generation
             already computed (distance-to-prediction, motion tier,
             worker-corroboration tier -- see _dominates), using Pareto
             dominance rather than a blended score: a candidate wins
             outright only if it is not worse than every other survivor
             on every axis AND meaningfully better on at least one.
             That's a real, evidence-based win: commit to it, not a
             guess. If no candidate dominates -- because the evidence
             genuinely trades off between candidates (one closer in
             distance, another stronger on motion or worker evidence)
             -- that IS a genuine tie, and only THEN does the FIFO
             tie-break decide: the candidate with the smallest
             last_seen_frame (hidden longest) wins. This is bookkeeping,
             not a claim about which physical block it actually was --
             the whole premise of a genuine tie is that no evidence,
             including this one, can tell them apart. No new queue
             state is introduced: last_seen_frame already exists on
             every slot for an unrelated reason (occlusion timing), and
             is simply read here as an insertion-order proxy.

        Returns (sid_or_None, rejected_sid_or_None). rejected_sid is
        populated only when exactly one slot was evaluated as a
        candidate at all and it failed -- mirrors the old single-
        candidate attribution used to drive a provisional slot's
        resolver_failed_streak (see _resolve_provisional_terminal_state)
        without inventing a second lookup. When 0 slots are evaluated,
        or when candidates existed but were resolved (uniquely, by
        dominance, or by FIFO), rejected_sid is None."""
        evaluated, passed = self._generate_reconnect_candidates(pos, box, frame_idx, seen_slots, verbose=verbose)

        if len(passed) == 0:
            rejected = evaluated[0] if len(evaluated) == 1 else None
            return None, rejected

        if len(passed) == 1:
            sid, s, elapsed_sec, d, move_score, worker_emerging, same_frame, dup_streak = passed[0]
            resolution_note = "single candidate"
            decision = "SINGLE_CANDIDATE"
            reason = "Only one physically plausible candidate -- no ranking needed"
        else:
            material_margin = self.RECONNECT_RANK_MATERIAL_MARGIN_BLOCK_WIDTHS * self._block_size_estimate()
            dominant_idx = None
            for i, cand in enumerate(passed):
                if all(i == j or self._dominates(cand, other, material_margin)
                       for j, other in enumerate(passed)):
                    dominant_idx = i
                    break
            if dominant_idx is not None:
                sid, s, elapsed_sec, d, move_score, worker_emerging, same_frame, dup_streak = passed[dominant_idx]
                resolution_note = (f"ranked: {len(passed)} candidates passed, slot={sid} "
                                    f"dominates every other candidate across the full evidence "
                                    f"vector (distance, motion, worker evidence) -- not worse on "
                                    f"any axis, meaningfully better on at least one -- decided by "
                                    f"existing evidence, not FIFO")
                decision = "DOMINANCE"
                reason = "Dominated every other candidate"
            else:
                # No candidate dominates -- the evidence genuinely
                # trades off between candidates (e.g. one closer in
                # distance, another stronger on motion/worker evidence).
                # That's a real tie, not resolvable by any single axis
                # without an unjustified implicit weighting -- FIFO
                # tie-break, derived from last_seen_frame (no new
                # state). Oldest-hidden slot wins.
                oldest = min(passed, key=lambda p: p[1].get("last_seen_frame", frame_idx))
                sid, s, elapsed_sec, d, move_score, worker_emerging, same_frame, dup_streak = oldest
                ids = [p[0] for p in passed]
                resolution_note = (f"FIFO tie-break: {len(passed)} candidates ({ids}) satisfied "
                                    f"every deterministic check and no candidate dominates the "
                                    f"others on the full evidence vector (distance, motion, worker "
                                    f"evidence) -- genuine trade-off, not decidable without an "
                                    f"implicit weighting, so the longest-hidden slot "
                                    f"(last_seen_frame={s.get('last_seen_frame')}) is chosen as "
                                    f"bookkeeping only, not a claim about which physical block it "
                                    f"actually was")
                decision = "FIFO"
                reason = "No dominant candidate -> FIFO"

        self._log_reconnect_diagnostics(frame_idx, pos, passed, decision, sid, reason)

        cancel_note = self._commit_reconnect(sid, box, pos, frame_idx, same_frame=same_frame, dup_streak=dup_streak)
        print(f"  [Reconnect:Unified] slot={sid} satisfied both hard eliminators (prediction "
              f"region, size) -- dist_to_prediction={d:.0f}px, elapsed={elapsed_sec:.1f}s, "
              f"same_frame={same_frame}, motion_score={move_score:.2f}, "
              f"worker_emerging={worker_emerging}, {resolution_note} "
              f"-> reconnected{cancel_note} (frame {frame_idx})")
        return sid, None

    @staticmethod
    def _box_size_similar(boxA, boxB, tolerance=0.5):
        """Binary size-match test, kept for _matches_snapshot (a simple
        accept/reject check). The reconnect candidate scorer above uses
        the continuous _box_size_similarity_score version instead."""
        wa, ha = boxA[2] - boxA[0], boxA[3] - boxA[1]
        wb, hb = boxB[2] - boxB[0], boxB[3] - boxB[1]
        if wb <= 0 or hb <= 0:
            return True
        w_ratio = wa / wb
        h_ratio = ha / hb
        return (1 - tolerance) <= w_ratio <= (1 + tolerance) and (1 - tolerance) <= h_ratio <= (1 + tolerance)

    def _resolve_detection_identity(self, pos, box, frame_idx, seen_slots, other_boxes):
        """Runs the full detection-to-slot identity chain for a single
        detection. Collapsed, by design, to exactly two stages:

            1. unified candidate reconnect   [Reconnect:Unified]
            2. rollback (tight)              [Rollback:Tight]

        [Unification] This used to be three independent identity-
        resolution pipelines run in sequence -- same-frame worker-
        carried fragment merge, same-frame stationary-duplicate merge,
        and cross-frame candidate reconnect -- each answering the same
        underlying question ("does this detection belong to an existing
        slot?") with its own distance constants and its own veto chain.
        A detection that failed one pipeline's narrow gate fell through
        to the next with no memory of what the first one had already
        evaluated, and if it failed all three it minted a brand-new
        slot -- even when, e.g., candidate generation had already found
        it a single, otherwise-perfectly-plausible candidate that a
        stricter earlier-stage gate had rejected for an unrelated
        reason. That disagreement between independent physical models,
        not any single threshold, was the actual cause of slot
        explosion under slight occlusion, slight movement, or detector
        fragmentation. Stage 1 now is a single call into
        _try_deterministic_reconnect / _generate_reconnect_candidates,
        which evaluates every not-yet-claimed slot -- whether claimed
        this exact frame (a same-frame split) or hidden for real
        elapsed time (an occlusion reconnect) -- under the identical
        prediction-region + size-compatibility test. See that method's
        own docstring for the full reasoning, including why the
        same-frame stationary-duplicate recurrence cap is deliberately
        the one piece of prior behavior left untouched rather than
        folded into this unification.

        [Architecture -- identity belongs to the block, not the worker]
        There used to be a stage here: worker-reveal
        (_try_worker_reveal_match), a hard, unscored short-circuit that
        reconnected a detection touching a bound worker's box directly
        to that worker's slot, with NO comparison against any other
        candidate and no requirement that the position/size/motion
        evidence actually support it being the same physical object.
        Confirmed bug, traced to exact numbers in a real log: a
        worker bound to a long-occluded slot (14.2s hidden) touched a
        completely different, never-before-seen block 288px away, and
        this stage reattached that new block's detection to the old
        slot's identity purely because the worker was nearby and the
        distance was not physically IMPOSSIBLE -- with zero appearance
        or trajectory evidence actually confirming it was the same
        block. That's a structural property of being a bypass: it never
        had to answer to anything else. Worker corroboration is still
        real evidence -- it now enters purely as ranking evidence inside
        _dominates, so it can corroborate a match or break a tie, but it
        can no longer single-handedly decide one, nor eliminate a
        candidate that never had a worker relationship at all.

        Stage 1 is itself hybrid: two hard eliminators (prediction
        region, size) narrow the field first, and dominance/FIFO
        selection is only invoked at all when 2+ candidates remain
        genuinely ambiguous after that -- a single surviving candidate
        reconnects deterministically, with no ranking needed. Rollback
        remains a distinct, final safety net for the different (and
        rarer) situation where a slot was already confirmed COUNTED and
        this detection proves that was a false positive -- not an
        identity-resolution question at all.

        Returns (slot_id, mechanism, rejected_sids). rejected_sids holds
        AT MOST ONE slot id and is only ever populated by stage 1 -- the
        only stage with real per-candidate elimination to surface; it's
        empty whenever stage 1 matched, when nothing survived
        elimination at all, or when 2+ candidates were genuinely
        ambiguous (that's evidence of ambiguity, not evidence against
        any one of them)."""
        sid, rejected_sid = self._try_deterministic_reconnect(pos, box, frame_idx, seen_slots,
                                                                other_boxes, verbose=True)
        rejected_sids = [rejected_sid] if rejected_sid is not None else []
        if sid is not None:
            return sid, "Reconnect:Unified", []

        sid = self._try_rollback_match(pos, box, frame_idx, verbose=True)
        if sid is not None:
            return sid, "Rollback:Tight", []

        return None, None, rejected_sids

    # ==================================================================
    # Entry Calibration
    # ==================================================================

    def _record_entry_vote(self, pos):
        if self.entry_side is not None:
            return
        side = nearest_edge_side(pos, self.platform_box)
        self._entry_votes.append(side)
        print(f"  entry-side auto-detect: genuine low-ratio arrival near '{side}' edge "
              f"({len(self._entry_votes)}/{self.entry_side_votes_needed} votes)")
        if len(self._entry_votes) >= self.entry_side_votes_needed:
            counts = {}
            for v in self._entry_votes:
                counts[v] = counts.get(v, 0) + 1
            self.entry_side = max(counts, key=counts.get)
            print(f"  ENTRY SIDE AUTO-DETECTED: '{self.entry_side}' "
                  f"(from {len(self._entry_votes)} observed arrivals: {counts})")

    def _check_entry_side_timeout(self, frame_idx):
        if self.entry_side is not None or self.entry_side_timeout_frames is None:
            return
        if frame_idx < self.entry_side_timeout_frames:
            return
        if self._entry_votes:
            counts = {}
            for v in self._entry_votes:
                counts[v] = counts.get(v, 0) + 1
            self.entry_side = max(counts, key=counts.get)
            print(f"  ENTRY SIDE TIMEOUT: locking in '{self.entry_side}' from partial "
                  f"evidence ({counts}) rather than waiting indefinitely")
        else:
            self.entry_side = self.entry_side_fallback
            print(f"  ENTRY SIDE TIMEOUT: no genuine arrivals observed at all — falling back "
                  f"to default '{self.entry_side}'. Counting was disabled until now; check "
                  f"whether this default matches your actual camera layout.")

    def _in_entry_corridor(self, pos):
        if self.entry_side is None:
            return True
        x, y = pos
        x1, y1, x2, y2 = self.platform_box
        if self.entry_side == "left":
            return x1 - self.entry_corridor_depth_px <= x <= x1 + self.entry_corridor_depth_px
        if self.entry_side == "right":
            return x2 - self.entry_corridor_depth_px <= x <= x2 + self.entry_corridor_depth_px
        if self.entry_side == "top":
            return y1 - self.entry_corridor_depth_px <= y <= y1 + self.entry_corridor_depth_px
        return y2 - self.entry_corridor_depth_px <= y <= y2 + self.entry_corridor_depth_px

    def _inside_platform(self, pos):
        x, y = pos
        x1, y1, x2, y2 = self.platform_box
        return x1 <= x <= x2 and y1 <= y <= y2

    # ==================================================================
    # Provisional Slot Promotion
    # A provisional (pending) slot is an ordinary entry in self.slots --
    # every existing resolution mechanism already applies to it for
    # free. These two methods own the ONE thing that's actually new: the
    # decision of when a still-unclaimed provisional slot has earned
    # "arrival" status. Neither commits a departure; that stays owned by
    # the Exit subsystem (_check_direct_exit / _check_drag_exit), which
    # calls _promote_provisional_slot itself for the terminal path.
    # ==================================================================

    def _promote_provisional_slot(self, sid, frame_idx, terminal=False):
        """Converts a PENDING slot into a CONFIRMED one -- the single
        place that performs "arrival" bookkeeping (entry-corridor vote +
        entered_count), regardless of which path triggered it (normal
        accumulation, or terminal exit-boundary confirmation).

        Deliberately anchored to the slot's OWN first-observed evidence
        (first_seen_frame / established_pos) rather than the current
        frame's -- for a normally-promoted slot these are close in time
        anyway, but for a TERMINAL promotion the current frame IS the
        exit boundary, and voting/counting from that position would
        misattribute which edge the block actually arrived from.

        Not idempotent by design -- callers only ever invoke this while
        "provisional" is still True, so a slot's arrival is counted
        exactly once no matter which promotion path reaches it first.

        Kept as its own step, called BEFORE any departure bookkeeping in
        the terminal-promotion path, so "this block existed" and "this
        block left" remain two distinct, separately-attributed events
        even when both are decided within the very same frame -- never
        collapsed into one atomic fact. This mirrors how Rollback:Tight
        already treats a count correction as a distinct claim from a new
        physical identity (see that method's own docstring) -- the same
        discipline applied to the opposite end of a slot's life."""
        s = self.slots[sid]
        if not s.get("provisional", False):
            return
        first_frame = s.get("first_seen_frame", frame_idx)
        first_pos = s.get("established_pos", s["pos"])

        self._record_entry_vote(first_pos)
        is_new_entry = self._in_entry_corridor(first_pos)
        s["entry_meaningful"] = is_new_entry
        s["provisional"] = False

        tag = "TERMINAL PROMOTION" if terminal else "PROMOTED"
        if is_new_entry:
            self.entered_count += 1
            print(f"  {tag}: slot={sid} ENTERED at ({first_pos[0]:.0f},{first_pos[1]:.0f}) "
                  f"(first seen frame {first_frame}, promoted frame {frame_idx}) "
                  f"-> entered_count={self.entered_count}")
        else:
            print(f"  {tag}: slot={sid} appeared away from entry corridor at "
                  f"({first_pos[0]:.0f},{first_pos[1]:.0f}) (first seen frame {first_frame}, "
                  f"promoted frame {frame_idx})")

    def _check_normal_promotion(self, frame_idx):
        """Normal promotion path: every frame, checks every still-pending
        provisional slot against the SAME confidence bar an established
        slot already has to clear elsewhere in this class -- sustained
        high-ratio visibility (min_high_ratio_frames) held over a real
        amount of observed time (min_settling_frames, measured from
        first_seen_frame rather than created_frame so a slot that was
        later reconnected-through doesn't get an unearned head start).
        No new confidence metric is introduced: both thresholds already
        gate other commitments in this class (DirectExit, DragExit) for
        exactly the same reason -- a handful of instantaneous high-ratio
        frames right after appearing isn't enough to trust yet, but
        sustained high-confidence presence is.

        Runs once per frame, right after Phase 2 and before Phase 4's
        exit checks, so a slot that qualifies for normal promotion AND
        happens to already be past the exit boundary in the very same
        frame is promoted first and then evaluated as a perfectly
        ordinary (non-terminal) exit right after -- terminal promotion
        only ever needs to fire for slots that didn't get here in time."""
        for sid, s in self.slots.items():
            if not s.get("provisional", False):
                continue
            if s["counted"] or s["state"] not in ("visible", "occluded"):
                continue
            if (s.get("high_ratio_frames", 0) >= self.min_high_ratio_frames
                    and frame_idx - s.get("first_seen_frame", frame_idx) >= self.min_settling_frames):
                self._promote_provisional_slot(sid, frame_idx, terminal=False)

    def _resolve_provisional_terminal_state(self, sid, frame_idx):
        """[Fix -- terminal decision for provisional identities] Called
        the instant a provisional slot's resolver_failed_streak reaches
        resolver_exhausted_frames.

        That streak is charged in exactly one place: the main detection
        loop in update_blocks, at the moment a real detection has been
        run through the full identity resolver (fast association,
        unified candidate reconnect, rollback) and this exact slot was
        one of the candidates the resolver's OWN elimination logic
        considered physically plausible and still rejected -- see
        rejected_sids, returned directly from _try_deterministic_reconnect /
        _resolve_detection_identity. It is reset to 0 the moment this
        slot IS matched by any resolver mechanism. It is untouched --
        neither incremented nor reset -- on a frame where there is no
        detection to test it against at all (occlusion, a missed
        detector frame, etc.): that produces no resolver verdict, so it
        produces no evidence. There is no separate proximity lookup: the
        resolver's own elimination pool already IS the identity
        association, so the evidence lands on the correct persistent
        self.slots entry directly.

        There are exactly two legal outcomes for a provisional slot, and
        no third one:
          1. The resolver matches it (directly, or via any of its own
             mechanisms) -- streak resets, slot remains provisional
             until it either earns normal promotion or reaches its own
             exit.
          2. The resolver has genuinely evaluated and rejected this slot
             for resolver_exhausted_frames straight occurrences -- this
             method fires, and the slot is PERMANENTLY promoted
             (_promote_provisional_slot) using its own first-observed
             evidence. It stops being "provisional" the moment this
             runs, so it can never again be silently discarded while
             still unresolved, and it can never again be treated with
             provisional-grade laxity by anything downstream.

        Promotion here does not by itself declare the block gone --
        ordinary occlusion/retirement bookkeeping in
        _update_slot_lifecycle still runs immediately afterward, same
        as for any established slot. What changes is identity status,
        not presence status: from this point on the slot is a normal,
        permanent, non-provisional identity -- exactly as an ordinary
        newly-observed slot would have been -- so it is judged going
        forward by the same rules (including snapshot verification)
        that already protect every other established slot from being
        overwritten or reassigned."""
        s = self.slots[sid]
        if not s.get("provisional", False):
            return
        print(f"  [ProvisionalResolved] slot={sid}: resolver evaluated and rejected this "
              f"identity for {s['resolver_failed_streak']} consecutive occurrences "
              f"(limit={self.resolver_exhausted_frames}) -- permanently promoting to a "
              f"new stable slot (frame {frame_idx})")
        self._promote_provisional_slot(sid, frame_idx, terminal=False)

    def _handle_unmatched_detection(self, pos, box, ratio, frame_idx, seen_slots, seen_observations):
        """Handles a detection that matched no existing slot through any
        resolution mechanism -- fast association, the unified candidate
        reconnect (scored across every physically reachable slot,
        including same-frame splits), and rollback have ALL already run
        and failed by the time execution reaches here (see
        _resolve_detection_identity). First guards against re-registering
        a block that is still visible while genuinely leaving frame right
        after a real departure was already counted just now (a dedup
        "echo"), which is simply declined -- nothing else in this class
        ever looks an echo up by id, so no slot record is needed to
        "reject" it.

        [Architecture -- observation buffer, not an identity stage]
        Confirmed bug: a reconnect miss was treated as conclusive
        evidence of a new physical block, unconditionally, the instant
        it happened -- one bad frame (detector jitter, partial
        emergence, box instability, a momentary split) minted a
        permanent-looking slot id immediately. If the SAME physical
        block's very next detection then reconnected correctly through
        the normal path (a different position, a cleaner box), nothing
        ever retired the spuriously-born slot from the frame before --
        it just sat there as an ordinary provisional slot, drawn on
        screen, competing for future candidacy, following the exact
        same retirement timeline as any genuine slot, with a real
        chance of eventually accumulating enough coincidental evidence
        to be promoted and even counted. Over a long video with
        constant occlusion this produces exactly what it sounds like:
        dozens of slot ids for a handful of physical blocks.

        A reconnect miss is no longer, by itself, sufficient evidence
        of a new physical block. It first becomes (or renews) an entry
        in self._unknown_observations -- see _update_unknown_observation
        immediately below for the full design. Only a detection that
        keeps failing to match ANYTHING, consistently, for
        resolver_exhausted_frames consecutive frames, earns an actual
        slot id -- reusing that existing constant deliberately (see
        _update_unknown_observation) rather than inventing a second
        persistence threshold that means almost the same thing.

        A provisional slot, once it IS created, is still not counted as
        an arrival yet -- entered_count and the entry-corridor vote are
        deferred until it is actually promoted, via one of two paths:
          - _check_normal_promotion: sustained high-confidence visibility
            (reused thresholds -- min_high_ratio_frames / min_settling_frames)
          - terminal promotion inside _check_direct_exit / _check_drag_exit:
            sustained presence at the exit boundary itself, for blocks
            that never get a full mid-platform lifetime before departing
        Both paths funnel through _promote_provisional_slot, which votes
        and counts using this slot's OWN first-observed position/frame
        -- now the observation's first-seen position/frame, not
        wherever/whenever persistence happened to be confirmed (see
        _create_slot_from_observation).

        If a slot IS eventually created and nothing ever reclaims or
        promotes it, it simply ages out via the existing give-up/
        retirement logic in _update_slot_lifecycle (no_reappear_grace_frames)
        -- no new expiry mechanism needed there either."""
        if self._is_recent_departure(pos):
            # [DIAG -- identity audit] The only remaining gate in this
            # redesigned flow that can prevent a detection from becoming
            # its own identity without some mechanism having already
            # claimed it above. Logged explicitly so "why didn't this
            # detection get a new slot" always has an answer on record --
            # either a claim mechanism (see [DIAG:claim] above, in
            # _update_matched_slot_geometry) or this dedup gate, never
            # silence.
            print(f"    [DIAG:no_slot] frame={frame_idx} detection_pos="
                  f"({pos[0]:.0f},{pos[1]:.0f}) detection_box={tuple(round(v) for v in box)} "
                  f"gate=RecentDepartureDedup (within departure_dedup_dist_px="
                  f"{self.departure_dedup_dist_px:.0f}px of a departure recorded in the last "
                  f"{self.departure_dedup_window_frames}f) -- treated as an echo of an "
                  f"already-counted departure, no new slot created")
            return

        self._update_unknown_observation(pos, box, ratio, frame_idx, seen_slots, seen_observations)

    # ==================================================================
    # Observation Buffer
    # [Architecture -- observation buffer, not an identity stage] A
    # SEPARATE dict from self.slots, deliberately: an UnknownObservation
    # is not a slot, not a temp slot, not a weaker kind of slot. It has
    # no slot id, participates in NOTHING a slot participates in
    # (reconnect candidacy, the draw layer, lifecycle, exit, counting),
    # and exists purely to answer one narrow question -- "has this
    # not-yet-identified blob been recurring consistently, or was it a
    # one-off miss?" -- before the rest of the tracker ever finds out
    # it existed. Every existing identity mechanism (fast association,
    # the unified candidate reconnect, rollback) still runs FRESH, every
    # frame, on every detection, completely unaware this buffer exists
    # -- an observation being tracked here never blocks or delays a
    # genuine reconnect from succeeding the moment it can; it only
    # delays the FALLBACK action (minting a new identity) that used to
    # fire immediately and unconditionally on the very first miss.
    # ==================================================================

    def _update_unknown_observation(self, pos, box, ratio, frame_idx, seen_slots, seen_observations):
        """Matches this unmatched detection against existing
        observations using simple centroid distance -- reusing
        visible_match_dist_px, the same "close enough to be the same
        object frame to frame" tolerance Fast Association already uses
        for exactly this judgment (there just isn't a slot to attach it
        to yet). No IoU/motion/worker/prediction reasoning is
        duplicated here; that would be rebuilding the resolver a second
        time for no benefit -- the resolver already runs first, every
        frame, before a detection ever reaches this method at all.

        On a match: updates position/box, increments
        consecutive_frames_seen. On no match: starts a new observation.
        Either way, if consecutive_frames_seen has now reached
        resolver_exhausted_frames, this observation graduates to a real
        slot (_create_slot_from_observation) and is removed from the
        buffer. Reuses resolver_exhausted_frames deliberately rather
        than introducing a second, separately-tuned persistence
        constant that would mean almost the same thing ("how many
        consecutive frames of resolver failure before committing to a
        decision") -- one existing knob governs both "stop waiting on
        an existing provisional slot" and "stop waiting to decide this
        is a new one."

        Every observation touched this frame (matched, or freshly
        created) is added to seen_observations. _prune_unmatched_
        observations (called once, after the whole detection loop) then
        deletes every observation NOT in that set -- this is what
        implements "reconnect succeeds next frame -> observation simply
        isn't renewed -> pruned, no slot ever created" and "false
        detection -> never recurs -> pruned" without any special-case
        logic: not being re-observed this frame is already the correct
        signal for both."""
        matched_oid = None
        best_d = float("inf")
        for oid, obs in self._unknown_observations.items():
            d = dist(pos, obs["pos"])
            if d <= self.visible_match_dist_px and d < best_d:
                best_d, matched_oid = d, oid

        if matched_oid is not None:
            obs = self._unknown_observations[matched_oid]
            obs["pos"] = pos
            obs["box"] = box
            obs["ratio"] = ratio
            obs["last_seen_frame"] = frame_idx
            obs["consecutive_frames_seen"] += 1
            print(f"    [UnknownObservation] obs={matched_oid} re-matched at "
                  f"({pos[0]:.0f},{pos[1]:.0f}) dist={best_d:.0f}px -- "
                  f"consecutive_frames_seen={obs['consecutive_frames_seen']}/"
                  f"{self.resolver_exhausted_frames} (frame {frame_idx})")
        else:
            matched_oid = self._next_observation_id
            self._next_observation_id += 1
            self._unknown_observations[matched_oid] = {
                "pos": pos, "box": box, "ratio": ratio,
                # first_pos/first_seen_frame are immutable -- the true
                # arrival evidence, preserved for whenever (if ever)
                # this observation is promoted to a slot. pos/box above
                # are the current/latest geometry, updated on every
                # re-match.
                "first_pos": pos, "first_seen_frame": frame_idx,
                "last_seen_frame": frame_idx,
                "consecutive_frames_seen": 1,
            }
            obs = self._unknown_observations[matched_oid]
            print(f"    [UnknownObservation] obs={matched_oid} NEW at "
                  f"({pos[0]:.0f},{pos[1]:.0f}) -- fast association, recently-occluded "
                  f"ownership, unified reconnect, and rollback all failed this detection "
                  f"this frame; observing before deciding whether this is a new physical "
                  f"block (frame {frame_idx})")

        seen_observations.add(matched_oid)

        if obs["consecutive_frames_seen"] >= self.resolver_exhausted_frames:
            self._create_slot_from_observation(matched_oid, frame_idx, seen_slots)
            del self._unknown_observations[matched_oid]
            seen_observations.discard(matched_oid)

    def _prune_unmatched_observations(self, seen_observations, frame_idx):
        """Deletes every UnknownObservation not re-matched for more than
        no_reappear_grace_frames straight frames.

        [Fix -- new block never promoted, departs uncounted] Used to
        prune on ANY single unmatched frame, zero tolerance -- deleting
        the observation outright and forcing a brand new one (back to
        consecutive_frames_seen=1) the instant it next re-appeared.
        Confirmed directly from user reports across multiple videos: a
        genuinely new, real block sitting in frame can flicker in and
        out of detection for entirely ordinary reasons (this same
        codebase's own logs document 400+ evidence flip cycles for a
        single object, roughly one flip every 2 processed frames, for
        hundreds of frames straight -- see _update_slot_lifecycle's
        [Fix -- flicker-driven evidence loss] comment) -- and every
        established SLOT already has rich tolerance for exactly that
        (occlusion state, reconnect, no_reappear_grace_frames). An
        UnknownObservation, by contrast, is a brand-new block's ONLY
        path to ever becoming a countable slot at all -- and had NONE
        of that tolerance: one dropped detection frame before it ever
        reached resolver_exhausted_frames consecutive matches wiped its
        whole streak, and a block unlucky enough to flicker early
        enough, often enough, could recur indefinitely as one
        never-promoted temp id after another, cross the exit boundary,
        and depart having never been assigned a slot -- completely
        invisible to every counting mechanism, since all of them
        operate on self.slots, never on _unknown_observations. Reuses
        no_reappear_grace_frames rather than inventing a new constant --
        the exact same "how many missed frames still count as the same
        object having a bad moment" tolerance already trusted for
        established slots is the physically correct scale for this
        earlier, more fragile stage of the same object's life too.
        consecutive_frames_seen is deliberately NOT incremented on a
        merely-tolerated miss (see _update_unknown_observation) -- a
        missed frame pauses progress toward promotion, it does not
        fabricate false evidence of having been seen."""
        stale = []
        for oid, obs in self._unknown_observations.items():
            if oid in seen_observations:
                continue
            frames_missed = frame_idx - obs.get("last_seen_frame", frame_idx)
            if frames_missed > self.no_reappear_grace_frames:
                stale.append(oid)
            elif self.RECONNECT_DIAGNOSTICS_ENABLED:
                print(f"    [UnknownObservation] obs={oid} missed this frame but within "
                      f"grace ({frames_missed}f <= {self.no_reappear_grace_frames}f) -- "
                      f"progress preserved (consecutive_frames_seen="
                      f"{obs['consecutive_frames_seen']}), not pruned (frame {frame_idx})")
        for oid in stale:
            obs = self._unknown_observations.pop(oid)
            print(f"    [UnknownObservation] obs={oid} discarded -- not re-observed for "
                  f"{frame_idx - obs.get('last_seen_frame', frame_idx)}f, past the "
                  f"{self.no_reappear_grace_frames}f grace window (seen for "
                  f"{obs['consecutive_frames_seen']} consecutive frame(s), "
                  f"first at frame {obs['first_seen_frame']}, last at frame "
                  f"{obs['last_seen_frame']}) -- never became a slot (frame {frame_idx})")

    def _create_slot_from_observation(self, oid, frame_idx, seen_slots):
        """The ONE place left that creates a new slot id -- reached only
        after an UnknownObservation has persisted, consistently
        unmatched by every existing identity mechanism, for
        resolver_exhausted_frames straight frames.

        Uses the observation's OWN first_seen_frame/first_pos for the
        slot's first_seen_frame/established_pos -- the entry-corridor
        vote and entered_count (charged later, at promotion, by
        _promote_provisional_slot) must be attributed to where and when
        the block actually first appeared, not to wherever/whenever
        persistence happened to be confirmed several frames later. This
        is the exact same discipline _promote_provisional_slot already
        applies one step later (promotion time vs. current time); this
        just applies it one step earlier, at birth. Uses the
        observation's LATEST pos/box/ratio for the slot's actual
        current geometry, since that's genuinely where/what it looks
        like right now."""
        obs = self._unknown_observations[oid]
        new_sid = self._next_slot_id
        self._next_slot_id += 1
        self.slots[new_sid] = {
            "pos": obs["pos"], "box": obs["box"], "last_seen_frame": frame_idx,
            "state": "visible", "max_ratio_ever": obs["ratio"], "last_ratio": obs["ratio"],
            "counted": False,
            "occluded_by": {},
            "bind_start_pos": None, "bind_start_frame": None,
            "drag_confirmed": False, "entry_meaningful": False,
            "frames_since_seen": 0, "contact_frames": 0,
            "last_worker_ids": set(),
            "created_frame": frame_idx,
            "first_created_frame": frame_idx,
            "high_ratio_frames": 1 if obs["ratio"] >= self.min_ratio_ever_for_real_block else 0,
            "established_pos": obs["first_pos"],
            "velocity": (0.0, 0.0),
            "provisional": True,
            "first_seen_frame": obs["first_seen_frame"],
            "resolver_failed_streak": 0,
            # [Fix -- KeyError crash on same-frame reconnect to a
            # brand-new slot] This method adds new_sid to seen_slots
            # below WITHOUT ever routing through
            # _update_matched_slot_geometry -- so, unlike every other
            # path that claims a slot for the first time in a frame,
            # it never seeded _pre_frame_box/_pre_frame_pos/
            # _frame_claim_boxes. If a SECOND detection this exact same
            # frame then reconnects to this same-just-born slot (a
            # genuine, legitimate case -- e.g. two split fragments
            # where the second one satisfies the reconnect candidate
            # checks against the slot the first one just created),
            # _update_matched_slot_geometry sees sid already in
            # seen_slots (already_updated_this_frame=True) and tries to
            # append to s["_frame_claim_boxes"], which never existed --
            # KeyError, hard crash (confirmed directly from a user-
            # supplied traceback: slot=1 created at frame 4, a second
            # detection reconnected to it same_frame=True later that
            # same frame, and the process crashed on
            # s["_frame_claim_boxes"].append(box)). Seeding these three
            # fields here, exactly as the "first claim this frame"
            # branch of _update_matched_slot_geometry would have, makes
            # slot creation itself count as that first claim -- a
            # second same-frame detection now correctly falls into the
            # "already_updated_this_frame" MERGE path instead of
            # crashing.
            "_pre_frame_box": obs["box"],
            "_pre_frame_pos": obs["pos"],
            "_frame_claim_boxes": [obs["box"]],
        }
        seen_slots.add(new_sid)
        print(f"  slot={new_sid} PENDING (unclaimed by any existing identity) -- promoted "
              f"from UnknownObservation obs={oid} after {obs['consecutive_frames_seen']} "
              f"consecutive unmatched frames (first observed frame {obs['first_seen_frame']} "
              f"at ({obs['first_pos'][0]:.0f},{obs['first_pos'][1]:.0f}), now at "
              f"({obs['pos'][0]:.0f},{obs['pos'][1]:.0f})) -- awaiting reconnect, normal "
              f"promotion, or terminal exit confirmation (frame {frame_idx})")

    # ==================================================================
    # Worker Evidence
    # [Architecture -- evidence, not ownership] Workers do not own
    # slots. self.workers holds no back-reference to any slot at all --
    # there is nothing on a worker record that names which block(s) it
    # explains. The only place that relationship is recorded is on the
    # SLOT itself, in occluded_by: {wid: last_overlap_frame}. This is
    # deliberately a single source of truth -- "which slots does worker
    # W explain" is answered by scanning slots for W in their
    # occluded_by, not by maintaining a second, synchronized index that
    # could drift from the first.
    #
    # occluded_by is additive evidence, never exclusive custody: any
    # number of workers may simultaneously appear in it (a worker
    # occluding several blocks at once; two workers momentarily
    # overlapping the same slot during a handover), and no worker's
    # presence in it excludes any other worker from also being added,
    # to this slot or to any other. Establishing it happens inline in
    # _update_slot_lifecycle, the instant a slot goes unseen while a
    # live worker's box overlaps it (Phase 5), and it is refreshed
    # every frame that overlap continues. Clearing it happens ONLY
    # through _release_worker_binding, the instant a slot is matched
    # (visible) again -- every other subsystem that needs to end a
    # slot's occlusion evidence (Identity's reconnect/rollback/
    # merge-back, Exit's direct/drag exit, Lifecycle's retirement)
    # calls that method rather than writing slot['occluded_by']
    # directly.
    # ==================================================================

    def _release_worker_binding(self, sid):
        """The ONLY method in this class allowed to clear a slot's
        occluded_by evidence. Safe to call on a slot with no live
        evidence (no-op). Deliberately does NOT touch last_worker_ids --
        that field exists specifically to survive release (see its own
        definition at slot-creation time) so a brief same-frame
        visibility flicker, or a later exit-ledger log entry, can still
        identify which worker(s) were last associated with this slot
        even after vision has taken over."""
        s = self.slots.get(sid)
        if s is None:
            return
        s["occluded_by"] = {}

    def _primary_worker_id(self, s):
        """occluded_by is evidence, not ownership -- there is no single
        'owning' worker to look up. Callers that need ONE live worker
        record as a positional fallback (DragExit's stand-in position,
        an exit ledger entry, etc.) get the most-recently-corroborating
        worker: the one whose box overlapped this slot most recently.
        This is a read-only, derived convenience -- recomputed on every
        call, never stored, and never used to gate eligibility anywhere
        (see the worker-emergence check in _generate_reconnect_candidates,
        which tests every id in occluded_by, not just this one)."""
        occ = s.get("occluded_by")
        if not occ:
            return None
        return max(occ.items(), key=lambda kv: kv[1])[0]

    def _representative_worker_id(self, s):
        """Persisted-identity counterpart to _primary_worker_id, for
        logging and exit-ledger fields that want to name a worker even
        after occluded_by has already been cleared by release (see
        _release_worker_binding). last_worker_ids survives release by
        design; this just picks one representative id from it when a
        single value is needed (e.g. a print statement or a ledger
        dict), with no claim that it's more "correct" than any other
        id that was also in the set."""
        ids = s.get("last_worker_ids")
        return next(iter(ids), None) if ids else None

    def _match_worker(self, pos, frame_idx, max_dist=120):
        best_wid, best_d = None, float("inf")
        for wid, w in self.workers.items():
            if w["expired"]:
                continue
            d = dist(pos, w["pos"])
            if d < best_d:
                best_d, best_wid = d, wid
        if best_wid is not None and best_d <= max_dist:
            return best_wid
        return None

    def update_workers(self, worker_boxes, frame_idx):
        seen = set()
        for box in worker_boxes:
            pos = centroid(box)
            wid = self._match_worker(pos, frame_idx)
            if wid is None:
                wid = self._next_worker_id
                self._next_worker_id += 1
                self.workers[wid] = {
                    "pos": pos, "box": box, "last_seen_frame": frame_idx,
                    "expired": False, "pending_reveal": None,
                    # [Fix -- worker handoff / worker-id churn causing a
                    # double count] See the handoff_partners update loop
                    # below, right after this detection loop, for why
                    # this exists.
                    "handoff_partners": set(),
                    # No back-reference to any slot here -- see the
                    # Worker Evidence section banner. occluded_by on
                    # the slot is the only source of truth.
                }
            else:
                self.workers[wid]["pos"] = pos
                self.workers[wid]["box"] = box
                self.workers[wid]["last_seen_frame"] = frame_idx
            seen.add(wid)

        # [Fix -- worker handoff / worker-id churn causing a double
        # count] Two workers briefly occluding/crossing each other is
        # exactly the condition under which _match_worker (simple
        # nearest-distance matching, max_dist=120) is most likely to
        # swap or lose a worker's own tracked id -- a person tracker
        # reassigning a new id to the same physical person right as
        # they separate from the other worker. When that happens mid-
        # carry, the block's slot has occluded_by keyed to the OLD
        # (now stale/expired) worker id; the physical handoff was real,
        # but nothing recorded it. Recording, every frame, which worker
        # ids were ever physically close to which other worker ids --
        # independent of any slot, purely worker-to-worker -- lets the
        # occlusion-continuity check (is_continuation, below in
        # _update_slot_lifecycle) and the reconnect worker-emergence
        # check (_generate_reconnect_candidates) recognize "this new
        # worker id was, at some point, standing right next to the
        # worker who used to explain this slot" as legitimate handoff
        # evidence, the same physical reasoning the previously-working
        # codebase used in its own rollback path (handoff_evidence).
        # Confirmed directly from user report: a worker-id swap during
        # a brief mutual worker occlusion was resolved as a lost slot
        # instead of a continuing one -> new slot minted -> double
        # count.
        live_wids = [wid for wid, w in self.workers.items() if not w["expired"]]
        for i in range(len(live_wids)):
            a = live_wids[i]
            wa = self.workers[a]
            for b in live_wids[i + 1:]:
                wb = self.workers[b]
                if boxes_close(wa["box"], wb["box"], self.worker_bind_margin_px):
                    wa.setdefault("handoff_partners", set()).add(b)
                    wb.setdefault("handoff_partners", set()).add(a)

        for wid, w in self.workers.items():
            if wid not in seen and not w["expired"]:
                if frame_idx - w["last_seen_frame"] > 300:
                    w["expired"] = True
                    w["pending_reveal"] = None
                    # [Fix 1] Worker expiry ordering: expiry marks the
                    # worker record itself as stale, but it must NOT
                    # touch bound_slots / the slot's bound_worker here.
                    # _release_worker_binding is the only method allowed
                    # to sever that relationship (see Worker Binding
                    # section banner) -- severing it here instead would
                    # prevent _check_drag_exit (which still runs every
                    # frame the slot remains bound, using this worker's
                    # last known box/pos as a frozen fallback) from ever
                    # evaluating the accumulated contact_frames/drag
                    # evidence again, since it bails out immediately once
                    # bound_worker is None. Leaving the binding intact
                    # keeps giving DragExit first refusal every frame.
                    #
                    # [Fix -- terminal decision, updated] This USED to
                    # also keep the slot on the long
                    # max_bound_occlusion_frames give-up threshold
                    # indefinitely, and separately, a slot with
                    # drag_confirmed=True (a permanent historical flag)
                    # was entirely exempt from ordinary retirement --
                    # together, an expired worker with any past drag
                    # evidence orphaned its slot forever if
                    # _check_drag_exit's own positional gate (block/
                    # worker near the platform boundary) could never
                    # pass. Both of those have since been fixed
                    # (_update_slot_lifecycle now requires CURRENT
                    # credible occlusion for the long threshold, and no
                    # longer exempts drag_confirmed slots from retiring),
                    # so an orphaned slot like this now genuinely does
                    # resolve -- via DragExit if its positional evidence
                    # holds, otherwise clean retirement shortly after
                    # falling back to the short no_reappear_grace_frames
                    # window -- instead of waiting for the rest of the
                    # video.
                    #
                    # [Architecture -- evidence, not ownership] No cached
                    # back-reference exists to answer "which slots did
                    # this worker explain" -- occluded_by on the slot is
                    # the single source of truth, so this diagnostic-only
                    # scan queries it directly rather than maintaining a
                    # second, synchronizable index purely for a log line
                    # that fires once per worker's expiry.
                    still_explained = [sid for sid, s in self.slots.items()
                                       if s["state"] != "gone" and wid in s.get("occluded_by", {})]
                    if still_explained:
                        print(f"  WORKER EXPIRED: worker={wid} (last seen frame {w['last_seen_frame']}, "
                              f"now frame {frame_idx}) was still corroborating slot(s)={still_explained} "
                              f"with no reveal ever confirmed — those slots are now orphaned from live "
                              f"reveal-search and will resolve shortly via DragExit if their evidence is "
                              f"positionally plausible, otherwise via clean retirement")

    # ==================================================================
    # Fast Association
    # The cheap, high-confidence first check tried for every detection
    # before any of the heavier semantic-resolution mechanisms above
    # are even considered: is this simply the nearest already-visible
    # slot? [Visible]
    # ==================================================================

    def _fragment_centroid_ceiling(self):
        """[Fix -- ceiling that scales with a value that can itself be
        wrong] MAX_FRAGMENT_CENTROID_OFFSET_BLOCK_WIDTHS * block_size_
        estimate() alone isn't a safe ceiling -- block_size_estimate is
        itself a running EMA that can drift upward from the same kind
        of bad matches this ceiling exists to prevent, quietly loosening
        its own safety net over time. Confirmed directly from log
        evidence: a 210px jump (a completely different, fully-confident,
        ratio=1.000 object matched onto a slot via ordinary Fast
        Association) passed this ceiling anyway. Hard-capped at
        2 * visible_match_dist_px (160px) regardless of what the block-
        size estimate currently claims -- generous enough for a genuine
        offset fragment on ordinary footage, small enough that a
        completely different object several block-widths away can no
        longer sneak through just because the size estimate happened to
        be inflated that day."""
        return min(
            max(self._block_size_estimate() * self.MAX_FRAGMENT_CENTROID_OFFSET_BLOCK_WIDTHS,
                self.visible_match_dist_px),
            self.visible_match_dist_px * 2,
        )

    def _match_visible_slot(self, pos, box, seen_slots):
        """[Fix] Now excludes any slot already claimed by another
        detection earlier in this SAME frame (seen_slots). Previously
        this had no awareness of same-frame claims at all: if two
        genuinely distinct blocks were close enough together (e.g.
        slightly occluding each other -- still two separate boxes out of
        the tracker) that both landed within visible_match_dist_px of
        the same slot's position, the second detection would silently
        match that same already-claimed slot too, instead of getting its
        own identity. With seen_slots excluded here, that second
        detection now falls through to the heavier resolution chain
        (candidate reconnect / new-slot creation), which
        already correctly excludes seen_slots in every one of its own
        eligibility checks -- Fast Association was the one gap.

        [Architecture -- slot state estimates the block, not the last
        detection] Confirmed bug: this used to test centroid distance
        (dist(pos, s["pos"])) against the slot's stored position -- but
        s["pos"] used to collapse to whichever ONE fragment had the
        highest ratio whenever a block was split (worker occlusion,
        detector fragmentation), silently discarding every other
        concurrent fragment's geometry. A fragment's own centroid is,
        by construction, offset from the whole block's centroid -- so
        when the discarded fragment was the one that reappeared alone
        on a later frame, its centroid could easily fall outside
        visible_match_dist_px of the surviving fragment's centroid, even
        though it never stopped being physically part of the same
        object. Ratio is noisy enough that which fragment is "primary"
        can flip frame to frame, so this wasn't a one-time transition
        bug -- it could recur every single frame a block stayed split.

        s["box"] is now a genuine running ESTIMATE of the physical
        block's extent (see _update_matched_slot_geometry), grown by
        union whenever what's currently visible looks like only part of
        the block, and reset to a fresh direct observation whenever a
        whole-block-sized detection confirms it. Testing box-to-box
        proximity (boxes_close, edge-to-edge gap) against that estimate
        -- rather than centroid-to-centroid distance against a single
        collapsed point -- is what correctly recognizes a fragment as
        still belonging to the slot regardless of which side it's on:
        a fragment's own box always touches or overlaps the estimated
        extent it's part of, even though its centroid does not sit near
        the extent's own centroid. Reuses visible_match_dist_px as the
        edge-gap tolerance -- same existing constant, same intended
        meaning ("close enough to be the same object, frame to frame,
        with no real movement expected"), just applied through the
        geometrically correct test for this case.

        [Fix -- edge-gap test with no centroid ceiling at all] boxes_close
        alone has no upper bound on centroid distance: a naturally tall
        or wide box (this is real, valid geometry for some camera
        positions -- not a bug, not drift) can have an edge sitting only
        a few pixels from a totally unrelated detection's edge, even
        though the two centroids are hundreds of pixels apart. Confirmed
        directly from log evidence: a genuine, repeatedly-confirmed
        149x295 whole-block box matched a completely different,
        physically unrelated 143x44 detection 280px away, twice, purely
        because the tall box's bottom edge sat 4px from the other
        detection's top edge. The fix is not to abandon edge-gap
        semantics (still needed for the legitimate offset-fragment case
        this method's own docstring describes above) -- it's to also
        require the centroid distance stay within a bounded multiple of
        one block's own size, since a genuine fragment's centroid offset
        from the whole block's center is physically limited by the
        block's own extent, not unbounded."""
        best_visible, best_visible_d = None, float("inf")
        for sid, s in self.slots.items():
            if s["counted"] or s["state"] == "gone":
                continue
            if sid in seen_slots:
                continue
            if s["state"] == "visible":
                d = dist(pos, s["pos"])
                if d > self.STATIONARY_SELF_RECLAIM_DIST_PX and self._matches_snapshot(box, pos, s.get("snapshot_boxes", [])):
                    continue
                if d > self._fragment_centroid_ceiling():
                    continue
                if boxes_close(box, s["box"], self.visible_match_dist_px) and d < best_visible_d:
                    best_visible_d, best_visible = d, sid
        return best_visible

    def _match_recently_occluded_slot(self, pos, box, seen_slots):
        """[Architecture -- ownership invariant, not a candidate-pool
        filter, not an age/graduation threshold] If this detection is
        still geometrically consistent with ANY existing slot's own
        estimated extent -- prediction still valid -- that slot already
        owns it: reconnect must not even run for this detection.
        Structurally identical to _match_visible_slot -- same
        visible_match_dist_px tolerance, same box-consistency test (see
        that method's own docstring for why box proximity against the
        slot's estimated extent replaced centroid distance against a
        single collapsed point), same "closest wins, already-claimed-
        this-frame excluded" logic -- the only difference is
        state == "occluded" instead of "visible", since a slot that's
        still literally visible is already caught by Fast Association
        itself and never reaches this method at all.

        Deliberately has NO age, tracked-frame-count, or "graduation"
        requirement of any kind. An earlier version of this gated
        eligibility on a slot having survived STABLE_GRADUATION_FRAMES
        tracked frames first -- which left a brand-new, one-frame-old
        Temp completely unprotected the instant it missed a single
        frame, exactly the failure mode this whole mechanism exists to
        close. The actual invariant is simpler and doesn't admit
        exceptions: something either already has an identity or it
        doesn't. A detection consistent with an existing slot's own
        estimated extent IS that slot, whether the slot was created one
        frame ago or a thousand.

        This exists specifically for the "just missed a frame or two"
        case: a slot's detection reappears essentially where it was, and
        that alone is enough to reclaim it, full stop -- no elimination
        tiers, no scoring, no competing candidate ever gets a chance to
        be considered. A slot that has genuinely moved a real distance
        (e.g. picked up and carried by a worker) is handled by the
        ordinary resolver instead -- Tier B2's emergence-corridor
        requirement (touching the CURRENT worker's own box) already
        protects that case on its own merits, requiring BOTH physical
        emergence from occlusion AND the correct worker, not distance
        alone and not worker-overlap alone. This method deliberately
        does not try to cover that case (a wide-radius match here would
        reintroduce exactly the vague, distance-only reasoning this
        whole architecture was built to remove).

        [Architectural fix -- snapshot check never wired in here] This
        is the single highest-risk spot in the whole file for the
        stationary-neighbor swap bug: it's a pure box-proximity
        ownership shortcut, with NO ranking, NO worker corroboration,
        NO competing-candidate consideration at all -- the first
        occluded slot whose estimated extent is close enough simply
        wins, unconditionally. snapshot_boxes was captured for exactly
        this moment (every OTHER currently-visible block's box, at the
        instant THIS slot went occluded) and was never once consulted
        here. Two blocks sitting next to each other -- one occluded,
        one stationary and untouched -- are, by construction, within
        each other's boxes_close tolerance; without this check, the
        stationary neighbor's own ordinary re-detection could get
        silently claimed as "the occluded slot reappearing," swapping
        both blocks' identities. Checked first, before the geometric
        test: a detection matching a recorded snapshot box is
        definitionally a different, already-known block, not this
        slot's own hidden content, regardless of how close it sits.

        [Fix -- ceiling mismatched with this method's own stated
        intent] This method's docstring above has always said "reappears
        essentially where it was" -- but the actual ceiling used was
        _fragment_centroid_ceiling() (160px), a constant built for a
        completely different physical question: how far apart a same-
        frame detector-split fragment of ONE block may legitimately land
        from that block's center (can be a real block-width or more,
        e.g. when a worker's body splits one block into two boxes on
        either side). "Reappeared essentially where it was" and "is a
        plausible sibling fragment of a block being split apart right
        now" are not the same claim, and 160px is nowhere near
        "essentially where it was" for the former. Confirmed directly
        from log evidence (20260310225553131): a low-confidence,
        low-ratio detection (ratio=0.146) landed 2px from a DIFFERENT,
        already-visible slot's own immediately-prior detection, yet got
        claimed by an unrelated occluded slot 143px away purely because
        143 < 160 -- the same shape of bug independently confirmed with
        slot=7/slot=5 (~160px, right at this same ceiling). Using
        STATIONARY_SELF_RECLAIM_DIST_PX here instead -- the constant
        this class already uses elsewhere for exactly "is this genuinely
        the same, essentially-stationary object still right here" --
        aligns the ceiling with what this method actually claims to do.
        A slot that has moved a real distance while occluded still isn't
        abandoned: it's exactly what the ordinary resolver chain
        (_generate_reconnect_candidates, with its own worker-emergence
        and ranking logic) exists to handle instead, per this method's
        own docstring above."""
        best_sid, best_d = None, float("inf")
        for sid, s in self.slots.items():
            if s["counted"] or s["state"] == "gone":
                continue
            if sid in seen_slots:
                continue
            if s["state"] == "occluded":
                d = dist(pos, s["pos"])
                # [Note] The snapshot check that used to sit here
                # (reject if d > STATIONARY_SELF_RECLAIM_DIST_PX and
                # this detection matches a recorded neighbor snapshot)
                # is now subsumed by the flat ceiling immediately below:
                # anything past STATIONARY_SELF_RECLAIM_DIST_PX is
                # rejected outright regardless of snapshot match, so the
                # snapshot-specific carve-out can never fire. Left out
                # rather than kept as dead code.
                if d > self.STATIONARY_SELF_RECLAIM_DIST_PX:
                    continue
                if boxes_close(box, s["box"], self.visible_match_dist_px) and d < best_d:
                    best_d, best_sid = d, sid
        return best_sid

    def _update_matched_slot_geometry(self, sid, pos, box, ratio, frame_idx, seen_slots, mechanism=None):
        """Applies bookkeeping for a detection that resolved to an existing
        slot identity (via Fast Association or any Semantic Identity
        Resolution mechanism).

        [Architecture -- slot state estimates the block, not the last
        detection] Confirmed bug, fully replaced: this used to let only
        the first (highest-ratio) fragment to reach a slot in a frame
        write its geometry -- every other same-frame fragment was
        "consumed" purely to prevent a duplicate slot, its own position
        discarded outright. The slot's stored pos/box therefore
        collapsed to whichever ONE fragment happened to have the higher
        ratio that specific frame -- a noisy, frame-to-frame-unstable
        choice, not a meaningful one. When the OTHER fragment (the one
        whose position was thrown away) was the one that survived alone
        on a later frame, it could fail Fast Association and even the
        reconnect prediction-region gate against a position that was
        never really "where the block is," just "where the winning
        fragment happened to be" -- producing exactly the failure this
        redesign closes: a still-owned fragment falling all the way
        through to a new slot.

        Every claim this frame -- not just the first -- now contributes
        to a genuine running ESTIMATE of the physical block's extent:
          - On the first claim this frame, snapshot the estimate as it
            stood before any of this frame's claims (pre_box/pre_pos)
            and start a fresh per-frame claim list.
          - After every claim, recompute this frame's own union (every
            box that has claimed this slot so far this frame) and check
            _looks_like_whole_block on it:
              * WHOLE -- this frame's observation(s), together, are
                convincing evidence of the block's full extent. RESET
                the estimate to this frame's union outright, discarding
                whatever came before -- a fresh full view supersedes
                stale partial memory. This is what lets a slot cleanly
                return to normal once fragments recombine or the worker
                moves away.
              * PARTIAL -- only part of the block is visible this frame
                (a single fragment, or fragments that together still
                don't look whole). MERGE this frame's union into the
                PRE-frame estimate rather than overwriting it -- the far
                side of the block, last confirmed on an earlier frame,
                is preserved rather than discarded, exactly what lets a
                lone surviving fragment keep matching Fast Association
                against the slot's still-correct (wider) extent instead
                of a stale single-fragment point.
        This directly implements "representation changes, ownership does
        not": whole block, left+right fragments, left fragment alone, or
        right fragment alone are all just different inputs to the same
        estimate-update rule -- none of them is treated as a special
        case, and none of them requires touching Fast Association's own
        matching logic (see _match_visible_slot) beyond testing against
        whatever the estimate currently is.

        [DIAG -- identity audit] `mechanism` is purely forensic -- it does
        not affect any decision here. Every call to this method is one
        "claim" event (a detection was attached to sid, by some named
        mechanism), and every claim is logged unconditionally -- whether
        or not it actually moved the slot's geometry -- so a full,
        frame-by-frame identity trace can be reconstructed after one run
        without inferring anything from secondary effects."""
        s = self.slots[sid]
        already_updated_this_frame = sid in seen_slots
        prev_pos = s.get("pos")
        prev_box = s.get("box")
        updated_geometry = not already_updated_this_frame

        if not already_updated_this_frame:
            s["_pre_frame_box"] = prev_box
            s["_pre_frame_pos"] = prev_pos
            s["_frame_claim_boxes"] = [box]
        else:
            s["_frame_claim_boxes"].append(box)

        frame_union = union_boxes(s["_frame_claim_boxes"])

        # [Fix -- oversized raw detection accepted outright, swallowing
        # a second, distinct object] _looks_like_whole_block only checks
        # a LOWER bound (is this box big enough to plausibly be a whole
        # block) -- there has never been an upper bound anywhere in this
        # pipeline. Confirmed directly from log evidence: a single raw
        # detection box, (200,162,714,525) = 514x363px, roughly 5-6x a
        # normal single block's area, sailed straight through as
        # RESET(whole) because it easily cleared the lower-bound area
        # test with plenty of room to spare -- the test was never built
        # to catch "too big," only "too small." This is almost certainly
        # the detector momentarily fusing two adjacent, physically
        # distinct blocks into one bounding box (common when blocks sit
        # close together) -- ten frames later the detector correctly
        # separated them again, but by then whatever had been briefly
        # swallowed into the oversized box had no identity of its own
        # left to reclaim: it just restarted as a fresh, unclaimed
        # observation and was promoted into a brand-new, unnecessary
        # slot. None of the existing MAX_PARTIAL_ESTIMATE_* caps catch
        # this either -- they only bound how big a MULTI-FRAME
        # accumulated union may grow, not a single frame's own raw
        # detection that's already oversized on arrival, before any
        # merging has even happened.
        #
        # Past MAX_PARTIAL_ESTIMATE_AREA_FRACTION (the same "how much
        # bigger than one block is still plausibly one block" ceiling
        # already trusted elsewhere in this class), a raw detection this
        # large is no longer treated as reliable geometry for THIS slot
        # at all -- the existing position/box is kept unchanged rather
        # than snapping to what's very likely two objects' combined
        # extent. The match itself still stands (this slot's ownership
        # of this frame isn't in question, last_seen_frame etc. still
        # update normally below) -- only the geometry is protected from
        # being corrupted by a detection that shouldn't be trusted at
        # face value.
        block_size_for_sanity = self._block_size_estimate()
        expected_area_for_sanity = block_size_for_sanity ** 2 if block_size_for_sanity > 0 else 0
        oversized_likely_fused = (
            expected_area_for_sanity > 0
            and box_area(frame_union) > expected_area_for_sanity * self.MAX_PARTIAL_ESTIMATE_AREA_FRACTION
        )

        if oversized_likely_fused:
            # [Fix -- see oversized_freeze_max_frames's own docstring in
            # __init__ for the full mechanism] Track how many
            # CONSECUTIVE frames this slot has now been frozen under
            # this branch. Only increments while the condition holds
            # (reset to 0 the instant a frame is NOT oversized, in
            # either branch below) -- so this is genuinely "how long has
            # the freeze been continuously in effect," not a lifetime
            # counter. Past oversized_freeze_max_frames, trust this
            # frame's own direct observation instead of continuing to
            # protect a reference that's now more likely stale than the
            # thing it's protecting against -- the same "prefer this
            # frame's real geometry over an aging historical estimate"
            # philosophy the elongation/area caps below already apply
            # to the ordinary MERGE path, just extended to cover this
            # branch too.
            oversized_streak = s.get("_oversized_streak_frames", 0) + 1
            s["_oversized_streak_frames"] = oversized_streak
            if oversized_streak > self.oversized_freeze_max_frames:
                new_box = frame_union
                estimate_mode = "RESET(stale-oversized-freeze-expired)"
                s["_oversized_streak_frames"] = 0
                print(f"  [DIAG:geometry-guard] slot={sid} raw detection area="
                      f"{box_area(frame_union)}px^2 still exceeds "
                      f"{self.MAX_PARTIAL_ESTIMATE_AREA_FRACTION}x expected single-block area "
                      f"({expected_area_for_sanity:.0f}px^2), but has now been frozen for "
                      f"{oversized_streak} consecutive frames (> "
                      f"{self.oversized_freeze_max_frames}) -- trusting this frame's own direct "
                      f"observation over an increasingly stale reference (frame {frame_idx})")
            else:
                new_box = s.get("box", frame_union)
                estimate_mode = "SKIP(oversized-likely-multi-object)"
                print(f"  [DIAG:geometry-guard] slot={sid} raw detection area="
                      f"{box_area(frame_union)}px^2 exceeds {self.MAX_PARTIAL_ESTIMATE_AREA_FRACTION}x "
                      f"expected single-block area ({expected_area_for_sanity:.0f}px^2) -- likely two "
                      f"objects fused by the detector, keeping existing geometry unchanged this frame "
                      f"(frame {frame_idx}, frozen streak={oversized_streak}/"
                      f"{self.oversized_freeze_max_frames})")
        elif self._looks_like_whole_block(frame_union):
            new_box = frame_union
            estimate_mode = "RESET(whole)"
            s["_partial_streak_frames"] = 0
            s["_oversized_streak_frames"] = 0
        else:
            s["_oversized_streak_frames"] = 0
            base = s.get("_pre_frame_box") or frame_union
            merged = union_boxes([base, frame_union])
            # [Architectural fix -- unbounded estimate growth] The old
            # codebase's geometry update simply overwrote pos/box with
            # the latest single detection every frame -- always centered
            # on something real, at the cost of losing a fragment's
            # position when a block stayed split (the bug the union-
            # estimate redesign above was built to fix). But nothing
            # bounds HOW FAR that union may grow: `base` here can
            # already be a many-frame accumulated union from a long run
            # of consecutive MERGE(partial) frames, and this line unions
            # it with yet another partial observation, with no ceiling.
            # Across an extended partial-occlusion stretch (a worker's
            # own body covering part of a block for many seconds while
            # carrying it, entirely ordinary) the estimate can grow
            # monotonically -- it only ever resets on a genuine
            # whole-block-sized detection, which may not arrive again
            # for a long time -- eventually ballooning well past the
            # physical size of one block and dragging the centroid off
            # the real object and into a neighbor's territory. Confirmed
            # as the likely mechanism behind "slots aren't centered,
            # keep moving and assign themselves to other blocks" --
            # every affected slot's `pos` is a centroid of an
            # ever-growing box, not a real observation.
            #
            # This caps the union at MAX_PARTIAL_ESTIMATE_AREA_FRACTION
            # times the expected single-block area. Past that ceiling,
            # the accumulated historical `base` is treated as too stale
            # to keep trusting -- new_box falls back to frame_union (this
            # frame's OWN direct observation(s) only), the same
            # "always centered on something real" guarantee the old
            # codebase had, while still preserving the union redesign's
            # actual fix (a same-frame split's second fragment is never
            # discarded, since frame_union already covers every claim
            # made THIS frame -- only the cross-frame historical memory
            # gets bounded).
            block_size = self._block_size_estimate()
            expected_area = (block_size ** 2) if block_size > 0 else 0
            cap_area = expected_area * self.MAX_PARTIAL_ESTIMATE_AREA_FRACTION
            merged_w = merged[2] - merged[0]
            merged_h = merged[3] - merged[1]
            # [Fix -- elongated estimate satisfying boxes_close at huge
            # centroid distances] The area cap above bounds how BIG the
            # estimate may grow, but not how STRETCHED it may become --
            # a tall, narrow box (or a wide, short one) can stay well
            # under the area cap while still spanning hundreds of pixels
            # in one dimension. boxes_close (used by _match_visible_slot,
            # _match_recently_occluded_slot, and every reconnect path)
            # tests EDGE-to-edge gap, not centroid distance -- so a
            # stretched box's far edge can sit close enough to a totally
            # different, unrelated detection's edge to pass, even though
            # the two centroids are hundreds of pixels apart. Confirmed
            # directly from log evidence: slot=1 oscillated between
            # (948,524) [a tall 149x294 box] and (726,697) [a short,
            # wide, physically unrelated 143x44 box] 280px away, twice,
            # via ordinary mechanism=Visible Fast Association -- the
            # tall box's own bottom edge sat only 4px from the other
            # detection's top edge. Capped at MAX_PARTIAL_ESTIMATE_
            # ELONGATION_FRACTION times the block's own expected single-
            # dimension size, in EITHER width or height -- past that,
            # same fallback as the area cap: trust only this frame's own
            # direct observation instead of the accumulated, now
            # too-stretched-to-trust historical estimate.
            elongation_cap = block_size * self.MAX_PARTIAL_ESTIMATE_ELONGATION_FRACTION
            too_elongated = block_size > 0 and (merged_w > elongation_cap or merged_h > elongation_cap)
            # [Fix -- estimate frozen, permanently offset from the real
            # detection, for hundreds of frames] The area and elongation
            # caps above only catch a union that grew too BIG or too
            # STRETCHED -- neither catches a union that's simply the
            # WRONG shape for _looks_like_whole_block's own calibration
            # (e.g. block_size_estimate itself running high) while
            # staying comfortably under both caps every single frame.
            # Confirmed directly from log evidence: a completely stable,
            # unchanging, correctly-detected block (ratio ~0.79-0.81,
            # same box dimensions, same position) was judged "not whole"
            # and stuck in MERGE(partial) for 200+ CONSECUTIVE frames --
            # detection_pos never moved from (630,268), but slot_pos
            # stayed frozen at (568,268) the entire time, a permanent
            # 62px offset from the actual, correct, currently-visible
            # detection, because _pre_frame_box was set once, long ago,
            # and never refreshed. This is exactly the drifted-off-
            # center circle marker reported directly by the user, and
            # very likely part of why nearby slots start losing/winning
            # matching contests against each other -- the registered
            # position simply isn't where the block actually is,
            # sometimes for a large fraction of the video. However many
            # consecutive frames this slot has gone without a genuine
            # RESET, once that streak exceeds MAX_PARTIAL_ESTIMATE_
            # STALE_FRAMES, the historical base is no longer trusted at
            # all regardless of area/elongation -- same fallback as
            # those two caps, forced here purely by elapsed time instead
            # of size.
            s["_partial_streak_frames"] = s.get("_partial_streak_frames", 0) + 1
            too_stale = s["_partial_streak_frames"] > self.MAX_PARTIAL_ESTIMATE_STALE_FRAMES
            size_capped = expected_area > 0 and (box_area(merged) > cap_area or too_elongated)
            if size_capped or too_stale:
                new_box = frame_union
                estimate_mode = "RESET(capped-stale-partial)"
                s["_partial_streak_frames"] = 0
            else:
                new_box = merged
                estimate_mode = "MERGE(partial)"
        new_pos = centroid(new_box)

        # [DIAG] Distance is always reported relative to the slot's
        # estimate as it stood before this frame's claims began -- "how
        # far did the estimate itself just move" (RESET) or "how far did
        # it just grow/shift to accommodate this fragment" (MERGE).
        pre_pos = s.get("_pre_frame_pos")
        moved = dist(new_pos, pre_pos) if pre_pos is not None else None
        moved_str = f"{moved:.0f}px" if moved is not None else "n/a(first_claim)"
        before_str = f"({pre_pos[0]:.0f},{pre_pos[1]:.0f})" if pre_pos is not None else "None"
        after_str = f"({new_pos[0]:.0f},{new_pos[1]:.0f})"
        print(f"    [DIAG:claim] frame={frame_idx} slot={sid} mechanism={mechanism} "
              f"updated_geometry={updated_geometry} estimate_mode={estimate_mode} "
              f"detection_pos=({pos[0]:.0f},{pos[1]:.0f}) "
              f"detection_box={tuple(round(v) for v in box)} "
              f"slot_pos_before={before_str} slot_pos_after={after_str} "
              f"distance_from_prior_estimate={moved_str} ratio={ratio:.3f} "
              f"occluded_by={sorted(s.get('occluded_by', {}).keys())}")
        if moved is not None and moved > self.worker_bind_margin_px:
            print(f"    [DIAG:jump] slot={sid} estimate jump: "
                  f"({pre_pos[0]:.0f},{pre_pos[1]:.0f}) -> "
                  f"({new_pos[0]:.0f},{new_pos[1]:.0f}) = {moved:.0f}px "
                  f"(frame {frame_idx}, mechanism={mechanism}, estimate_mode={estimate_mode}, "
                  f"ratio={ratio:.3f}, occluded_by={sorted(s.get('occluded_by', {}).keys())})")
        # Velocity EMA (pixels/frame), computed from the pre-frame
        # estimate against the just-updated one -- this is what State 2
        # ("freeze last position/velocity") and the deterministic
        # reconnect's predicted-emergence check both rely on while the
        # slot is hidden. Smoothed rather than replaced outright so a
        # single noisy jump doesn't distort the prediction used for the
        # next several occluded frames. Recomputed on every claim this
        # frame (not gated to the first) so a same-frame MERGE is
        # reflected immediately for any downstream same-frame consumer
        # (e.g. _accumulate_drag_evidence, called right after this) --
        # the minor cost is that a multi-fragment frame applies the EMA
        # smoothing more than once within that single frame, converging
        # to the frame's overall movement slightly faster than a
        # strict once-per-frame design would; negligible next to the
        # bug this replaces.
        if pre_pos is not None:
            dt = max(frame_idx - s.get("last_seen_frame", frame_idx), 1)
            new_vx = (new_pos[0] - pre_pos[0]) / dt
            new_vy = (new_pos[1] - pre_pos[1]) / dt
            old_vx, old_vy = s.get("velocity", (0.0, 0.0))
            s["velocity"] = (0.6 * old_vx + 0.4 * new_vx, 0.6 * old_vy + 0.4 * new_vy)
        s["last_update_mechanism"] = mechanism
        s["pos"] = new_pos
        s["box"] = new_box
        s["last_ratio"] = ratio
        if updated_geometry:
            if ratio >= self.min_ratio_ever_for_real_block:
                s["high_ratio_frames"] = s.get("high_ratio_frames", 0) + 1
                self._update_block_size_estimate(box)
        s["last_seen_frame"] = frame_idx
        s["state"] = "visible"
        s["max_ratio_ever"] = max(s["max_ratio_ever"], ratio)
        seen_slots.add(sid)

    # ==================================================================
    # Lifecycle / Debug Utilities
    # Purely observational -- these never influence a decision, they
    # only make an already-made decision (or lack thereof) visible in
    # the logs.
    # ==================================================================

    def _log_stuck_slot(self, sid, s, frame_idx):
        """Periodic diagnostic for a slot with live worker evidence that
        has gone unresolved (neither confirmed departed nor retired) for
        a long stretch. Fires every 300 frames of absence so a
        long-running stall is visible in the logs without flooding them
        every frame."""
        primary_wid = self._primary_worker_id(s)
        w = self.workers.get(primary_wid) if primary_wid is not None else None
        w_status = "MISSING" if w is None else ("EXPIRED" if w["expired"] else "ALIVE")
        w_pending = None if w is None else w.get("pending_reveal")
        print(f"  [stuck-check] frame={frame_idx} slot={sid} unresolved for "
              f"{s['frames_since_seen']}f | state={s['state']} "
              f"occluded_by={sorted(s.get('occluded_by', {}).keys())} primary={primary_wid} "
              f"({w_status}) drag_confirmed={s['drag_confirmed']} "
              f"contact_frames={s.get('contact_frames',0)} "
              f"high_ratio_frames={s.get('high_ratio_frames',0)} pending_reveal={w_pending} "
              f"last_update_mechanism={s.get('last_update_mechanism')}")

    # ==================================================================
    # Exit Subsystem -- Decision Paths & Count Commit
    # Owns the actual mutation of loaded_count / _recent_departures /
    # _recent_worker_loads -- no other subsystem commits a count.
    # The two ways a slot can leave the platform and be counted:
    #   [DirectExit] seen crossing the platform outline while visible
    #                (bound_worker is None -- see ownership boundary
    #                in _check_direct_exit's docstring)
    #   [DragExit]   worker-bound, occluded, with confirmed drag evidence
    #                (called from Lifecycle's per-slot pass, but the
    #                commit itself lives here, not there)
    # A [Rollback:Full] merge-back check runs immediately after a
    # [DragExit] commits, in case this same physical block had already
    # split into a separate slot earlier (see Semantic Identity
    # Resolution). This is the "broader" rollback check, distinct from
    # the tight, per-detection [Rollback:Tight] check tried during
    # identity resolution.
    # ==================================================================

    def _check_direct_exit(self, sid, pos, box, frame_idx, seen_slots):
        """[DirectExit] path: a block seen crossing the platform outline
        while still visible (no occlusion involved). Requires a short
        confirmation window (exit_grace_frames) to avoid platform-box
        jitter being mistaken for a real departure. Returns True if this
        call committed the block as LOADED. Called from Phase 4 (Evaluate
        exits) with the slot's own current pos/box, after Phase 3 (Bind
        workers) has finalized this frame's bindings -- see the pipeline
        banner on update_blocks for why that ordering matters.

        Ownership boundary: evaluates any slot that isn't currently in
        GENUINE, LIVE worker custody. DirectExit and DragExit have
        mutually exclusive authority over a slot's departure --
            worker actively holding it right now -> worker-carry custody -> DragExit
            no worker, or worker stale/elsewhere -> independently observed -> DirectExit
        A worker standing at or holding a block right at the platform
        boundary can otherwise make this method's own boundary-crossing
        test fire on pure detection jitter around a position that never
        actually progresses; each false commit gets caught by
        Rollback:Tight, which resets the slot back to a clean-looking
        baseline (bound_worker, created_frame) and unintentionally re-arms
        this exact same check to fire again once the settling clock
        re-elapses -- forever, for as long as the worker stands there.
        Excluding a slot in genuine live custody removes that failure
        mode entirely rather than narrowing the window it can occur in.

        [Fix] Confirmed bug: this used to key off bound_worker's mere
        EXISTENCE rather than whether that binding still represents
        anyone actually holding the block. A worker can go stale
        (expired -- no longer detected at all) or simply walk away from
        this exact block without the binding ever being released (only
        _release_worker_binding may sever it, and nothing else does so
        just because the worker moved on). Once that happened, this
        method's own guard permanently blocked DirectExit for that slot
        -- even while the block stayed genuinely VISIBLE and TRACKED,
        clearly crossing the platform outline (e.g. mostly outside it,
        still poking in slightly) -- forcing departure detection onto
        DragExit instead, which only fires once the block goes UNSEEN
        for exit_grace_frames. A block that's still being tracked every
        frame as it exits never satisfies that, so it sails past the
        boundary uncounted until it eventually leaves the camera's view
        entirely and DragExit's slower, indirect (worker-displacement
        fallback) evidence catches up much later -- if it ever does.
        Now the guard only blocks DirectExit when at least one worker in
        occluded_by is BOTH still live (not expired) AND its own
        current box is actually touching this block's box right now --
        i.e. someone is demonstrably holding it this instant. A stale or
        absent hold no longer suppresses DirectExit."""
        s = self.slots[sid]
        worker_actively_holding = False
        for wid in s.get("occluded_by", {}):
            w = self.workers.get(wid)
            if w is not None and not w.get("expired") and boxes_close(w["box"], box, self.worker_bind_margin_px):
                worker_actively_holding = True
                break
        if worker_actively_holding:
            s["pending_direct_exit"] = False
            return False
        # [Terminal promotion] A provisional slot -- a late-appearing
        # genuine block revealed from behind a worker, another identical
        # block, or a barrel -- may reach the exit boundary before it can
        # ever satisfy normal promotion's full-lifetime bars (settling
        # time since first seen, confirmed drag displacement): both of
        # those assume a mid-platform lifetime this slot never got to
        # have. Dropped for the provisional branch; high_ratio_frames
        # stays a hard requirement regardless, since it's the one bar
        # that actually distinguishes a genuine, confidently-detected
        # block from single-frame detector noise skimming the exit.
        provisional = s.get("provisional", False)
        if provisional:
            direct_exit_ready = (
                not s["counted"]
                and s.get("high_ratio_frames", 0) >= self.min_high_ratio_frames
                and self._past_exit_boundary(pos, margin=self.direct_exit_margin_px)
            )
        else:
            direct_exit_ready = (
                not s["counted"]
                and s.get("high_ratio_frames", 0) >= self.min_high_ratio_frames
                and frame_idx - s.get("created_frame", frame_idx) >= self.min_settling_frames
                and dist(pos, s.get("established_pos", pos)) >= self.min_drag_displacement_px
                and self._past_exit_boundary(pos, margin=self.direct_exit_margin_px)
            )
        if direct_exit_ready:
            if not s.get("pending_direct_exit", False):
                # Same confirmation-window pattern already used for the
                # worker-drag path (pending_load), and reused as-is for
                # the provisional/terminal case above rather than
                # inventing a second one: a single instant of being past
                # the boundary is not enough, since platform-box jitter
                # or a worker briefly binding to a static edge block can
                # satisfy this for one frame without a real departure.
                # Require it to hold for exit_grace_frames straight before
                # committing.
                s["pending_direct_exit"] = True
                s["pending_direct_exit_frame"] = frame_idx
                print(f"  PENDING {'TERMINAL ' if provisional else ''}DIRECT EXIT: slot={sid} "
                      f"seen past the platform outline while visible, starting "
                      f"{self.exit_grace_frames}f confirmation window (frame {frame_idx}) "
                      f"before counting as loaded")
            elif frame_idx - s["pending_direct_exit_frame"] >= self.exit_grace_frames:
                if provisional:
                    # Arrival is synthesized FIRST, from the slot's own
                    # first-observed evidence -- see _promote_provisional_slot
                    # for why arrival and departure stay two distinct
                    # events even though both are decided this frame.
                    self._promote_provisional_slot(sid, frame_idx, terminal=True)
                s["counted"] = True
                s["state"] = "gone"
                self.loaded_count += 1
                self._recent_departures.append((frame_idx, pos))
                # Register in the same rollback ledger used by the
                # worker-drag path, so that if this block genuinely
                # reappears (i.e. this was a false-positive commit),
                # the existing rollback safety net can undo the count
                # instead of the reappearance spawning a brand-new slot.
                committed_worker_id = self._primary_worker_id(s)
                self._recent_worker_loads.append({
                    "sid": sid,
                    "frame": frame_idx,
                    "worker_id": committed_worker_id,
                    "block_pos": pos,
                    "block_box": box,
                    "snapshot_boxes": s.get("snapshot_boxes", []),
                })
                print(f"  [DirectExit{':Terminal' if provisional else ''}] LOADED: slot={sid} directly "
                      f"seen crossing the platform outline (confirmed after {self.exit_grace_frames}f, "
                      f"no occlusion involved) -> TOTAL={self.loaded_count}")
                # No longer purely defensive: the relaxed ownership guard
                # above can now let DirectExit commit while worker
                # evidence is still present (a stale/expired or
                # no-longer-adjacent worker relationship that just
                # wasn't actively holding this block). Release it here
                # so the worker record(s) are freed for future evidence
                # instead of permanently pointing at a slot that's now
                # gone.
                if s.get("occluded_by"):
                    self._release_worker_binding(sid)
                # [Fix 5] DirectExit symmetry: reuse the exact same
                # merge-back reconciliation DragExit already runs after
                # its own commit, in case this same physical block had
                # already split into a separate slot earlier.
                # committed_worker_id captured BEFORE _release_worker_binding
                # above, so the same-worker exemption inside
                # _check_prior_split can still recognize a sibling fragment
                # slot that this same worker is (or was) also occluding.
                self._check_prior_split(sid, box, s.get("snapshot_boxes", []), frame_idx, seen_slots,
                                         verbose=True, committed_worker_id=committed_worker_id)
                return True
        else:
            s["pending_direct_exit"] = False
        return False

    def _check_predicted_exit_continuation(self, sid, frame_idx, seen_slots):
        """[Predicted-exit continuation] Called only for a slot that is
        NOT matched this frame and already has real, observed exit
        evidence in progress (pending_direct_exit -- set exclusively by
        _check_direct_exit off an actual visible boundary crossing).
        This is not a prediction-only counting path: a slot with no
        prior observed evidence never reaches here at all (see the call
        site in _update_slot_lifecycle), so nothing is ever counted from
        extrapolation alone.

        What this DOES do is let an already-started confirmation window
        continue while the slot is hidden, instead of either committing
        immediately on occlusion (too eager -- a prediction can be
        wrong) or freezing the window indefinitely the moment occlusion
        starts (too passive -- exactly the "wait forever" failure mode
        this exists to close). Each frame the slot stays unseen, its
        frozen last position is extrapolated by its own frozen velocity
        to a predicted current position:
          - if that prediction is no longer past the exit boundary, the
            evidence has weakened -- cancel the pending window and let
            the slot fall back to ordinary occlusion/drag-exit/
            retirement handling, exactly as if it had never started one.
          - if the prediction is still past the boundary, keep waiting
            up to the SAME exit_grace_frames confirmation window a live
            crossing requires (no separate, longer timeout -- occlusion
            does not earn extra patience beyond what a visible crossing
            already gets).
          - once that window elapses with the prediction still past the
            boundary, commit -- using the exact same ledger bookkeeping
            (_recent_departures / _recent_worker_loads) every other exit
            path uses, so rollback remains the sole, unmodified recovery
            mechanism if this block genuinely reappears.

        Returns True if this call committed the block as LOADED."""
        s = self.slots[sid]
        elapsed_frames = frame_idx - s.get("last_seen_frame", frame_idx)
        vx, vy = s.get("velocity", (0.0, 0.0))
        pred_pos = (s["pos"][0] + vx * elapsed_frames, s["pos"][1] + vy * elapsed_frames)

        if not self._past_exit_boundary(pred_pos, margin=self.direct_exit_margin_px):
            print(f"  [PredictedExit] slot={sid} predicted position "
                  f"({pred_pos[0]:.0f},{pred_pos[1]:.0f}) after {elapsed_frames}f hidden is no "
                  f"longer past the exit boundary -- cancelling the in-progress confirmation "
                  f"window, this slot gets no credit from prediction alone (frame {frame_idx})")
            s["pending_direct_exit"] = False
            return False

        if frame_idx - s["pending_direct_exit_frame"] < self.exit_grace_frames:
            return False

        provisional = s.get("provisional", False)
        if provisional:
            self._promote_provisional_slot(sid, frame_idx, terminal=True)
        s["counted"] = True
        s["state"] = "gone"
        self.loaded_count += 1
        self._recent_departures.append((frame_idx, pred_pos))
        committed_worker_id = self._representative_worker_id(s)
        self._recent_worker_loads.append({
            "sid": sid,
            "frame": frame_idx,
            "worker_id": committed_worker_id,
            "block_pos": pred_pos,
            "block_box": s["box"],
            "snapshot_boxes": s.get("snapshot_boxes", []),
        })
        print(f"  [DirectExit:PredictedContinuation{':Terminal' if provisional else ''}] LOADED: "
              f"slot={sid} had real observed exit evidence before occlusion, and its predicted "
              f"position stayed past the exit boundary through the full "
              f"{self.exit_grace_frames}f confirmation window while hidden -> "
              f"TOTAL={self.loaded_count}")
        if s.get("occluded_by"):
            self._release_worker_binding(sid)
        self._check_prior_split(sid, s["box"], s.get("snapshot_boxes", []), frame_idx, seen_slots,
                                 verbose=True, committed_worker_id=committed_worker_id)
        return True

    def _accumulate_drag_evidence(self, sid, pos, box):
        """While a slot carries worker evidence and is visible this
        frame, accumulate the evidence a later [DragExit] commit depends
        on: confirmed displacement from the bind-start position, and
        sustained contact with any corroborating worker's box."""
        s = self.slots[sid]
        occ = s.get("occluded_by")
        if not occ:
            return
        drag_dist = dist(pos, s["bind_start_pos"])
        if drag_dist >= self.min_drag_displacement_px:
            s["drag_confirmed"] = True
        for wid in occ:
            w = self.workers.get(wid)
            if w is not None and boxes_close(w["box"], box, self.worker_bind_margin_px):
                s["contact_frames"] = s.get("contact_frames", 0) + 1
                break

    def _drag_exit_evidence(self, sid, frame_idx):
        """[Fix 2] Single shared source of truth for "does this slot have
        genuine drag-to-exit evidence right now" -- used identically by
        the live _check_drag_exit path and by end-of-video finalization,
        so the two can never diverge on what counts as evidence. Returns
        (ready, dragging_evidence, worker_or_None):
          ready             -- enough high-ratio history, settling time,
                                and sustained worker contact to even
                                consider a drag-exit for this slot
          dragging_evidence -- the block's OWN confirmed displacement,
                                OR the worker's own displacement as a
                                fallback for when the block became fully
                                occluded before drag_confirmed could latch
        Does not mutate any state -- pure evaluation only.

        [Fix -- evidence must not depend on live binding status] Used to
        hard-return (False, False, None) the instant occlusion evidence
        was empty, discarding ready/drag_confirmed/contact_frames -- all
        pure s.get(...) reads with no dependency on live evidence --
        purely because no worker happened to be attached at this exact
        instant. Under the visibility-driven architecture a slot's
        evidence is released the moment it's matched visible and only
        re-created on its next occlusion transition, so "currently no
        live evidence" is a routine, frequent state for a slot with a
        long, genuine drag history behind it -- not evidence of
        anything. drag_confirmed is documented elsewhere in this class
        as "a PERMANENT historical flag... never reset"; this function
        was contradicting that by making its visibility conditional on
        occluded_by. ready and the drag_confirmed half of
        dragging_evidence are now computed unconditionally from the
        slot's own persisted fields. Only the worker-DISPLACEMENT half
        of dragging_evidence genuinely needs a worker record -- for that
        it falls back to last_worker_ids (unlike occluded_by, never
        cleared by release) so a momentary release doesn't blind it to
        a worker still actually in self.workers (even if since expired
        -- expiry only means undetected, not that its last real position
        was wrong)."""
        s = self.slots[sid]
        wid = self._primary_worker_id(s)
        if wid is None:
            wid = self._representative_worker_id(s)
        w = self.workers.get(wid) if wid is not None else None

        if s.get("provisional", False):
            # [Redesign -- evidence per exit path] DirectExit and DragExit
            # don't have symmetric evidence available. A directly-seen
            # crossing naturally produces high-ratio frames (it's clearly
            # visible by definition). A worker-carried block that's
            # grabbed almost immediately and stays mostly occluded for
            # its whole life naturally produces contact_frames instead --
            # real, repeated physical contact with the worker -- and may
            # never clear a ratio-confidence floor at all. Confirmed case:
            # a genuine block with contact_frames=11 (>= min_sustained_
            # contact_frames=8, solid evidence of real carry) but
            # high_ratio_frames=1, permanently unable to promote under a
            # ratio-only floor once its worker expired and no further
            # detection could ever arrive -- structurally unreachable, not
            # just slow. Either signal, on its own, is real evidence a
            # genuine block is present; requiring specifically
            # high_ratio_frames was requiring evidence this exit path
            # can't reliably produce. dragging_evidence and boundary
            # proximity below still gate the actual commit, so this
            # relaxation alone still can't commit anything by itself.
            #
            # [Root Cause C -- minimal targeted fix] Confirmed via direct
            # log evidence (20260312103845210, slot=8/slot=15): a
            # stationary, chronically low-ratio artifact near the
            # platform's own exit boundary (peak ratio 0.214, NEVER once
            # approaching min_ratio_ever_for_real_block=0.35 in its
            # entire life) can still satisfy the contact_frames leg alone
            # if a worker happens to walk past it, and gets wrongly
            # terminal-promoted and counted. The distinguishing evidence
            # between this and the genuine case Bug 2 was built for
            # (slot=3, 20260310225553131: high_ratio_frames=1,
            # contact_frames=11) is not contact_frames -- both have
            # plenty -- it's that the genuine block was clearly visible
            # at least ONCE, and the stationary artifact never was, not
            # even for a single frame. Requiring high_ratio_frames >= 1
            # as an additional floor keeps the OR-relaxation exactly as
            # useful for the case it was built for (slot=3 already has
            # 1) while closing off the chronically-never-visible case,
            # with no new constant, no new state, no architecture change
            # -- just one more condition on the existing evidence field.
            ever_clearly_visible = s.get("high_ratio_frames", 0) >= 1
            ready = ever_clearly_visible and (
                s.get("high_ratio_frames", 0) >= self.min_high_ratio_frames
                or s.get("contact_frames", 0) >= self.min_sustained_contact_frames
            )
        else:
            ready = (
                s.get("high_ratio_frames", 0) >= self.min_high_ratio_frames
                and frame_idx - s.get("created_frame", frame_idx) >= self.min_settling_frames
                and s.get("contact_frames", 0) >= self.min_sustained_contact_frames
            )

        bind_start_pos = s.get("bind_start_pos")
        worker_drag_dist = (
            dist(w["pos"], bind_start_pos) if (w is not None and bind_start_pos is not None) else 0.0
        )
        dragging_evidence = s.get("drag_confirmed", False) or worker_drag_dist >= self.min_drag_displacement_px
        return ready, dragging_evidence, w

    def _check_drag_exit(self, sid, frame_idx, seen_slots):
        """[DragExit] path (Exit subsystem): evaluates and, once
        confirmed, commits a worker-carried departure for a slot that is
        not currently matched this frame. Mirrors _check_direct_exit's
        pending/confirm/commit pattern for the worker-carry evidence
        branch (occluded_by non-empty). Requires: a live worker still
        bound, enough high-ratio history and settling time, sustained
        contact, and genuine drag evidence (the block's OWN confirmed
        displacement, or the worker's own displacement as a fallback for
        when the block became fully occluded before drag_confirmed could
        latch) held continuously for pending_load_confirm_frames after
        the block stopped being seen. Returns True if this call
        committed the block as LOADED. Owns the actual count mutation
        (loaded_count, _recent_departures, _recent_worker_loads) for this
        branch -- Lifecycle calls this but never mutates those itself."""
        s = self.slots[sid]
        # [Fix -- evidence must not depend on live binding status] Used
        # to do its own separate "if bound_worker is None: return False"
        # lookup here, discarding _drag_exit_evidence's more robust
        # worker reference (which already falls back to last_worker_id)
        # via an unused `_w`. A slot with a long, genuine drag history
        # can be legitimately unbound at any given instant under the
        # visibility-driven architecture (release happens the moment a
        # block is matched visible, independent of whether this method
        # happens to be evaluating it right then) -- that's a routine
        # state, not evidence of anything. Call _drag_exit_evidence
        # first and use ITS worker reference throughout instead.
        ready, dragging_evidence, w = self._drag_exit_evidence(sid, frame_idx)
        if not ready:
            return False
        if w is None:
            return False

        # [Fix] Confirmed bug: this used to unconditionally do
        # `s["contact_frames"] += 1` right here, every single time this
        # method runs. But this method is only ever called (from
        # _update_slot_lifecycle) for slots NOT matched this frame --
        # i.e. slots that are, by definition, not currently touching
        # anything. That silently redefined "contact_frames" as "frames
        # spent hidden while bound to a worker" instead of its actual,
        # documented meaning everywhere else in this class (genuine
        # frames of the block touching the worker's box -- see
        # _accumulate_drag_evidence, the ONLY place that should be
        # incrementing this, gated on boxes_close). The effect: a
        # worker who bound to a slot, touched it once, then walked away
        # to handle a completely different, unrelated block elsewhere
        # (its own separate slot) would still silently rack up
        # "contact_frames" on the ORIGINAL slot purely from elapsed
        # hidden time -- fast-tracking it past min_sustained_contact_frames
        # (the readiness gate below) and past LONG_ESTABLISHED_CONTACT_
        # MULTIPLIER's hard veto in _validate_reconnect_continuity with
        # zero genuine evidence behind either. Combined with dragging_evidence's
        # worker-displacement fallback (how far the WORKER has moved,
        # not the block), this let one worker's unrelated trip across
        # the platform to pick up a genuinely different block also
        # falsely confirm a DragExit on the original, untouched slot --
        # a real double count with no actual second departure behind it.
        # contact_frames is now read-only here; nothing in this method
        # writes it.

        if not (dragging_evidence and s["frames_since_seen"] >= self.exit_grace_frames):
            return False

        # [Fix] Confirmed bug -- the actual root cause behind slot=10's
        # repeated commit/rollback churn and the ID handoff to a
        # genuinely new arriving block: DragExit had NO positional check
        # at all. It commits purely from displacement (block's own drag,
        # or the worker's own movement as a fallback) plus the block
        # going unseen -- it never asks "was this block anywhere NEAR
        # the platform's outline when it disappeared?" DirectExit, by
        # contrast, only ever fires once a detection is observed past
        # the actual boundary (_past_exit_boundary). Without an
        # equivalent check here, a block that's simply occluded at a
        # busy INTERIOR staging/handoff spot -- far from any edge, just
        # a place workers hand blocks off to each other or stage them --
        # satisfies "moved >= min_drag_displacement_px, then went
        # unseen" trivially, and gets falsely marked departed. That
        # false ledger entry (block_pos/block_box anchored to that same
        # busy interior spot) then sits waiting for "a reappearance" --
        # and because that spot is a through-traffic chokepoint, the
        # NEXT block to pass through it (often a genuinely different,
        # newly-arriving one) satisfies Rollback:Tight's proximity+timing
        # check and gets silently absorbed into the stale identity
        # instead of getting its own. This is a real positional
        # plausibility gap, not just a rollback-matching gap -- fixing
        # only the rollback side (entry-corridor exclusion) can't help
        # when the false departure shouldn't have been recorded in the
        # first place. Reuses the same loose exit_margin_px already
        # defined for exactly this "generously counts near-the-edge
        # positions" purpose (see _past_exit_boundary), rather than
        # inventing a new threshold -- appropriate here since, unlike
        # DirectExit, we're inferring the crossing rather than observing
        # it directly, so the check has to be generous, not exact.
        # [Fix] Confirmed bug: this only ever tested the BLOCK's own
        # frozen position -- but once a block goes fully occluded, it
        # stops getting updated at all, while the WORKER carrying it
        # often keeps being independently tracked for a while longer (a
        # person detector is generally more robust than the object
        # detector for something now fully hidden behind a body). The
        # result: a block picked up well inside the platform, whose own
        # last-seen position is nowhere near the edge, could go on to be
        # genuinely carried the rest of the way out and off-camera --
        # confirmed by real drag evidence -- and still never pass this
        # gate, because the only position ever tested was frozen from
        # the moment it disappeared, not wherever the worker (and the
        # block still in their hands) actually ended up. Now accepted if
        # EITHER the block's own last position OR its carrying worker's
        # own last known position (even if that worker has since
        # expired -- expiry only means undetected, not that its last
        # real position was wrong) is near the platform outline.
        block_past_boundary = self._past_exit_boundary(s["pos"], margin=self.exit_margin_px)
        worker_past_boundary = self._past_exit_boundary(w["pos"], margin=self.exit_margin_px)
        if not (block_past_boundary or worker_past_boundary):
            if s.get("pending_load", False):
                print(f"  [DragExit] slot={sid} worker={self._representative_worker_id(s)} drag evidence present "
                      f"but neither the block's last known position ({s['pos'][0]:.0f},{s['pos'][1]:.0f}) "
                      f"nor its worker's last known position ({w['pos'][0]:.0f},{w['pos'][1]:.0f}) is "
                      f"near the platform outline -- looks like an interior occlusion (busy staging "
                      f"spot), not a real departure; cancelling pending load instead of committing")
                s["pending_load"] = False
            return False

        if not s.get("pending_load", False):
            s["pending_load"] = True
            s["pending_load_frame"] = frame_idx
            print(f"  PENDING LOAD: slot={sid} worker={self._representative_worker_id(s)} drag evidence "
                  f"present, starting {self.pending_load_confirm_frames}f confirmation "
                  f"window (frame {frame_idx}) — slot and worker lock stay intact so "
                  f"reassociation can still cancel this if the block reappears")
            return False

        if frame_idx - s["pending_load_frame"] < self.pending_load_confirm_frames:
            return False

        provisional = s.get("provisional", False)
        if provisional:
            # Arrival is synthesized FIRST, from the slot's own
            # first-observed evidence -- see _promote_provisional_slot for
            # why arrival and departure stay two distinct events even
            # though both are decided this frame.
            self._promote_provisional_slot(sid, frame_idx, terminal=True)
        s["counted"] = True
        s["state"] = "gone"
        self.loaded_count += 1
        self._recent_departures.append((frame_idx, s["pos"]))
        committed_worker_id = self._representative_worker_id(s)
        self._recent_worker_loads.append({
            "sid": sid,
            "frame": frame_idx,
            "worker_id": committed_worker_id,
            "block_pos": s["pos"],
            "block_box": s["box"],
            "snapshot_boxes": s.get("snapshot_boxes", []),
        })
        print(f"  [DragExit{':Terminal' if provisional else ''}] LOADED: slot={sid} "
              f"worker={self._representative_worker_id(s)} genuine drag evidence confirmed after "
              f"{self.pending_load_confirm_frames}f window with no reappearance, "
              f"block absent {s['frames_since_seen']} frames -> TOTAL={self.loaded_count}")
        self._release_worker_binding(sid)
        self._check_prior_split(sid, s["box"], s.get("snapshot_boxes", []), frame_idx, seen_slots,
                                 verbose=True, committed_worker_id=committed_worker_id)
        return True

    # ==================================================================
    # Lifecycle Subsystem -- Presence Tracking & Retirement
    # Owns exactly two things: occlusion/presence bookkeeping for slots
    # not matched this frame, and retiring (never counting) a slot that
    # gives up with no drag evidence. Calls Exit subsystem's
    # _check_drag_exit as an explicit step rather than committing counts
    # itself -- see the section banner above.
    # ==================================================================

    def _apply_terminal_exit_policy(self, sid, frame_idx, seen_slots):
        """[Policy -- terminal resolution for waiting slots, NOT a bug
        fix] Called only after ALL of the following are already true:
        waiting has ended (give_up_threshold exceeded in
        _update_slot_lifecycle), no credible occlusion remains
        (genuinely_occluded is False), _check_drag_exit already had its
        full, unmodified, positionally-gated chance to commit this exact
        frame and declined, and no reconnect occurred. At that point
        there is no remaining evidence-based mechanism left to explain
        this slot's continued existence.

        This is a deliberate recall-over-precision policy choice, not an
        objectively-correct default: a slot with genuine drag evidence
        that reaches this terminal point with no further evidence is
        resolved as LOADED rather than silently discarded as GONE. The
        alternative (retiring uncounted) is equally defensible and was
        this codebase's prior behavior -- this method exists because the
        counting policy has been chosen to favor catching real departed
        blocks whose worker's tracking simply lapsed before reaching the
        boundary, accepting the tradeoff that some of these commits will
        be wrong, in exchange for _try_rollback_match (unmodified) as
        the safety net: it already scans _recent_worker_loads by sid/
        block_pos/block_box regardless of which mechanism populated that
        ledger, so a slot resolved here that then genuinely reappears
        gets its count reversed exactly the same way a wrongly-committed
        DragExit would. This method deliberately does NOT touch
        _check_drag_exit's own positional requirement for its normal,
        fast, high-confidence path -- see that method's own [Fix]
        comment for why that check must stay exactly as it is.

        [Fix -- eligibility tightened] Used to require only bound_worker
        is not None -- ANY slot that ever had a worker relationship,
        including one that never accumulated real evidence of an actual
        pickup (e.g. a worker merely walked adjacent to it once and the
        binding never went anywhere). That was too broad: "had custody
        at some point" isn't the same claim as "there is real evidence
        this block was actually dragged". Eligibility now reuses
        _drag_exit_evidence's dragging_evidence signal -- the block's
        OWN confirmed displacement, or the worker's own displacement as
        a fallback for when the block became fully occluded before
        drag_confirmed could latch -- the same underlying evidence
        _check_drag_exit itself requires. No new evidence model was
        introduced -- this is the same helper DragExit and end-of-video
        finalization already both trust as their single shared source of
        truth for what counts as a real drag.

        Deliberately does NOT also require _drag_exit_evidence's `ready`
        flag, unlike _check_drag_exit. `ready` encodes LIVE-commit
        timing requirements (enough high-ratio history, settling time
        elapsed, sustained contact_frames) that exist specifically to
        gate a decision being made RIGHT NOW while the slot might still
        be visible or about to reappear. TerminalPolicy only ever runs
        after DragExit has already had its full, repeated chance and the
        waiting period has already expired -- it exists precisely for
        slots whose evidence never satisfied those live timing
        requirements before time ran out. Requiring `ready` here would
        make TerminalPolicy structurally unreachable for exactly the
        slots it's meant to catch, recreating the same "can never reach
        a terminal decision" failure mode this whole policy exists to
        close.

        A slot with no worker relationship at all, or one that never
        accumulated genuine drag evidence, is NOT covered by this policy
        -- it continues to retire uncounted, unchanged.

        Returns True if this call committed the block as LOADED."""
        s = self.slots[sid]
        if s["counted"]:
            return False
        _ready, dragging_evidence, _w = self._drag_exit_evidence(sid, frame_idx)
        if not dragging_evidence:
            return False

        provisional = s.get("provisional", False)
        if provisional:
            self._promote_provisional_slot(sid, frame_idx, terminal=True)
        s["counted"] = True
        s["state"] = "gone"
        self.loaded_count += 1
        self._recent_departures.append((frame_idx, s["pos"]))
        committed_worker_id = self._representative_worker_id(s)
        self._recent_worker_loads.append({
            "sid": sid,
            "frame": frame_idx,
            "worker_id": committed_worker_id,
            "block_pos": s["pos"],
            "block_box": s["box"],
            "snapshot_boxes": s.get("snapshot_boxes", []),
        })
        print(f"  [TerminalPolicy{':Terminal' if provisional else ''}] LOADED: slot={sid} "
              f"worker={self._representative_worker_id(s)} waiting ended with no credible occlusion, no "
              f"reconnect, and DirectExit/DragExit already declined this frame -- resolved as "
              f"LOADED per counting policy (recall over precision; rollback remains active if "
              f"this block reappears) -> TOTAL={self.loaded_count}")
        self._release_worker_binding(sid)
        self._check_prior_split(sid, s["box"], s.get("snapshot_boxes", []), frame_idx, seen_slots,
                                 verbose=True, committed_worker_id=committed_worker_id)
        return True

    def _update_slot_lifecycle(self, frame_idx, worker_boxes, other_block_boxes, seen_slots):
        """End-of-frame pass over every slot NOT freshly matched this
        frame (Lifecycle subsystem). Owns presence/occlusion state, and
        ensures every slot that has gone unseen past its give-up
        threshold reaches a terminal outcome -- no slot may remain in
        waiting indefinitely. That invariant (the lifecycle FIX) is
        deliberately kept separate from what the terminal outcome
        actually is (a counting POLICY):

          0. [Fix -- exit policy #5] Checked FIRST, before anything else
             in this per-slot pass: a slot whose DirectExit confirmation
             window was already in progress (pending_direct_exit) when it
             went occluded commits immediately, on the evidence already
             gathered -- _check_direct_exit itself only runs for slots
             matched THIS frame, so without this check such a slot would
             be permanently orphaned, its confirmation window frozen
             forever, silently falling back to the much slower (and
             possibly evidence-less) DragExit path instead.
          1. The existing, unmodified _check_drag_exit already had its
             full chance to commit this exact frame (called below as
             its own step, same relationship _check_direct_exit has
             with Phase 4 of update_blocks) -- positional evidence
             requirement fully intact, untouched.
          2. If it didn't fire, _apply_terminal_exit_policy gets one
             explicit, separately-named chance to resolve it as LOADED
             under this tracker's chosen recall-over-precision counting
             policy -- but only for a slot with genuine drag evidence
             (the same (ready, dragging_evidence) signal _drag_exit_evidence
             already gives _check_drag_exit itself, not merely having
             had a worker relationship at some point) -- see that
             method's own docstring; this is a deliberate choice, not a
             bug fix, and _try_rollback_match (unmodified) remains the
             safety net if the block reappears afterward.
          3. Otherwise (no genuine drag evidence, or the policy above
             still declines), the slot retires uncounted.

        [zombie-guard] (fixes confirmed bug #2): coincidental overlap
        with a stale, frozen slot box is only trusted as genuine
        occlusion -- and allowed to reset the give-up clock -- within
        ABSOLUTE_MAX_HIDDEN_SEC of true elapsed time since the slot was
        last an actual detection match. Past that ceiling, the give-up
        clock runs regardless of what else happens to overlap the slot's
        stale box, so a dead slot can no longer survive indefinitely by
        coincidence.

        [Fix -- terminal decision for confirmed/waiting slots] The
        extended (max_bound_occlusion_frames) give-up grace period now
        requires genuinely credible occlusion -- occluded_now (physical
        proximity RIGHT NOW) AND occlusion_still_credible (still within
        ABSOLUTE_MAX_HIDDEN_SEC of true elapsed time) together, the same
        combined test this function already trusts to label a slot
        "occluded" in the first place -- not merely "this slot has a
        bound_worker field set" (a historical relationship from bind
        time that nothing else re-verifies), and not proximity alone
        (which the zombie-guard above has already decided not to trust
        past ABSOLUTE_MAX_HIDDEN_SEC). The moment genuine occlusion stops
        holding, the slot falls back to the same short
        no_reappear_grace_frames window any ordinary slot gets, so a
        "stuck red circle" whose worker walked away resolves promptly --
        via genuine drag-exit evidence (_check_drag_exit, called once,
        unconditionally, at the top of this same per-slot pass -- see
        below) if it exists, or clean retirement (state -> "gone") if it
        doesn't. That single call is the one and only place drag exits
        are decided each frame; the retirement branch does not
        re-evaluate it -- if an exit were possible, it would already
        have committed there. See the give_up_threshold computation
        below for the actual change."""
        for sid, s in self.slots.items():
            if s["counted"] or s["state"] == "gone":
                continue
            if sid in seen_slots:
                s["frames_since_seen"] = 0
                if s.get("provisional", False):
                    # Claimed again this frame by the reconnect chain --
                    # reset the resolver-failure streak. This is a
                    # resolver-outcome signal, not a timer: it only
                    # resets on an actual successful claim.
                    s["resolver_failed_streak"] = 0
                continue

            # [Redesign -- predicted-exit continuation, not prediction-
            # only counting] A slot whose DirectExit confirmation window
            # (pending_direct_exit) was already in progress -- i.e. it
            # was DIRECTLY OBSERVED past the platform boundary on its
            # last visible frame, real exit evidence, not a guess -- and
            # then went occluded before that short window could complete
            # must not be abandoned to the much slower DragExit path.
            # But it must also not be counted from prediction alone: the
            # observed evidence only entitles it to CONTINUE its already-
            # started confirmation window while hidden, using its own
            # frozen velocity to extrapolate a predicted position each
            # frame. Only once that predicted position is still past the
            # exit boundary after the SAME exit_grace_frames window used
            # for a live crossing does this commit -- and if the
            # prediction ever drifts back inside the boundary first, the
            # window is cancelled and the slot falls through to ordinary
            # occlusion/lifecycle handling below, exactly like any slot
            # with no exit evidence at all.
            if s.get("pending_direct_exit", False) and not s["counted"]:
                if self._check_predicted_exit_continuation(sid, frame_idx, seen_slots):
                    continue
                # Falls through deliberately (no `continue`): the window
                # may still be open (waiting on exit_grace_frames) or was
                # just cancelled this frame (prediction moved back inside
                # the boundary) -- either way, ordinary occlusion/drag-
                # exit/retirement bookkeeping below still needs to run
                # for this slot this frame.

            # [Fix -- terminal decision for provisional identities]
            # resolver_failed_streak is NOT touched here beyond the
            # reset above. Being unseen this frame (occluded, missed by
            # the detector, genuinely gone -- doesn't matter which) is
            # not, by itself, resolver-failure evidence: it only means
            # nothing was tested. The streak advances in exactly one
            # place -- the main detection loop in update_blocks, at the
            # moment a real detection has been evaluated by the full
            # resolver chain and this exact slot was one of the
            # candidates the resolver's own elimination/validation logic
            # considered and rejected (see rejected_sids, returned
            # directly from _resolve_via_candidates /
            # _resolve_detection_identity). That keeps the evidence tied
            # to genuine resolver outcomes only -- never to elapsed time,
            # visibility, occlusion, movement, contact, or overlap ratio.

            # [Architecture -- evidence, not ownership] Worker identity
            # plays no role while a block is visible; this whole section
            # is therefore only ever reached for a slot that has already
            # gone unseen. Every non-expired worker whose box currently
            # overlaps this slot's frozen box is corroborating evidence
            # that its disappearance is consistent with occlusion by
            # that worker -- nothing more is checked, and nothing more
            # is needed. Unlike ownership, there is no exclusivity here
            # in either direction: a worker already corroborating one
            # slot is not excluded from also corroborating a second,
            # different slot (a single worker can occlude several
            # distinct blocks at once -- both hands, an armload), and a
            # slot already corroborated by one worker is not prevented
            # from ALSO being corroborated by a second worker in the
            # same frame (two workers momentarily overlapping the same
            # slot during a hand-off). occluded_by simply accumulates
            # whichever workers are genuinely, physically overlapping
            # this slot's box right now; it never decides which one, if
            # any, a later reappearing detection actually is -- that is
            # entirely _generate_reconnect_candidates' job (worker-
            # emergence is one more required check there, testing every
            # id in occluded_by, not a single privileged one), and it
            # still resolves genuine ambiguity via the FIFO tie-break
            # rather than guessing which specific worker explains it.
            had_occluded_by_before = bool(s.get("occluded_by"))
            overlapping_wids = [
                wid for wid, w in self.workers.items()
                if not w["expired"] and boxes_close(w["box"], s["box"], self.occlusion_margin_px)
            ]

            occluded_now = False
            worker_overlap_now = bool(overlapping_wids)
            if worker_overlap_now:
                occluded_now = True
            elif not had_occluded_by_before:
                # Never had worker evidence, and no worker overlaps
                # right now -- fall back to plain block-on-block
                # occlusion, exactly as before.
                for ob in other_block_boxes:
                    if boxes_close(ob, s["box"], self.occlusion_margin_px):
                        occluded_now = True
                        break
            # else: this slot already carries worker evidence from a
            # prior frame but no worker overlaps it RIGHT NOW --
            # occluded_now stays False this frame (a stale worker
            # relationship doesn't get proximity-based occlusion credit
            # here, same as the original ownership-framed version), and
            # occluded_by is left untouched (only release-on-reveal ever
            # clears it, not a lapsed overlap). A bound slot's clock is
            # governed by its own worker evidence; once no worker
            # currently corroborates it, unrelated nearby activity must
            # not keep resetting frames_since_seen -- otherwise a slot
            # near busy foot traffic could never accumulate enough
            # absence to resolve via either path.

            # [Fix -- ordinary single-frame detector jitter treated as a
            # full occlusion episode] See OCCLUSION_ONSET_DEBOUNCE_FRAMES'
            # own docstring. already_committed is true for any slot
            # already mid-occlusion-episode (state already "occluded", or
            # occluded_by already populated from a moment ago) -- an
            # ONGOING occlusion never re-debounces, only a BRAND NEW
            # onset does. For a brand new onset, occluded_now must
            # persist for OCCLUSION_ONSET_DEBOUNCE_FRAMES consecutive
            # frames before any state change or bookkeeping mutation
            # happens at all -- until then the slot's state, occluded_by,
            # last_worker_ids, and snapshot_boxes are all left completely
            # untouched, so a single missed detection frame that recovers
            # on its own leaves no trace whatsoever: no state flip, no
            # snapshot captured, nothing for the next frame's ordinary
            # Fast Association to have to undo or work around.
            already_committed = had_occluded_by_before or s["state"] == "occluded"
            if occluded_now and not already_committed:
                onset_streak = s.get("_occlusion_onset_streak", 0) + 1
                s["_occlusion_onset_streak"] = onset_streak
            else:
                onset_streak = self.OCCLUSION_ONSET_DEBOUNCE_FRAMES  # already committed -> no debounce gate
                s["_occlusion_onset_streak"] = 0
            commit_occlusion = occluded_now and (already_committed or onset_streak >= self.OCCLUSION_ONSET_DEBOUNCE_FRAMES)

            if commit_occlusion and worker_overlap_now:
                # [Fix -- flicker-driven evidence loss, preserved] A
                # block sitting at a worker's hand naturally flickers in
                # and out of "visible" frame to frame -- confirmed
                # directly from log evidence: 400+ evidence-clear/
                # re-establish cycles for a single slot, roughly one
                # flip every 2 processed frames, for hundreds of frames
                # straight. Treating EVERY re-establishment as a
                # brand-new pickup -- unconditionally resetting
                # bind_start_pos/drag_confirmed -- would wipe out
                # genuine cumulative displacement evidence on every
                # single flicker, even though the same worker(s) never
                # actually let go of the block. last_worker_ids
                # (persists across release, unlike occluded_by) is the
                # signal that tells those apart, generalized from a
                # single id to a set: if ANY worker overlapping this
                # frame also explained this slot just before its last
                # release, this is a continuation of the same ongoing
                # occlusion episode, not a fresh one -- keep everything
                # already accumulated. Only a genuinely disjoint set of
                # workers (or no prior worker at all) is treated as
                # fresh.
                prior_worker_ids = s.get("last_worker_ids", set())
                direct_continuation = bool(prior_worker_ids & set(overlapping_wids))
                # [Fix -- worker handoff / worker-id churn] A worker id
                # in overlapping_wids that never literally matches
                # prior_worker_ids can still be the SAME physical
                # handoff if it's a recorded handoff_partner of one of
                # the prior workers -- see the handoff_partners update
                # in update_workers for why this is needed and what it
                # represents.
                handoff_continuation = any(
                    wid in self.workers and bool(self.workers[wid].get("handoff_partners", set()) & prior_worker_ids)
                    for wid in overlapping_wids
                )
                is_continuation = direct_continuation or handoff_continuation
                for wid in overlapping_wids:
                    s["occluded_by"][wid] = frame_idx
                s["last_worker_ids"] = set(overlapping_wids)
                if not is_continuation:
                    s["bind_start_pos"] = s["pos"]
                    s["bind_start_frame"] = frame_idx
                    s["drag_confirmed"] = False
                    # [Option B] The worker's overlap with this slot's
                    # box, observed at the exact moment this evidence is
                    # first established, IS the positive evidence
                    # contact_frames was always meant to represent -- it
                    # no longer needs to accumulate incrementally while
                    # visible (there is no evidence then), so it's
                    # seeded directly at the existing threshold. This
                    # keeps _drag_exit_evidence's `ready` gate -- and
                    # therefore _check_drag_exit's confidence bar --
                    # completely unchanged; DragExit's own logic is not
                    # touched at all.
                    s["contact_frames"] = self.min_sustained_contact_frames
                    s["snapshot_boxes"] = [
                        other["box"] for osid, other in self.slots.items()
                        if osid != sid and other["state"] == "visible"
                    ]
                    print(f"  [WorkerBind] OCCLUDED_BY_WORKER: worker(s)={overlapping_wids} <-> "
                          f"slot={sid} (frame {frame_idx}) -- block disappeared while "
                          f"{'these workers' if len(overlapping_wids) > 1 else 'this worker'} "
                          f"overlapped it; contact_frames seeded at min_sustained_contact_frames="
                          f"{self.min_sustained_contact_frames} (Option B)")
                else:
                    print(f"  [WorkerContinuity] OCCLUDED_BY_WORKER: worker(s)={overlapping_wids} <-> "
                          f"slot={sid} (frame {frame_idx}) -- at least one of this frame's "
                          f"overlapping workers already corroborated this slot before its last "
                          f"release, not a fresh pickup; bind_start_pos/drag_confirmed/"
                          f"contact_frames={s.get('contact_frames', 0)} preserved unchanged")

            # Overlap only counts as REAL occlusion (allowed to reset the
            # give-up clock) within ABSOLUTE_MAX_HIDDEN_SEC of true elapsed
            # time since this slot was last a genuine detection match.
            # last_seen_frame is untouched by coincidental overlap -- only
            # an actual re-match updates it -- so this ceiling can't be
            # gamed the way frames_since_seen was.
            true_hidden_sec = (frame_idx - s.get("last_seen_frame", frame_idx)) / self.fps
            occlusion_still_credible = true_hidden_sec <= self.ABSOLUTE_MAX_HIDDEN_SEC

            if commit_occlusion and occlusion_still_credible:
                s["state"] = "occluded"
                s["frames_since_seen"] = 0
            else:
                if occluded_now and s["frames_since_seen"] == 0 and not occlusion_still_credible:
                    print(f"  [zombie-guard] slot={sid} occlusion claim no longer credible -- "
                          f"unseen for {true_hidden_sec:.1f}s of real elapsed time, past the "
                          f"{self.ABSOLUTE_MAX_HIDDEN_SEC:.0f}s ceiling; retirement clock now "
                          f"runs regardless of coincidental overlap")
                s["frames_since_seen"] += 1

            if (s.get("occluded_by") and s["frames_since_seen"] > 0
                    and s["frames_since_seen"] % 300 == 0):
                self._log_stuck_slot(sid, s, frame_idx)

            # Exit subsystem's decision, not Lifecycle's -- see docstring.
            if self._check_drag_exit(sid, frame_idx, seen_slots):
                continue

            # [Fix -- terminal decision for confirmed/waiting slots]
            # give_up_threshold used to key off s["bound_worker"] is not
            # None -- a HISTORICAL relationship, set once at bind time
            # and never re-verified, not a statement about whether
            # anything is still plausibly explaining this slot's absence
            # right now. That let a slot whose worker had long since
            # walked away keep drawing on max_bound_occlusion_frames
            # (minutes) of patience purely because bound_worker was
            # never cleared -- exactly the "stuck red circle forever"
            # pattern: no worker, no block, no plausible reason left,
            # yet still waiting on the strength of a stale binding.
            #
            # The extended grace period now requires genuinely credible
            # occlusion, not mere proximity: occluded_now (a worker or
            # block is physically near this slot's last known position
            # RIGHT NOW) AND occlusion_still_credible (that overlap is
            # still within ABSOLUTE_MAX_HIDDEN_SEC of true elapsed time
            # since this slot was last a real detection match) -- the
            # exact same combined test this function already trusts, a
            # few lines above, to decide whether to even label the slot
            # "occluded" this frame. Proximity alone was too weak a
            # bar -- coincidental overlap with a long-stale box could
            # still count as "occluded_now" long after ABSOLUTE_MAX_
            # HIDDEN_SEC makes that claim no longer credible (see
            # [zombie-guard] above), which would have kept granting the
            # long grace period to a slot this function's OWN existing
            # logic has already decided not to trust as occluded. Using
            # the same trusted signal both places keeps this decision
            # internally consistent. The instant genuine occlusion
            # stops holding, this slot falls back to the same short
            # no_reappear_grace_frames window any ordinary unbound slot
            # gets -- reusing the existing threshold, not inventing a
            # new one. Genuine drag-exit evidence still gets a full,
            # unmodified chance to commit first, via the unchanged
            # _check_drag_exit call immediately above -- this only
            # shortens how long a slot may wait with NO such evidence.
            genuinely_occluded = occluded_now and occlusion_still_credible
            give_up_threshold = (
                self.max_bound_occlusion_frames
                if (s.get("occluded_by") and genuinely_occluded)
                else self.no_reappear_grace_frames
            )
            # [Fix 3] Retirement must never interrupt an exit confirmation
            # already in progress. If _check_drag_exit has already opened
            # its own pending_load confirmation window for this slot,
            # defer any retirement decision entirely until that window
            # resolves (commits via DragExit, or is cancelled by a
            # reconnect) -- retiring out from under an in-progress
            # confirmation would silently drop evidence DragExit was
            # still in the middle of confirming.
            if s.get("pending_load", False):
                pass
            elif s["frames_since_seen"] >= give_up_threshold and not s["counted"]:
                # [Fix -- terminal decision for confirmed/waiting slots,
                # part 2] This used to also require "s['bound_worker'] is
                # None or not s['drag_confirmed']" before retiring.
                # drag_confirmed is a PERMANENT historical flag (see
                # _accumulate_drag_evidence -- set once, the moment the
                # block ever moved min_drag_displacement_px while bound,
                # and never reset), not a statement about whether an
                # exit is still plausible right now. Any slot that ever
                # moved a modest amount while a worker held it -- true of
                # nearly every real pickup -- was therefore PERMANENTLY
                # exempt from ordinary retirement, left to resolve only
                # via _check_drag_exit's own positional gate (block or
                # worker last-known position near the platform boundary).
                # If a block was picked up at an interior staging spot
                # and its worker vanished (expired) before either of them
                # ever got near an edge, that gate can never pass -- the
                # slot then waited forever with no fallback (confirmed
                # via logs: slot stuck 2700+ frames past its worker
                # expiring, drag_confirmed=True the whole time).
                #
                # This lifecycle fix guarantees exactly one thing: a slot
                # can no longer wait forever. What happens once waiting
                # ends is a SEPARATE decision -- see
                # _apply_terminal_exit_policy, called below, for the
                # (explicit, deliberate, recall-over-precision) counting
                # policy that decides LOADED vs GONE once we're here.
                # _check_drag_exit, called unconditionally above every
                # single frame this slot remains bound, still gets full,
                # unmodified first refusal -- with its positional
                # evidence requirement fully intact -- before either this
                # branch or the terminal policy is ever reached.
                if self._apply_terminal_exit_policy(sid, frame_idx, seen_slots):
                    continue
                print(f"  slot={sid} gone with no drag evidence — not counted, retiring "
                      f"(no plausible explanation remains: occluded_now={occluded_now}, "
                      f"genuinely_occluded={genuinely_occluded}, "
                      f"occluded_by={sorted(s.get('occluded_by', {}).keys())}, "
                      f"drag_confirmed={s['drag_confirmed']})")
                s["state"] = "gone"
                if s.get("occluded_by"):
                    self._release_worker_binding(sid)

    # ==================================================================
    # Registry Orchestrator -- Frame Update Entry Point
    # update_blocks() is intentionally thin: it sequences the pipeline
    # below in a fixed order every frame, with no hidden cross-phase
    # mutation -- each phase's job is fully described by its own name.
    # Subsystem ownership is strict: Identity owns slot creation/geometry
    # and reconnect decisions; Worker owns self.workers and is the ONLY
    # subsystem allowed to establish or sever the bound_worker <->
    # bound_slots relationship (via _update_slot_lifecycle's binding-
    # creation step and the release step in update_blocks' Phase 2 / see
    # _release_worker_binding, called by every other subsystem instead
    # of touching that relationship directly); Exit owns the actual
    # count commit (_check_direct_exit, _check_drag_exit); Lifecycle owns
    # presence/occlusion tracking and retirement, and calls into Exit
    # rather than committing counts itself.
    #
    # [Redesign -- provisional-slot lifecycle] A slot unclaimed by every
    # existing identity mechanism no longer vanishes for the frame. It
    # becomes a PENDING (provisional) slot -- an ordinary self.slots
    # entry, so Phase 2's own resolver mechanisms already apply to it on
    # every later frame with no extra wiring. Two, and only two, things
    # were added on top of that: Phase 2.5 (normal promotion, sustained
    # high-confidence visibility) and a terminal-promotion branch inside
    # Exit's own confirmation windows (_check_direct_exit /
    # _check_drag_exit) for a block that reaches the exit boundary
    # before it ever gets a normal mid-platform lifetime. A provisional
    # slot that is never reclaimed and never promoted simply ages out
    # via Lifecycle's existing give-up/retirement logic -- unidentified,
    # never counted, same as it always has for any other stale slot.
    #
    #   1. calibration bookkeeping (entry-side timeout, departure dedup)
    #   2. fast association / generate+resolve reconnect candidates /
    #      create PENDING slots  (one per-detection pass -- see note
    #      below on why these three don't split into separate full
    #      passes)
    #   2.5 normal promotion -- any provisional slot with sustained
    #      high-confidence visibility graduates to a confirmed,
    #      counted arrival (Identity subsystem; see
    #      _check_normal_promotion)
    #   3. bind workers                                    (Worker Binding)
    #   4. evaluate exits + commit counts  -- DIRECT EXIT ONLY here;
    #      runs AFTER worker binding so it sees THIS frame's binding
    #      state, not last frame's (previously ran mid-loop in phase 2,
    #      before binding had happened at all -- see fix note on
    #      _check_direct_exit's call site below). Also owns TERMINAL
    #      promotion for any provisional slot reaching the exit boundary
    #      here -- see _promote_provisional_slot.
    #   5. update lifecycle (occlusion/zombie-guard) + retire stale slots
    #      (_update_slot_lifecycle -- Lifecycle subsystem), which itself
    #      calls _check_drag_exit (Exit subsystem) as its own explicit
    #      step for slots not seen this frame -- also the other terminal
    #      promotion site, for a provisional slot carried out by a
    #      worker rather than seen directly crossing the boundary. Kept
    #      as one pass over slots rather than three full extra passes:
    #      each slot's own occlusion -> drag-exit -> retirement decision
    #      is a strict per-slot dependency chain with no cross-slot
    #      ordering issue, so extra full passes would add iteration and
    #      risk without fixing anything -- the ordering *within* the
    #      method, and the ownership boundary between what Lifecycle
    #      decides and what Exit commits, are both already correct.
    # ==================================================================

    def _resolve_priority_reclaims(self, block_detections, seen_slots):
        """[Architectural fix -- greedy per-detection processing order
        deciding, arbitrarily, which of several plausible detections
        reclaims a recently-occluded slot] _match_recently_occluded_slot
        is an unconditional "first close-enough detection wins"
        ownership shortcut (see its own docstring), evaluated
        independently for each detection in whatever order the detector
        happened to emit them -- with zero awareness of any OTHER
        detection this same frame that might be an even better match
        for that exact same slot. Ordinarily harmless (only one
        plausible detection exists per hidden slot). But when a worker
        briefly, incidentally overlaps a STATIONARY block -- not
        picking it up, just passing near or through it -- and, on the
        very reveal frame, a second, genuinely different detection also
        happens to land within the same tolerance of that slot's frozen
        position (e.g. emerging from the other side of the worker),
        whichever detection this loop reaches first claims the slot --
        and if that's the wrong one, the real reappearing block is shut
        out (its own true slot is already in seen_slots) and falls all
        the way through to a brand-new temp id, while the wrong
        detection keeps an identity that was never really its own.
        Confirmed directly from user report.

        This runs once, before the main per-detection loop, as a
        genuine (if narrowly scoped -- only this one ownership shortcut,
        not a general rewrite of detection-to-slot assignment) joint
        resolution pass: collect every (slot, detection) pair that
        clears the EXACT SAME tolerance and snapshot test _match_
        recently_occluded_slot itself already uses, then commit pairs
        globally in order of INCREASING distance -- the detection
        actually closest to where the slot was last known to be wins
        it, regardless of iteration order, and a slot or detection
        already claimed by a closer pair becomes unavailable to any
        other pair.

        Returns {detection_index: sid}: every detection index that
        should bypass ordinary per-detection resolution entirely and go
        straight to that slot. The caller still runs the exact same
        post-match side effects (_update_matched_slot_geometry,
        _accumulate_drag_evidence, worker-binding release, etc.)
        unchanged -- only the IDENTITY decision itself moves here,
        nothing about what happens once it's made."""
        candidate_pairs = []
        for sid, s in self.slots.items():
            if s["counted"] or s["state"] != "occluded":
                continue
            if sid in seen_slots:
                continue
            for i, (box, ratio) in enumerate(block_detections):
                pos = centroid(box)
                d_self = dist(pos, s["pos"])
                if (d_self > self.STATIONARY_SELF_RECLAIM_DIST_PX
                        and self._matches_snapshot(box, pos, s.get("snapshot_boxes", []))):
                    continue
                # [Fix -- edge-gap test let a genuinely different,
                # far-away block steal a slot] Originally reused
                # boxes_close (the same EDGE-TO-EDGE gap test _match_
                # recently_occluded_slot itself uses), on the theory
                # that this priority pass should accept exactly what
                # that method would accept, just resolved globally
                # instead of by iteration order. Confirmed as wrong via
                # direct log evidence: slot=2's box was tall (162-373 in
                # y), and boxes_close's edge-gap test let a fully
                # visible, ratio=1.000, 329px-away detection -- a
                # different, unrelated block on the floor below it --
                # pass as "close enough," because the GAP between the
                # two boxes' edges was small even though their CENTROIDS
                # were nowhere near each other. That edge-gap semantics
                # is correct for recognizing a fragment as still part of
                # a slot's own growing extent estimate (see _match_
                # visible_slot's docstring) -- it is NOT correct for
                # "is this really the same stationary object reappearing
                # essentially where it was," which is what this
                # PRIORITY pass exists for (see its own docstring: it
                # only runs for stationary-reclaim ambiguity, not carried
                # blocks). A stationary block's own reappearance should
                # be near-exact, centroid to centroid -- so this now
                # tests centroid distance directly, at the same
                # visible_match_dist_px tolerance, instead of the
                # box-edge-gap test.
                if d_self > self.visible_match_dist_px:
                    continue
                candidate_pairs.append((d_self, sid, i))

        candidate_pairs.sort(key=lambda t: t[0])
        forced = {}
        claimed_sids = set()
        claimed_idxs = set()
        for d, sid, i in candidate_pairs:
            if sid in claimed_sids or i in claimed_idxs:
                continue
            forced[i] = sid
            claimed_sids.add(sid)
            claimed_idxs.add(i)
            print(f"    [PriorityReclaim] slot={sid} <-> detection#{i} "
                  f"dist={d:.0f}px -- closest-match reclaim, decided before "
                  f"iteration order could give it to a farther competing detection")
        return forced

    def update_blocks(self, block_detections, frame_idx, worker_boxes):
        # Phase 1: calibration bookkeeping.
        self._check_entry_side_timeout(frame_idx)
        self._prune_recent_departures(frame_idx)

        seen_slots = set()
        seen_observations = set()
        other_block_boxes = [box for box, ratio in block_detections]
        # [Unification] There is no more per-frame carried_this_frame
        # ledger. Under the old three-pipeline design, a slot claimed by
        # one detection this frame was invisible to reconnect (seen_slots
        # excluded it everywhere), so a second same-frame fragment of
        # the same worker-carried block needed this out-of-band dict to
        # find its way back to the slot the first fragment just claimed.
        # _generate_reconnect_candidates now treats an already-claimed
        # slot (elapsed_frames == 0) as an ordinary candidate, found by
        # the same prediction-region + size test as any hidden slot --
        # so a second fragment finds its way back on its own, and this
        # pass over detections still needs to stay sequential (fragment
        # 2 needs slot state fragment 1 just wrote) but no longer needs
        # a side-channel to do it.

        # Highest-ratio (most reliable) fragment first, so it governs the
        # carried slot's geometry; any lower-ratio fragments of the same
        # physical block only suppress duplicate slot creation (see below).
        block_detections = sorted(block_detections, key=lambda bd: bd[1], reverse=True)

        # Phase 1.5: [Architectural fix -- greedy per-detection iteration
        # order deciding, arbitrarily, which of several plausible
        # detections reclaims a recently-occluded slot] See
        # _resolve_priority_reclaims' own docstring. Confirmed directly
        # from user report: a stationary block briefly, incidentally
        # overlapped by a worker (never picked up) got shut out of its
        # own slot on the reveal frame because a second, different
        # detection on the other side of the worker happened to be
        # iterated first and claimed it via _match_recently_occluded_
        # slot's unconditional first-come shortcut -- the real block
        # then fell through to a brand-new temp id while the wrong
        # detection kept its identity.
        forced_reclaims = self._resolve_priority_reclaims(block_detections, seen_slots)

        # Phase 2: fast association -> generate/resolve reconnect
        # candidates -> create new slots.
        #
        # [Fix -- persistent-identity invariant] A persistent slot must
        # originate on the platform. Confirmed via direct video review
        # (142152944, 232743869): the tracker was creating/resurrecting
        # persistent slots from detections outside the platform/exit
        # area, which then accumulated drag evidence and eventually got
        # counted -- inventing inventory outside the inventory region.
        # Separately (20260310225553131): a legitimately-established
        # slot must remain free to continue through and past the
        # boundary once it exists, or real departures go uncounted.
        #
        # The single choke point: every detection tries Fast Association
        # FIRST, unconditionally, regardless of location -- this is what
        # lets an already-visible, continuously-tracked slot keep being
        # matched right through its own exit crossing (DirectExit depends
        # on exactly this; untouched below). Only once Fast Association
        # FAILS does location matter: if the detection is outside the
        # platform at that point, it is by definition not a continuation
        # of something already visible, so nothing may create a new
        # identity, or reconnect a hidden one (the unified candidate
        # reconnect) for it -- the ONLY
        # remaining possibility that's still allowed is Rollback:
        # OutsideTrack, called directly and unmodified, which already
        # exists specifically to let an ALREADY-COUNTED departed slot
        # keep being visually tracked as it finishes leaving frame
        # without any count change. Reuses _past_exit_boundary (not
        # _inside_platform) deliberately -- the same generous,
        # negative-margin boundary DirectExit/DragExit/Rollback:
        # OutsideTrack already trust, so this decision can never
        # disagree with theirs about where the edge is.
        for det_idx, (box, ratio) in enumerate(block_detections):
            pos = centroid(box)

            if det_idx in forced_reclaims:
                # [Fix -- see Phase 1.5] Decided globally above, not by
                # iteration order -- skip straight to the winning slot,
                # everything after "if sid is not None" below (geometry
                # update, drag evidence, worker release) still runs
                # exactly as it would for any other match.
                sid = forced_reclaims[det_idx]
                mechanism = "RecentlyOccludedOwnership:Priority"
                rejected_sids = []
            else:
                sid = self._match_visible_slot(pos, box, seen_slots)
                mechanism = "Visible" if sid is not None else None
                rejected_sids = []

            if sid is None:
                # [Architecture -- ownership invariant] Checked before
                # reconnect is even attempted, not as a filter inside it.
                # If this detection already belongs to a graduated slot,
                # that's absolute -- claim it immediately and skip the
                # entire resolver (unified candidate generation/scoring,
                # rollback) for this detection outright.
                sid = self._match_recently_occluded_slot(pos, box, seen_slots)
                mechanism = "RecentlyOccludedOwnership" if sid is not None else None

            if sid is None:
                if self._past_exit_boundary(pos, margin=self.exit_margin_px):
                    sid = self._try_rollback_match(pos, box, frame_idx, verbose=True)
                    mechanism = "Rollback:Tight" if sid is not None else None
                else:
                    sid, mechanism, rejected_sids = self._resolve_detection_identity(pos, box, frame_idx, seen_slots, other_block_boxes)

            if sid is not None:
                # [Fix -- OutsideTrack re-touch silently undoing its own
                # state] _try_rollback_match's OutsideTrack branch (see
                # its own docstring) can return the SAME, already-
                # committed sid for a block still visibly leaving frame
                # after departure -- it deliberately does its own direct
                # pos/box update and sets state="departed" itself,
                # specifically so this already-retired identity is never
                # touched by the ordinary matched-slot pipeline again.
                # Confirmed directly from log evidence
                # (20260312103845210, slot=14): running
                # _update_matched_slot_geometry on it anyway silently
                # overwrote state="departed" back to "visible" (that
                # function's own unconditional last line) on the very
                # next line here -- which re-enters an already-departed
                # slot into every "still on platform" tally permanently,
                # and (via _accumulate_drag_evidence /
                # _release_worker_binding, each harmless in isolation)
                # does pointless work on an object that should be
                # completely inert from this point on. Every OTHER path
                # that can produce a non-None sid here already excludes
                # s["counted"] before ever returning it (Fast
                # Association, RecentlyOccludedOwnership, PriorityReclaim,
                # the reconnect resolver, and _try_rollback_match's own
                # "false positive -> brand new slot" branch all check
                # this) -- OutsideTrack is the one deliberate exception,
                # by design, so checking counted here catches exactly
                # that one case and nothing else.
                if self.slots[sid].get("counted", False):
                    continue
                self._update_matched_slot_geometry(sid, pos, box, ratio, frame_idx, seen_slots, mechanism)
                # Drag-exit evidence gathering is unconditional now (no
                # longer short-circuited by an inline direct-exit commit
                # here -- direct exit moved to Phase 4, after binding).
                # Harmless on a slot that Phase 4 later commits via direct
                # exit: a counted slot is excluded from every future
                # candidate/lifecycle pass, so its drag fields simply
                # stop being read.
                self._accumulate_drag_evidence(sid, pos, box)
                # [Architecture -- visibility-driven worker ownership]
                # "When a block becomes visible again, immediately
                # release." Vision wins as soon as vision returns -- no
                # timer, no grace period, no re-validation of any kind.
                # This runs for every matched detection this frame
                # (including same-frame duplicate fragments consumed
                # into an existing slot without a geometry update), but
                # _release_worker_binding is an explicit no-op on a slot
                # with no live binding, so calling it more than once per
                # frame for the same slot is harmless. Evidence
                # accumulation above already ran first, using the
                # binding while it still existed -- this only ever
                # clears bound_worker/bound_slots, never touches
                # drag_confirmed/contact_frames/bind_start_pos, so
                # nothing already earned is lost.
                self._release_worker_binding(sid)
                continue

            # [Fix -- illegal slot births, tightened] The exit-boundary
            # check alone (_past_exit_boundary with its generous,
            # negative exit_margin_px) only rejects detections that have
            # already crossed deep past the platform edge. It does NOT
            # reject a detection that never touched the platform at all
            # but also never crossed that far exit line -- e.g. noise or
            # a real object sitting beside the platform, off to the
            # side, outside any legal entry path. That gap is exactly
            # how phantom slots kept being born outside the platform.
            # The legal creation region is therefore the platform itself
            # PLUS its own entry corridor (where genuine new arrivals are
            # expected to first appear) -- nothing outside that region
            # may ever originate a new identity.
            if not (self._inside_platform(pos) or self._in_entry_corridor(pos)):
                continue

            if self._past_exit_boundary(pos, margin=self.exit_margin_px):
                # Never create a persistent identity from a detection
                # that first appears outside the platform -- a temporary,
                # non-persistent observation, dropped entirely. This is
                # the direct fix for the confirmed phantom-slot pattern:
                # such a detection now never reaches
                # _handle_unmatched_detection at all.
                continue

            # No identity resolved at all -- either a dedup echo of a
            # just-counted departure, or a genuine new arrival, INSIDE
            # the platform. Becomes a provisional (pending) slot, never
            # a permanent rejection -- see _handle_unmatched_detection.
            # [Fix -- terminal decision for provisional identities]
            # rejected_sids holds AT MOST ONE slot id -- the resolver's
            # own elimination/validation logic never surfaces a genuinely
            # ambiguous group here (see _resolve_via_candidates), only
            # the single, unambiguous candidate it evaluated and
            # rejected, if any. That keeps this evidence tied to ONE
            # identity, never spread across every candidate that
            # happened to be nearby -- a single ambiguous detection can
            # no longer promote two different provisional slots at once.
            # If that one candidate is a still-provisional slot, its own
            # resolver_failed_streak (the same persistent self.slots
            # entry, not a fresh association) is charged directly. Only
            # when the resolver found nothing at all to blame (empty, or
            # the rejected candidate wasn't provisional) does this
            # detection start a brand-new provisional identity.
            charged_provisional = False
            for rej_sid in rejected_sids:
                rej_s = self.slots.get(rej_sid)
                if rej_s is None or not rej_s.get("provisional", False) or rej_s["counted"]:
                    continue
                rej_s["resolver_failed_streak"] = rej_s.get("resolver_failed_streak", 0) + 1
                charged_provisional = True
                print(f"    [ResolverFailure] slot={rej_sid} evaluated and rejected by the "
                      f"resolver's own elimination/validation for this detection -> "
                      f"streak={rej_s['resolver_failed_streak']}/{self.resolver_exhausted_frames} "
                      f"(frame {frame_idx})")
                if rej_s["resolver_failed_streak"] >= self.resolver_exhausted_frames:
                    self._resolve_provisional_terminal_state(rej_sid, frame_idx)

            if charged_provisional:
                continue

            self._handle_unmatched_detection(pos, box, ratio, frame_idx, seen_slots, seen_observations)

        # Phase 2b: prune any UnknownObservation not re-matched by any
        # detection this frame -- see _prune_unmatched_observations'
        # own docstring for why this one rule covers every required
        # case (reconnect succeeded elsewhere, fragment merged away,
        # false detection never recurred).
        self._prune_unmatched_observations(seen_observations, frame_idx)

        # Phase 2.5: normal promotion -- any provisional slot that has
        # now accumulated enough sustained, high-confidence visibility
        # graduates to a confirmed, counted arrival. Runs before Phase 4
        # so a slot promoted this frame is evaluated for an ordinary
        # exit right after, rather than needing the (relaxed) terminal
        # promotion path.
        self._check_normal_promotion(frame_idx)

        # [Architecture -- visibility-driven worker ownership] There is
        # no separate "Phase 3: bind workers to slots" step anymore.
        # Binding creation and release are now driven entirely by
        # visibility transitions: release happens inline in Phase 2,
        # the instant a slot is matched (visible) again (see the
        # _release_worker_binding call right after
        # _accumulate_drag_evidence, above); creation happens inline in
        # _update_slot_lifecycle (Phase 5, below), the instant a slot
        # goes unseen while an unbound worker's box overlaps it. Neither
        # needs a dedicated phase of its own -- each belongs to the
        # exact transition it represents.

        # Phase 4: evaluate exits + commit counts -- direct exit. Runs
        # over every slot matched in Phase 2. bound_worker is already
        # correct for every slot here -- Phase 2's release-on-reveal
        # step (above) already cleared it the instant each slot was
        # matched this frame -- so _check_direct_exit's own
        # bound_worker-is-None ownership gate reflects reality, not a
        # stale prior-frame snapshot.
        for sid in seen_slots:
            s = self.slots.get(sid)
            if s is None or s["counted"] or s["state"] == "gone":
                continue
            self._check_direct_exit(sid, s["pos"], s["box"], frame_idx, seen_slots)

        # Phase 5: update lifecycle (occlusion / zombie-guard) + evaluate
        # and commit drag exits + retire stale slots, for everything not
        # freshly matched above.
        self._update_slot_lifecycle(frame_idx, worker_boxes, other_block_boxes, seen_slots)

        return self.loaded_count


# ======================================================================
# Rendering / Video I/O
# ======================================================================
class FrameReader(threading.Thread):
    def __init__(self, video_path, start_frame, end_frame, queue_size=64):
        super().__init__(daemon=True)
        self.cap = cv2.VideoCapture(video_path)
        self.cap.set(cv2.CAP_PROP_POS_FRAMES, start_frame)
        self.start_frame = start_frame
        self.end_frame = end_frame
        self.q = queue.Queue(maxsize=queue_size)
        self.stopped = False

    def run(self):
        frame_idx = self.start_frame
        while not self.stopped and frame_idx < self.end_frame:
            success, raw = self.cap.read()
            if not success:
                break
            self.q.put((frame_idx, raw))
            frame_idx += 1
        self.q.put(None)
        self.cap.release()

    def get(self):
        return self.q.get()


def draw_frame(job):
    im0 = job["im0"]
    last_plat_box = job["last_plat_box"]
    person_boxes = job["person_boxes"]
    slots_snapshot = job["slots_snapshot"]
    ice_snapshot = job["ice_snapshot"]
    smooth_now = job["smooth_now"]
    loaded_count = job["loaded_count"]
    active_s = job["active_s"]
    inactive_s = job["inactive_s"]
    live_fps = job["live_fps"]
    t_sec = job["t_sec"]
    h = job["h"]

    vis = im0
    for (x1, y1, x2, y2) in person_boxes:
        cv2.rectangle(vis, (x1, y1), (x2, y2), (255, 255, 0), 2)
        cv2.putText(vis, "WORKER", (x1, y1 - 6), cv2.FONT_HERSHEY_SIMPLEX, 0.45, (255, 255, 0), 1)

    if last_plat_box:
        cv2.rectangle(vis, (last_plat_box[0], last_plat_box[1]),
                      (last_plat_box[2], last_plat_box[3]), (0, 200, 255), 2)

    for sid, cx, cy, active in slots_snapshot:
        cx, cy = int(cx), int(cy)
        color = (0, 255, 100) if active else (100, 100, 255)
        cv2.circle(vis, (cx, cy), 10, color, -1 if active else 2)
        cv2.putText(vis, f"S{sid}", (cx-10, cy+4), cv2.FONT_HERSHEY_SIMPLEX, 0.42, (0, 0, 0) if active else color, 1)

    for tid, stable_id, b, ratio in ice_snapshot:
        color = (0, 255, 0)
        cv2.rectangle(vis, (b[0], b[1]), (b[2], b[3]), color, 2)
        label = f"S{stable_id}" if stable_id is not None else f"T{tid}"
        cv2.putText(vis, f"{label} {ratio:.2f}", (b[0], b[1]-4), cv2.FONT_HERSHEY_SIMPLEX, 0.38, color, 1)

    cv2.rectangle(vis, (8, 8), (220, 100), (0, 0, 0), -1)
    cv2.rectangle(vis, (8, 8), (220, 100), (0, 255, 100), 1)
    cv2.putText(vis, f"On Platform: {smooth_now}", (14, 24), cv2.FONT_HERSHEY_SIMPLEX, 0.4, (200, 200, 200), 1)
    cv2.putText(vis, f"LOADED: {loaded_count}", (14, 48), cv2.FONT_HERSHEY_SIMPLEX, 0.44, (0, 140, 255), 1)
    cv2.putText(vis, f"a={active_s} m={inactive_s} t={len(ice_snapshot)} FPS:{live_fps:.0f}",
                (14, 72), cv2.FONT_HERSHEY_SIMPLEX, 0.32, (150, 150, 150), 1)
    cv2.putText(vis, f"t={t_sec:.1f}s", (8, h-8), cv2.FONT_HERSHEY_SIMPLEX, 0.4, (180, 180, 180), 1)

    if (OUT_W, OUT_H) != (INPUT_W, INPUT_H):
        vis = cv2.resize(vis, (OUT_W, OUT_H))
    return vis


class VideoWriterThread(threading.Thread):
    def __init__(self, out_path, fps, size, queue_size=64):
        super().__init__(daemon=True)
        self.vw = cv2.VideoWriter(out_path, cv2.VideoWriter_fourcc(*"mp4v"), fps, size)
        self.q = queue.Queue(maxsize=queue_size)

    def run(self):
        while True:
            job = self.q.get()
            if job is None:
                break
            self.vw.write(draw_frame(job))
        self.vw.release()

    def submit(self, job):
        self.q.put(job)

    def stop(self):
        self.q.put(None)
        self.join()


# ======================================================================
# Tracker Setup
# ======================================================================
FASTTRACK_OVERRIDES = {
    "occ_cover_thresh": 0.55,
    "occ_reappear_window": 750,
    "track_buffer": 750,
    "active_occ_to_lost_thresh": 60,
    "init_iou_suppress": 0.4,
    "dampen_motion_occ": 0.2,
}

def init_tracker(tracker_yaml, frame_rate):
    cfg_dict = YAML.load(check_yaml(tracker_yaml))
    if FASTTRACK_OVERRIDES:
        cfg_dict.update(FASTTRACK_OVERRIDES)
        print(f"FastTracker overrides applied: {FASTTRACK_OVERRIDES}")
    cfg = IterableSimpleNamespace(**cfg_dict)
    return TRACKER_MAP[cfg.tracker_type](args=cfg)

def apply_tracking(result, tracker):
    det = result.boxes.cpu().numpy()
    if len(det) == 0:
        return result[0:0] if len(result.boxes) else result
    tracks = tracker.update(det, result.orig_img)
    if len(tracks) == 0:
        return result[0:0]
    idx = tracks[:, -1].astype(int)
    updated = result[idx]
    updated.update(boxes=torch.as_tensor(tracks[:, :-1]))
    return updated


# ======================================================================
# Model Loading & Main Pipeline
# ======================================================================
print(f"Loading model: {MODEL_PATH_PT}")
if not os.path.exists(MODEL_PATH_PT):
    raise FileNotFoundError(f"{MODEL_PATH_PT} not found.")
model = YOLO(MODEL_PATH_PT, task="segment")
model.to(DEVICE)
print(f"Model loaded on    : {next(model.model.parameters()).device}")

print(f"Loading person-detection model: {PERSON_MODEL_PATH}")
person_model = YOLO(PERSON_MODEL_PATH)
person_model.to(DEVICE)
print(f"Person model loaded on : {next(person_model.model.parameters()).device}")
print("=" * 60)


cap_probe = cv2.VideoCapture(VIDEO_PATH)
assert cap_probe.isOpened(), "Error reading video file"
fps = cap_probe.get(cv2.CAP_PROP_FPS)
total = int(cap_probe.get(cv2.CAP_PROP_FRAME_COUNT))
orig_w = int(cap_probe.get(cv2.CAP_PROP_FRAME_WIDTH))
orig_h = int(cap_probe.get(cv2.CAP_PROP_FRAME_HEIGHT))
cap_probe.release()

computed_duration_s = total / fps if fps > 0 else float("nan")
print(f"FPS check: {fps:.2f} fps, {total} frames -> {computed_duration_s:.1f}s "
      f"({computed_duration_s/60:.1f} min). Compare to your player's shown duration.")

w, h = INPUT_W, INPUT_H
start_frame = int(START_SECOND * fps)
end_frame = int(END_SECOND * fps) if END_SECOND is not None else total
end_frame = min(end_frame, total)

EXIT_GRACE_FRAMES = int(EXIT_GRACE_SECONDS * fps / PROCESS_EVERY_N)
NO_REAPPEAR_GRACE_FRAMES = int(NO_REAPPEAR_GRACE_SECONDS * fps / PROCESS_EVERY_N)
MAX_BOUND_OCCLUSION_FRAMES = int(MAX_BOUND_OCCLUSION_SECONDS * fps / PROCESS_EVERY_N)
ENTRY_SIDE_TIMEOUT_FRAMES = int(ENTRY_SIDE_TIMEOUT_SECONDS * fps)
DEPARTURE_DEDUP_WINDOW_FRAMES = int(DEPARTURE_DEDUP_WINDOW_SECONDS * fps)
MIN_SETTLING_FRAMES = int(MIN_SETTLING_SECONDS * fps)
print(f"Minimum settling time before a slot can depart: {MIN_SETTLING_SECONDS}s = {MIN_SETTLING_FRAMES} raw frames "
      f"(prevents a block that just arrived near an edge from being mistaken for one that just departed)")
print(f"Departure dedup window: {DEPARTURE_DEDUP_WINDOW_SECONDS}s = {DEPARTURE_DEDUP_WINDOW_FRAMES} raw frames "
      f"(prevents an already-counted block from being re-counted while it's still visible leaving frame)")
print(f"Exit grace window: {EXIT_GRACE_SECONDS}s = {EXIT_GRACE_FRAMES} processed frames")
print(f"No-reappear grace window: {NO_REAPPEAR_GRACE_SECONDS}s = {NO_REAPPEAR_GRACE_FRAMES} processed frames")
print(f"Max bound-occlusion window: {MAX_BOUND_OCCLUSION_SECONDS}s = {MAX_BOUND_OCCLUSION_FRAMES} processed frames "
      f"(how long a slot stays bound mid-drag before giving up, separate from the short no-reappear window)")
print(f"Entry-side auto-detect timeout: {ENTRY_SIDE_TIMEOUT_SECONDS}s = {ENTRY_SIDE_TIMEOUT_FRAMES} raw frames "
      f"(falls back to '{ENTRY_SIDE_FALLBACK}' if no genuine arrival is seen by then)")

print(f"Video  : {orig_w}x{orig_h} -> {w}x{h} @ {fps:.1f}fps ({total} frames)")
print(f"Range  : {start_frame/fps:.1f}s -> {end_frame/fps:.1f}s")
print(f"Tracker: {TRACKER_YAML}  |  BATCH_SIZE={BATCH_SIZE}")
print("=" * 60)

tracker = init_tracker(TRACKER_YAML, frame_rate=int(fps))

reader = FrameReader(VIDEO_PATH, start_frame, end_frame)
reader.start()

writer = VideoWriterThread(OUTPUT_VIDEO, fps, (OUT_W, OUT_H))
writer.start()

registry = None
last_plat_box = None
count_history = deque(maxlen=SMOOTH_WINDOW)
frame_log = []

fps_window = deque(maxlen=10)
last_batch_fps = 0.0

time_wait_reader = 0.0
time_resize = 0.0
time_inference = 0.0
time_person_inference = 0.0
time_postprocess = 0.0
time_writer_submit = 0.0
frames_processed = 0
frames_read = 0
last_confirmed_frame_idx = -1

with torch.inference_mode():
    reading_done = False
    while not reading_done:
        _batch_t0 = time.perf_counter()

        batch_frame_idxs = []
        batch_images = []

        while len(batch_images) < BATCH_SIZE:
            _t0 = time.perf_counter()
            item = reader.get()
            _t1 = time.perf_counter()
            time_wait_reader += (_t1 - _t0)

            if item is None:
                reading_done = True
                break
            frame_idx, raw = item
            frames_read += 1
            if PROCESS_EVERY_N > 1 and (frame_idx - start_frame) % PROCESS_EVERY_N != 0:
                continue

            _t2 = time.perf_counter()
            im0 = cv2.resize(raw, (INPUT_W, INPUT_H))
            _t3 = time.perf_counter()
            time_resize += (_t3 - _t2)

            batch_frame_idxs.append(frame_idx)
            batch_images.append(im0)

        if not batch_images:
            break

        for k in range(1, len(batch_frame_idxs)):
            assert batch_frame_idxs[k] > batch_frame_idxs[k-1], "frame order broke inside batch"

                                                                      
                                                                                
        QUANTIZE_ARG = 16 if (USE_HALF and DEVICE != "cpu") else None

        _t4 = time.perf_counter()
        results = model.predict(batch_images, imgsz=INFER_SIZE, quantize=QUANTIZE_ARG,
                                 conf=DETECTION_CONF_FLOOR, device=DEVICE, verbose=False)
        _t5 = time.perf_counter()
        time_inference += (_t5 - _t4)

        _tp0 = time.perf_counter()
        person_results = person_model.predict(batch_images, imgsz=INFER_SIZE, quantize=QUANTIZE_ARG,
                                                device=DEVICE, classes=[0], conf=PERSON_CONF_THRESHOLD, verbose=False)
        _tp1 = time.perf_counter()
        time_person_inference += (_tp1 - _tp0)
        assert len(person_results) == len(batch_images), "person batch size mismatch"
        assert len(results) == len(batch_images), "batch size mismatch"

        for frame_idx, im0, result, person_result in zip(batch_frame_idxs, batch_images, results, person_results):
            assert frame_idx > last_confirmed_frame_idx, "frame order broke across batches"
            last_confirmed_frame_idx = frame_idx

            person_boxes = []
            if person_result.boxes is not None and len(person_result.boxes) > 0:
                for pbox in person_result.boxes:
                    person_boxes.append(list(map(int, pbox.xyxy[0].tolist())))

            _t6 = time.perf_counter()
            tracked_result = apply_tracking(result, tracker)

            ice_detections = {}
            platform_boxes = []

            if tracked_result.boxes is not None and len(tracked_result.boxes) > 0:
                for box in tracked_result.boxes:
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
            block_detections = []

            if last_plat_box is not None:
                if registry is None:
                    registry = EventBasedRegistry(
                        entry_side=ENTRY_SIDE, platform_box=last_plat_box,
                        entry_corridor_depth_px=ENTRY_CORRIDOR_DEPTH_PX,
                        visible_match_dist_px=VISIBLE_MATCH_DIST_PX,
                        occluded_match_dist_px=OCCLUDED_MATCH_DIST_PX,
                        worker_bind_margin_px=WORKER_BIND_MARGIN_PX,
                        occlusion_margin_px=OCCLUSION_MARGIN_PX,
                        min_drag_displacement_px=MIN_DRAG_DISPLACEMENT_PX,
                        exit_grace_frames=EXIT_GRACE_FRAMES,
                        no_reappear_grace_frames=NO_REAPPEAR_GRACE_FRAMES,
                        min_ratio_ever_for_real_block=MIN_RATIO_EVER_FOR_REAL_BLOCK,
                        min_high_ratio_frames=MIN_HIGH_RATIO_FRAMES,
                        stationary_reid_dist_px=STATIONARY_REID_DIST_PX,
                        pending_load_confirm_frames=PENDING_LOAD_CONFIRM_FRAMES,
                        rollback_window_frames=ROLLBACK_WINDOW_FRAMES,
                        recent_merge_window_frames=RECENT_MERGE_WINDOW_FRAMES,
                        recent_merge_dist_px=RECENT_MERGE_DIST_PX,
                        rollback_reappear_dist_px=ROLLBACK_REAPPEAR_DIST_PX,
                        min_sustained_contact_frames=MIN_SUSTAINED_CONTACT_FRAMES,
                        entry_side_votes_needed=ENTRY_SIDE_VOTES_NEEDED,
                        entry_side_timeout_frames=ENTRY_SIDE_TIMEOUT_FRAMES,
                        entry_side_fallback=ENTRY_SIDE_FALLBACK,
                        max_bound_occlusion_frames=MAX_BOUND_OCCLUSION_FRAMES,
                        exit_margin_px=EXIT_MARGIN_PX,
                        direct_exit_margin_px=DIRECT_EXIT_MARGIN_PX,
                        departure_dedup_window_frames=DEPARTURE_DEDUP_WINDOW_FRAMES,
                        departure_dedup_dist_px=DEPARTURE_DEDUP_DIST_PX,
                        min_settling_frames=MIN_SETTLING_FRAMES,
                        fps=fps,
                        resolver_exhausted_frames=RESOLVER_EXHAUSTED_FRAMES,
                    )
                else:
                    registry.platform_box = last_plat_box

                for tid, (b, conf) in ice_detections.items():
                    ratio = overlap_ratio(b, last_plat_box)
                    if ratio > 0:
                        block_detections.append((b, ratio))

                registry.update_workers(person_boxes, frame_idx)
                registry.update_blocks(block_detections, frame_idx, person_boxes)

            loaded_count = registry.loaded_count if registry is not None else 0
            current_on = (
                sum(1 for s in registry.slots.values() if s["state"] in ("visible", "occluded"))
                if registry is not None else 0
            )
            count_history.append(current_on)
            smooth_now = mode_count(count_history)

            ice_snapshot = []
            if last_plat_box is not None:
                for tid, (b, conf) in ice_detections.items():
                    ratio = overlap_ratio(b, last_plat_box)
                    stable_id = None
                    if registry is not None:
                        bpos = centroid(b)
                        best_d = float("inf")
                        for sid, slot in registry.slots.items():
                            if slot["state"] == "gone":
                                continue
                            d = dist(bpos, slot["pos"])
                            if d < best_d:
                                best_d, stable_id = d, sid
                        # [Fix] Confirmed bug: no distance cutoff at all --
                        # this always returned the single nearest non-gone
                        # slot, no matter how far away it actually was. The
                        # instant a block's real slot is marked "gone"
                        # (happens immediately on commit), a block still
                        # sitting in the exact same spot on screen would
                        # get relabeled with whatever OTHER slot happened
                        # to be least-far-away -- even a completely
                        # unrelated block on the other side of the
                        # platform -- making one continuously-visible
                        # block appear, on screen and in the CSV, to
                        # switch identities from its real id to a
                        # stranger's. Reuse visible_match_dist_px, the
                        # same "close enough to be this block" constant
                        # already used everywhere else in the registry --
                        # past it, there's no honest label to give, so
                        # leave it unlabeled rather than borrow one.
                        if best_d > registry.visible_match_dist_px:
                            stable_id = None
                    ice_snapshot.append((tid, stable_id, b, ratio))
                    bcx, bcy = centroid(b)
                    frame_log.append({
                        "frame": frame_idx, "time_sec": round(t_sec, 3),
                        "track_id": tid, "stable_id": stable_id if stable_id is not None else "",
                        "overlap_ratio": round(ratio, 4), "conf": round(conf, 3),
                        # [DIAG] Raw geometry, so a slot's/track's actual
                        # coordinate trajectory can be read straight from
                        # the CSV instead of re-derived from log messages.
                        "cx": round(bcx, 1), "cy": round(bcy, 1),
                        "x1": round(b[0], 1), "y1": round(b[1], 1),
                        "x2": round(b[2], 1), "y2": round(b[3], 1),
                    })

            live_fps = last_batch_fps
            active_s = sum(1 for s in registry.slots.values() if s["state"] == "visible") if registry else 0
            inactive_s = sum(1 for s in registry.slots.values() if s["state"] == "occluded") if registry else 0

            slots_snapshot = [
                (sid, slot["pos"][0], slot["pos"][1], slot["state"] == "visible")
                for sid, slot in registry.slots.items() if slot["state"] != "gone"
            ] if registry else []

            job = {
                "im0": im0, "last_plat_box": last_plat_box, "person_boxes": person_boxes,
                "slots_snapshot": slots_snapshot, "ice_snapshot": ice_snapshot,
                "smooth_now": smooth_now, "loaded_count": loaded_count,
                "active_s": active_s, "inactive_s": inactive_s,
                "live_fps": live_fps, "t_sec": t_sec, "h": h,
            }
            _t7 = time.perf_counter()
            time_postprocess += (_t7 - _t6)

            _t8 = time.perf_counter()
            writer.submit(job)
            _t9 = time.perf_counter()
            time_writer_submit += (_t9 - _t8)
            frames_processed += 1

            if frame_idx % max(1, int(fps)) == 0:
                print(f"t={t_sec:6.1f}s | on:{smooth_now:2d} | LOADED:{loaded_count:3d} | "
                      f"active:{active_s:2d} mem:{inactive_s:2d} | FPS:{live_fps:5.1f}")

        _batch_elapsed = time.perf_counter() - _batch_t0
        batch_fps = len(batch_frame_idxs) / _batch_elapsed if _batch_elapsed > 0 else 0
        fps_window.append(batch_fps)
        last_batch_fps = sum(fps_window) / len(fps_window)

writer.stop()
pd.DataFrame(frame_log).to_csv(OUTPUT_CSV, index=False)

print("\n" + "=" * 60)
print("End-of-video finalization pass:")
if registry is not None:
    for sid, slot in registry.slots.items():
        if slot["state"] == "gone" or slot.get("counted", False):
            continue
        # Use the EXACT same drag-evidence evaluation DragExit itself
        # uses (shared _drag_exit_evidence helper) -- ready gate
        # (high-ratio history, settling time, sustained contact) AND the
        # same drag_confirmed-OR-worker-displacement evidence, so
        # finalization can never diverge from the live DragExit path.
        ready, dragging_evidence, _w = registry._drag_exit_evidence(sid, frame_idx)
        # A slot that is still "visible" at the very last processed
        # frame was, by definition, plainly seen sitting on the platform
        # -- it cannot simultaneously be a block that was mid-carry out
        # of frame when the video cut off. Only "occluded" slots (i.e.
        # a worker appeared to be carrying it out of view right as the
        # video ended, and just didn't get pending_load_confirm_frames
        # worth of confirmation time) are eligible for this fallback --
        # otherwise a long-stationary block whose bound worker's own box
        # jitter eventually nudges drag_confirmed/displacement past
        # threshold gets wrongly counted as loaded despite never having
        # actually left.
        has_drag_evidence = (
            slot["state"] == "occluded"
            and slot.get("occluded_by")
            and ready
            and dragging_evidence
            # Same positional plausibility gate as the live DragExit path
            # (see _check_drag_exit) -- a slot whose last known position
            # was never near the platform outline was very likely just
            # occluded at an interior staging spot, not genuinely
            # mid-exit, and shouldn't be counted here either. Also
            # matches the live path's worker-position fallback: the
            # block's own frozen position is often stale by the time it
            # fully occludes, while its (possibly since-expired) worker
            # often kept being tracked further toward the actual exit.
            and (
                registry._past_exit_boundary(slot["pos"], margin=registry.exit_margin_px)
                or (
                    _w is not None
                    and registry._past_exit_boundary(_w["pos"], margin=registry.exit_margin_px)
                )
            )
        )
        if has_drag_evidence:
            # [Redesign] Confirmed gap: this branch used to commit
            # counted=True / loaded_count += 1 directly with no call to
            # _promote_provisional_slot, unlike the live _check_direct_exit
            # / _check_drag_exit paths (both call it before committing).
            # A provisional slot reaching finalization would have been
            # counted as a departure with entered_count never incremented
            # and no entry vote ever cast for it -- silently collapsing
            # arrival and departure into a single asymmetric event. Same
            # sequencing as everywhere else: synthesize arrival first,
            # from the slot's own first-observed evidence, then commit
            # the departure.
            slot_provisional = slot.get("provisional", False)
            if slot_provisional:
                registry._promote_provisional_slot(sid, frame_idx, terminal=True)
            slot["counted"] = True
            slot["state"] = "gone"
            registry.loaded_count += 1
            print(f"  LOADED (video ended mid-drag{':Terminal' if slot_provisional else ''}): "
                  f"slot={sid} had confirmed drag evidence toward "
                  f"the exit but the video ended before the normal grace period completed "
                  f"-> TOTAL={registry.loaded_count}")
        else:
            print(f"  slot={sid} state={slot['state']} at video end — left as still on platform, "
                  f"not counted (no confirmed drag-to-exit evidence).")

active_end = (
    sum(1 for s in registry.slots.values() if s["state"] in ("visible", "occluded"))
    if registry is not None else 0
)
total_elapsed = time.time() - SCRIPT_START_TIME

print("\n" + "=" * 60)
print(f"  LOADED (confirmed departed forward) : {registry.loaded_count if registry else 0}")
print(f"  Still visually on platform now       : {active_end}")
print("=" * 60)
print(f"  TOTAL EXECUTION TIME : {format_duration(total_elapsed)}")
print(f"  BATCH_SIZE USED      : {BATCH_SIZE}")
print("=" * 60)

stage_total = (time_wait_reader + time_resize + time_inference +
               time_person_inference + time_postprocess + time_writer_submit)
n = max(frames_processed, 1)

print("\n----- TIMING BREAKDOWN -----")
print(f"frames_read={frames_read}  frames_processed={frames_processed}  "
      f"total_wall_time={total_elapsed:.1f}s  BATCH_SIZE={BATCH_SIZE}")
print(f"{'stage':<20}{'total_s':>10}{'pct':>8}{'avg_ms/frame':>15}")
for name, val in [
    ("wait_for_reader", time_wait_reader),
    ("resize", time_resize),
    ("inference", time_inference),
    ("person_inference", time_person_inference),
    ("postprocess", time_postprocess),
    ("writer_submit", time_writer_submit),
]:
    pct = (val / stage_total * 100) if stage_total > 0 else 0
    avg_ms = (val / n) * 1000
    print(f"{name:<20}{val:>10.1f}{pct:>7.1f}%{avg_ms:>13.2f}ms")
print("-----------------------------\n")

print(f"Log   -> {OUTPUT_CSV}")
print(f"Video -> {OUTPUT_VIDEO}")