"""Pure image recognition of the fishing mini-game as a mixin (no own state).

Contains the three detection methods of the FishingBot, which read exclusively from
the capture (fish position, clock/minigame, daily reward) and only access
class/instance attributes already defined in :class:`fishingbot.FishingBot`
(``needle_img``, ``FISH_RANGE``, ``fish_pos_x`` ...).

Extracted as a mixin so the stateful cast/state-machine part in :mod:`fishingbot`
remains lightweight. ``FishingBot`` inherits from
:class:`FishingDetectMixin`; method resolution (``self.detect`` etc.) and every
``self.`` access therefore remain byte-identical to the earlier single-class version.
"""

import math
import cv2 as cv
from time import time

try:
    import numpy as np
except Exception:  # pragma: no cover - numpy is bundled with cv2; pure fallback
    np = None

from fishing_match import _match_template_max
from respath import resource_path


# -- Golden tuna confirmation dialog (after the option click) ------------------
#
# After clicking one of the three options (release/split/bait), the SERVER opens
# a second window with a single OK button (for example, the release bonus dialog).
# Two hard live findings determine the design:
#   1. The window does NOT black out the image corners (max 125 instead of 0) ->
#      detect_daily_reward never sees it; it needs its own detection.
#   2. The window is NOT at a fixed position: its height depends on the message
#      text and its placement varies (live references: OK center (403,250) vs.
#      (403,202) client). Fixed coordinates (v1.1.5) missed the second variant ->
#      the OK button is now searched across the entire frame by template (like the
#      campfire label search), and the click goes to the FOUND location instead of a constant.
#
# Detection = two factors:
#   * Grayscale NCC of the OK button template (images/golden_ok_knob.png,
#     20x32): positive 0.81/1.00, strongest negative case 0.61 -> threshold
#     0.70 with margin on both sides. It only runs within the 10s window after the option click.
#   * Bar check: the button sits on a broad, FLAT gray bar; both flanks (left/right of the match)
#     must be flat (std <= 12) and must not contain either a black hole or a burned-out area.
#
# BRIGHTNESS WINDOW INTENTIONALLY WIDE (v1.6.12, 2026-08-18). It was 50..110 --
# calibrated on the three references (measured 65.7 / 79.3 / 84.7). This is exactly
# the mistake this project has paid for before: a threshold based on samples instead of the actual object.
# The bar is SEMI-TRANSPARENT, so its brightness follows the scene BEHIND it; on a brighter fishing spot,
# the 110 would have been exceeded and the OK button would have remained unclickable even with perfect
# detection of the button itself. That is exactly the complaint from the tester ("no longer clicks").
# The actual distinction is still provided by the NCC threshold (positive 0.80/0.81/1.00 against strongest
# negative 0.57 across all 30 reference images) plus the flatness (positive std <= 3.3 against negatives >= 8.7).
# The window should only exclude "black nothing" and "burned-out white".
GOLDEN_OK_TEMPLATE = 'images/golden_ok_knob.png'
GOLDEN_OK_NCC_MIN = 0.70
GOLDEN_OK_BAR_MEAN = (20.0, 200.0)
GOLDEN_OK_BAR_STD_MAX = 12.0

# -- Second path: the ENDS of the OK bar (v1.6.13, User log 2026-09-02) ---------
#
# The case from the log: option click 13:25:46, then no OK click within 10 s even though the dialog was present.
# In the screenshot, the OK button itself only reaches 0.68 -- below threshold -- because the GUILD NAME of the
# player's character in pink stretches across the "OK". The character stands in the middle of the image,
# the dialog is semi-transparent, and the client draws name tags OVER the dialog. Whether this happens depends
# on the camera and the location -- exactly the pattern of "sometimes it works, sometimes it doesn't".
#
# What a name tag does NOT reach are the ENDS of the bar: it is 280 px wide (client x 260..539), tags are ~150 px
# and hang centered on the character. The dialog frame also stands FIXED (client x 49..748, y from 149 onward;
# all five references identical) -- only the bar moves in y with the text length. For that reason, both ends are
# searched with templates in NARROW columns at fixed x positions; a hit requires BOTH ends at the same height.
#
# MEASURED (five dialogs, 25 negatives): weakest positive 0.775 (both ends, |dy| <= 4), strongest negative 0.598 at |dy| = 13 -- two separate gaps.
# Cost 0.15 ms per frame versus 4.7 ms for full-frame search. Scene brightness (+45, x1.5, -35) changes values by < 0.003.
#
# The button path remains as a fallback, now restricted to the central strip of the fixed dialog
# (the button sits at x 403 in all references).
GOLDEN_OK_END_LEFT_TEMPLATE = 'images/golden_ok_end_left.png'
GOLDEN_OK_END_RIGHT_TEMPLATE = 'images/golden_ok_end_right.png'
GOLDEN_BAR_LEFT_X = 260       # Client x of the left bar start
GOLDEN_BAR_RIGHT_X = 539      # Client x of the right bar end
GOLDEN_BAR_END_ANCHOR = (6, 17)   # Column in the template that must align with LEFT_X/RIGHT_X
GOLDEN_BAR_END_DX = 8         # Search range in x per side (px)
GOLDEN_BAR_END_NCC_MIN = 0.70
GOLDEN_BAR_END_DY_MAX = 6     # both ends at (almost) the same height
GOLDEN_PANEL_Y = (160, 445)   # y-range of the fixed dialog frame (client)
GOLDEN_OK_X = 403             # Client x of the button center (all references)
GOLDEN_OK_X_HALF = 73         # half-width of the middle strip for the button

# -- Third path: FIXED GEOMETRY (v1.6.13, at the user's request) -------------
#
# "If the images are not recognizable enough, make the fixed coordinates better."
# The dialog frame is fixed, so the button can also be found WITHOUT a template:
# (1) the frame is there -- a bright vertical line at client x 49..53 and a bright horizontal line at y 149..153;
# (2) the OK bar is the brightest FLAT row in the two columns left and right of the center
# (x 270..340 and 460..530), where a name tag never hangs. The click lands at (400, y) --
# the bar is 280 px wide, and every point on it is the button.
#
# WHY NOT BLIND: without the frame check, a fixed click would hit the world while the server response
# was not yet there -- the character would run away (report 2026-07-22). The frame is the cheapest hard
# evidence that a dialog is really present.
#
# MEASURED (five dialogs, 25 negatives): frame contrast left 41.6..55.1 / top 37.1..55.5 against at most 1.6 / 2.7 without a dialog.
# Bar: contrast 19.7..41.9 with std <= 9.7; without a dialog it is either textured (std >= 49) or low-contrast (<= 8.9).
# The options window carries the same frame -- it is handled before that via the black corner (detect_daily_reward).
GOLDEN_FRAME_LEFT_X = (47, 56)       # Search area of the left frame line
GOLDEN_FRAME_TOP_Y = (147, 156)      # Search area of the upper frame line
GOLDEN_FRAME_MIN = 15.0              # Minimum contrast per frame line
GOLDEN_BAND_COLS = ((270, 340), (460, 530))   # name-tag-free columns
GOLDEN_BAND_Y = (175, 425)           # y search range of the bar center
GOLDEN_BAND_MIN_CONTRAST = 12.0
GOLDEN_BAND_MAX_STD = 14.0
GOLDEN_BAR_CENTER_X = 400            # Click-x on the bar

_golden_ok_cache = None
_golden_end_cache = None


def _golden_ok_template():
    """The OK button template as a grayscale array (cached, soft). None = off."""
    global _golden_ok_cache
    if _golden_ok_cache is not None:
        return _golden_ok_cache
    if np is None:
        return None
    tmpl = cv.imread(resource_path(GOLDEN_OK_TEMPLATE), cv.IMREAD_GRAYSCALE)
    if tmpl is None:
        return None
    _golden_ok_cache = tmpl
    return _golden_ok_cache


def _golden_end_templates():
    """The two end templates as grayscale (cached, soft). None = off."""
    global _golden_end_cache
    if _golden_end_cache is not None:
        return _golden_end_cache
    if np is None:
        return None
    left = cv.imread(resource_path(GOLDEN_OK_END_LEFT_TEMPLATE),
                     cv.IMREAD_GRAYSCALE)
    right = cv.imread(resource_path(GOLDEN_OK_END_RIGHT_TEMPLATE),
                      cv.IMREAD_GRAYSCALE)
    if left is None or right is None:
        return None
    _golden_end_cache = (left, right)
    return _golden_end_cache


def _match_end(gray, tmpl, anchor_x, anchor_col):
    """Search one bar end in its narrow column -> ``(score, y_center)``.

    ``anchor_x`` is the client column on which ``anchor_col`` of the template must
    lie; the search spans +-GOLDEN_BAR_END_DX in x and the full dialog frame in y.
    ``(0.0, None)`` when the crop does not fit in the image.
    """
    th, tw = tmpl.shape[0], tmpl.shape[1]
    x0 = anchor_x - anchor_col - GOLDEN_BAR_END_DX
    x1 = anchor_x - anchor_col + tw + GOLDEN_BAR_END_DX
    y0, y1 = GOLDEN_PANEL_Y
    if x0 < 0 or y0 < 0 or x1 > gray.shape[1] or y1 > gray.shape[0]:
        return (0.0, None)
    col = gray[y0:y1, x0:x1]
    if col.shape[0] <= th or col.shape[1] <= tw:
        return (0.0, None)
    res = cv.matchTemplate(col, tmpl, cv.TM_CCOEFF_NORMED)
    _mn, score, _mnl, loc = cv.minMaxLoc(res)
    return (float(score), int(y0 + loc[1] + th // 2))


def golden_bar_ends_find(gray):
    """Both ends of the OK bar -> ``(found, score, point, detail)``.

    ``score`` is the weaker of the two ends (both must contribute), ``point`` is the
    click center ``(GOLDEN_OK_X, y)`` in client coordinates, and ``detail`` is a dict
    with ``links``/``rechts``/``dy`` for diagnostics.
    Pure, never throws; missing templates -> ``(False, 0.0, None, {})``.
    """
    tm = _golden_end_templates()
    if tm is None or gray is None:
        return (False, 0.0, None, {})
    try:
        s_l, y_l = _match_end(gray, tm[0], GOLDEN_BAR_LEFT_X,
                              GOLDEN_BAR_END_ANCHOR[0])
        s_r, y_r = _match_end(gray, tm[1], GOLDEN_BAR_RIGHT_X,
                              GOLDEN_BAR_END_ANCHOR[1])
        score = min(s_l, s_r)
        detail = {'links': round(s_l, 3), 'rechts': round(s_r, 3),
                  'dy': (abs(y_l - y_r) if None not in (y_l, y_r) else None)}
        if y_l is None or y_r is None or score < GOLDEN_BAR_END_NCC_MIN:
            return (False, score, None, detail)
        if abs(y_l - y_r) > GOLDEN_BAR_END_DY_MAX:
            return (False, score, None, detail)
        return (True, score, (GOLDEN_OK_X, (y_l + y_r) // 2), detail)
    except Exception:
        return (False, 0.0, None, {})


def golden_panel_frame(gray):
    """Contrast of the two fixed frame lines -> ``(left, top)``.

    Each line: brightest column/row in the search area, measured against the mean of
    four pixels before and after it. Without a dialog, both are near 0.
    Never throws -> ``(0.0, 0.0)`` if in doubt.
    """
    try:
        y0, y1 = GOLDEN_PANEL_Y
        if gray is None or gray.shape[0] <= y1 + 40 or gray.shape[1] < 600:
            return (0.0, 0.0)
        g = gray.astype('float32')
        col = g[y0 + 10:y1 - 15, :].mean(axis=0)
        row = g[:, 60:600].mean(axis=1)
        lo, hi = GOLDEN_FRAME_LEFT_X
        links = max(float(col[x] - (col[x - 4] + col[x + 4]) / 2)
                    for x in range(lo, hi))
        lo, hi = GOLDEN_FRAME_TOP_Y
        oben = max(float(row[y] - (row[y - 4] + row[y + 4]) / 2)
                   for y in range(lo, hi))
        return (links, oben)
    except Exception:
        return (0.0, 0.0)


def golden_bar_band_find(gray):
    """The OK bar as the brightest FLAT row in the name-tag-free columns.

    :return: ``(y, contrast, std)`` of the best row -- the caller checks it against
        GOLDEN_BAND_MIN_CONTRAST / GOLDEN_BAND_MAX_STD. Never throws ->
        ``(None, 0.0, 999.0)`` if in doubt.
    """
    try:
        y0, y1 = GOLDEN_BAND_Y
        if gray is None or gray.shape[0] <= y1 + 31 or gray.shape[1] < 540:
            return (None, 0.0, 999.0)
        g = gray.astype('float32')
        cols = [g[:, a:b] for a, b in GOLDEN_BAND_COLS]
        prof = sum(c.mean(axis=1) for c in cols) / len(cols)
        # Windowed mean using prefix sums: band = 19 rows around y, background =
        # 18 rows above (y-30..y-13) and below (y+13..y+30).
        csum = np.concatenate(([0.0], np.cumsum(prof, dtype='float64')))

        def fenster(a_off, b_off):
            ys = np.arange(y0, y1)
            return (csum[ys + b_off] - csum[ys + a_off]) / float(b_off - a_off)

        band = fenster(-9, 10)
        umfeld = (fenster(-30, -12) + fenster(13, 31)) / 2.0
        kontrast = band - umfeld
        i = int(np.argmax(kontrast))
        y = y0 + i
        std = float(np.hstack([c[y - 6:y + 7] for c in cols]).std())
        return (int(y), float(kontrast[i]), std)
    except Exception:
        return (None, 0.0, 999.0)


def golden_fixed_geometry_find(gray):
    """Path 3: frame present AND bar found -> ``(found, score, point, detail)``.

    ``score`` is the bar contrast, ``point`` = (GOLDEN_BAR_CENTER_X, y).
    """
    links, oben = golden_panel_frame(gray)
    detail = {'rahmen_links': round(links, 1), 'rahmen_oben': round(oben, 1)}
    if links < GOLDEN_FRAME_MIN or oben < GOLDEN_FRAME_MIN:
        return (False, 0.0, None, detail)
    # The OPTIONS window has the same frame and also flat bars -- its signature is
    # the black image corner (like detect_daily_reward). It is NOT a confirmation dialog;
    # in the fishing loop it is handled earlier, but this function must reject it cleanly on its own.
    try:
        if not gray[10:15, 10:15].any():
            detail['optionsfenster'] = True
            return (False, 0.0, None, detail)
    except Exception:
        pass
    y, kontrast, std = golden_bar_band_find(gray)
    detail.update({'leiste_y': y, 'leiste_kontrast': round(kontrast, 1),
                   'leiste_std': round(std, 1)})
    if y is None or kontrast < GOLDEN_BAND_MIN_CONTRAST \
            or std > GOLDEN_BAND_MAX_STD:
        return (False, kontrast, None, detail)
    return (True, kontrast, (GOLDEN_BAR_CENTER_X, y), detail)


def golden_confirm_find(image_bgr):
    """Search the OK button of the confirmation dialog -- three paths in sequence.

    :return: ``(found, score, point)`` -- ``point`` is the button center in client
        coordinates (the click point), ``None`` if not found.
        ``score`` is the NCC value of the end search or button match (the geometry
        path has no NCC; its value is supplied by :func:`golden_confirm_scores`).
        Pure, headless-testable, never throws; missing templates/numpy or too-small
        frame -> no click (the safe direction).
    """
    if image_bgr is None or np is None:
        return (False, 0.0, None)
    try:
        img = np.asarray(image_bgr)
        if img.ndim != 3 or img.shape[2] < 3:
            return (False, 0.0, None)
        gray = cv.cvtColor(img[:, :, :3], cv.COLOR_BGR2GRAY)

        # PATH 1 -- the bar ends (0.15 ms, insensitive to a name tag over "OK";
        # see constant docs).
        found, score, point, _detail = golden_bar_ends_find(gray)
        if found:
            return (True, score, point)

        # PATH 2 -- fixed geometry: frame present + brightest flat row in the
        # name-tag-free columns (no template; see constant docs).
        found, _k, point, _detail = golden_fixed_geometry_find(gray)
        if found:
            return (True, score, point)

        # PATH 3 -- the button itself, in the center strip of the fixed dialog.
        tmpl = _golden_ok_template()
        if tmpl is None:
            return (False, score, None)
        th, tw = tmpl.shape[0], tmpl.shape[1]
        sx0 = max(0, GOLDEN_OK_X - GOLDEN_OK_X_HALF)
        sx1 = min(gray.shape[1], GOLDEN_OK_X + GOLDEN_OK_X_HALF)
        strip = gray[:, sx0:sx1]
        if strip.shape[0] <= th or strip.shape[1] <= tw:
            return (False, score, None)
        res = cv.matchTemplate(strip, tmpl, cv.TM_CCOEFF_NORMED)
        _mn, knob, _mnl, loc = cv.minMaxLoc(res)
        score = max(score, float(knob))
        if float(knob) < GOLDEN_OK_NCC_MIN:
            return (False, score, None)
        cx, cy = int(sx0 + loc[0] + tw // 2), int(loc[1] + th // 2)
        # Bar check: both flanks flat + plausibly bright.
        for x0, x1 in ((cx - 48, cx - 24), (cx + 24, cx + 48)):
            y0, y1 = cy - 7, cy + 8
            if y0 < 0 or x0 < 0 or y1 > gray.shape[0] or x1 > gray.shape[1]:
                return (False, score, None)
            strip = gray[y0:y1, x0:x1].astype('float32')
            lo, hi = GOLDEN_OK_BAR_MEAN
            if not (lo <= float(strip.mean()) <= hi):
                return (False, score, None)
            if float(strip.std()) > GOLDEN_OK_BAR_STD_MAX:
                return (False, score, None)
        return (True, score, (cx, cy))
    except Exception:
        return (False, 0.0, None)


def golden_confirm_scores(image_bgr):
    """All partial values of the detection for one diagnostic line -> Dict.

    ``knopf`` = best NCC of the OK button in the center strip, ``links``/``rechts`` =
    the ends, ``dy`` = their vertical offset. Only for logging when an expected dialog
    was NOT found -- so the next report can decide whether it was "not recognized"
    versus "clicked but not accepted". Never throws.
    """
    out = {'knopf': None, 'links': None, 'rechts': None, 'dy': None,
           'rahmen_links': None, 'rahmen_oben': None}
    if image_bgr is None or np is None:
        return out
    try:
        img = np.asarray(image_bgr)
        gray = cv.cvtColor(img[:, :, :3], cv.COLOR_BGR2GRAY)
        _f, _s, _p, detail = golden_bar_ends_find(gray)
        out.update({k: detail.get(k) for k in ('links', 'rechts', 'dy')})
        _f, _s, _p, geo = golden_fixed_geometry_find(gray)
        out.update(geo)
        tmpl = _golden_ok_template()
        if tmpl is not None:
            sx0 = max(0, GOLDEN_OK_X - GOLDEN_OK_X_HALF)
            sx1 = min(gray.shape[1], GOLDEN_OK_X + GOLDEN_OK_X_HALF)
            res = cv.matchTemplate(gray[:, sx0:sx1], tmpl, cv.TM_CCOEFF_NORMED)
            out['knopf'] = round(float(cv.minMaxLoc(res)[1]), 3)
    except Exception:
        pass
    return out


def golden_confirm_present(image_bgr):
    """``True`` iff the golden fish confirmation dialog is present in the frame."""
    return golden_confirm_find(image_bgr)[0]


class FishingDetectMixin:
    """Pure detection methods (fish / minigame / daily reward).

    Contains NO own attributes and NO ``__init__`` -- all state (``needle_img``,
    ``FISH_RANGE``, ``fish_pos_x`` ...) continues to live on
    :class:`fishingbot.FishingBot`. Pure behavior, mixed in via MRO.
    """

    def _note_detect(self, grund, conf=None, dist=None, velo=None,
                     ref_alter=None):
        """Records WHY ``detect`` decided the way it did -- pure diagnostics for the
        click line in the debug log, NO behavior change.

        Never throws: if writing fails, only the additional fields are missing from the log.
        """
        try:
            self._last_detect_info = {
                'grund': grund, 'conf': conf, 'dist': dist,
                'velo': velo, 'ref_alter': ref_alter,
            }
        except Exception:
            pass

    def detect(self, haystack_img):

        # Match the needle_image with the haystack image (robust: a mismatched
        # capture must NOT trigger a cv2 crash -> then "no fish" (None)).
        ok, max_val, max_loc = _match_template_max(haystack_img, self.needle_img)
        if not ok:
            self._note_detect('template-missing')
            return None

        # needle_image's dimensions
        needle_w = self.needle_img.shape[1]
        needle_h = self.needle_img.shape[0]

        # get the position of the match image
        top_left = max_loc
        bottom_right = (top_left[0] + needle_w, top_left[1] + needle_h)

        # Draw the circle of the fish limits
        cv.circle(haystack_img,
                (int(haystack_img.shape[1] / 2), int(haystack_img.shape[0] / 2)),
                self.FISH_RANGE, color=(0, 0, 255), thickness=1)

        # Only the max level of match is greater than 0.5
        if max_val > 0.5:
            pos_x = (top_left[0] + bottom_right[0])/2
            pos_y = (top_left[1] + bottom_right[1])/2

            if self.fish_last_time:
                dist = math.sqrt((pos_x - self.fish_pos_x)**2 + (self.fish_pos_y - pos_y)**2)
                cv.rectangle(haystack_img, top_left, bottom_right,
                            color=(0, 255, 0), thickness=2, lineType=cv.LINE_4)

                # Calculate the fish velocity
                velo = dist/(time() - self.fish_last_time)

                if velo == 0.0:
                    # The found spot lies EXACTLY on the reference point -> target rests.
                    self._note_detect('resting', conf=max_val, dist=dist,
                                      velo=velo,
                                      ref_alter=time() - self.fish_last_time)
                    return (pos_x, pos_y, True)
                elif velo >= 150:

                    # With this velocity the fish position will be predicted.

                    pro = self.FISH_VELO_PREDICT / dist
                    destiny_x = int(pos_x + (pos_x - self.fish_pos_x) * pro)
                    destiny_y = int(pos_y + (pos_y - self.fish_pos_y) * pro)

                    # Draw the prediction line

                    cv.line(haystack_img, (int(pos_x), int(pos_y)),
                            (destiny_x, destiny_y), (0, 255, 0),  thickness=3)

                    # Lead: the click is deliberately placed FISH_VELO_PREDICT px beside the
                    # match, in the direction of the offset from the reference point.
                    self._note_detect('lead', conf=max_val, dist=dist,
                                      velo=velo,
                                      ref_alter=time() - self.fish_last_time)
                    return (destiny_x, destiny_y, False)

            # get the fish position and the time

            had_reference = bool(self.fish_last_time)
            self.fish_pos_x = pos_x
            self.fish_pos_y = pos_y
            self.fish_last_time = time()
            # Fish found, but no click: either first find of this round or dead zone
            # (0 < velo < 150). The reference point was updated.
            self._note_detect('deadzone' if had_reference else 'first-fish',
                              conf=max_val)
            return None

        self._note_detect('no-fish', conf=max_val)
        return None

    def detect_minigame(self, haystack_img):
        # Robust against shape/type deviations of the capture (no more crash).
        ok, max_val, _ = _match_template_max(haystack_img, self.needle_img_clock)
        if ok and max_val > self._best_minigame_conf:
            self._best_minigame_conf = max_val
        return ok and max_val > 0.9

    def detect_daily_reward(self, image):
        # Daily-reward popup leaves the top-left 5x5 patch all-black: True iff
        # every BGR channel in image[10:15, 10:15] is 0. A single numpy reduction
        # over the 75-element slice (with numpy's internal short-circuit) replaces
        # the old 25-step Python loop + per-pixel int() casts -- identical result.
        return not image[10:15, 10:15, :3].any()

    def detect_golden_confirm(self, image):
        """``(found, score, point)`` of the confirmation dialog's OK button.

        Thin mixin wrapper around :func:`golden_confirm_find` (module function so it
        stays testable headless without a FishingBot instance). ``point`` is the FOUND
        button center (client) -- the dialog is not at a fixed position, and the click
        goes to the match; see the constant docs above.
        """
        return golden_confirm_find(image)

    def golden_confirm_diag(self, image):
        """Partial values of the detection used for the diagnostics line (see
        :func:`golden_confirm_scores`). Never throws."""
        return golden_confirm_scores(image)
