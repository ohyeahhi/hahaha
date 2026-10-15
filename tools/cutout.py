"""Cut clay figures out of a plain-backdrop photo into transparent PNG sprites.

usage: python tools/cutout.py <photo> <outdir> <prefix> [max_height]

Works for the 동글이 reference photos: one seamless paper backdrop, soft floor
shadows, big round heads. Steps:
  1. fit a smooth backdrop to the border (handles vignette)
  2. find figures by colour difference, weighting chroma over lightness so
     floor shadows (mostly darker, not yellower) stay out
  3. split blobs that hold two touching figures at their narrowest column
  4. GrabCut each figure, then fill bites in the head by fitting a circle
  5. trim leftover floor shadow under the feet, feather the edge, crop
"""
import sys
import cv2
import numpy as np

src, outdir, prefix = sys.argv[1], sys.argv[2], sys.argv[3]
max_h = int(sys.argv[4]) if len(sys.argv) > 4 else 0

bgr = cv2.imread(src, cv2.IMREAD_COLOR)
h, w = bgr.shape[:2]
lab = cv2.cvtColor(bgr, cv2.COLOR_BGR2LAB).astype(np.float32)

# 1. backdrop
yy, xx = np.mgrid[0:h, 0:w]
border = np.zeros((h, w), bool)
b = 24
border[:b], border[-b:], border[:, :b], border[:, -b:] = True, True, True, True
fx, fy = xx.ravel() / w, yy.ravel() / h
X = np.stack([np.ones(h * w), fx, fy, fx * fx, fy * fy, fx * fy], 1)
bg = np.zeros_like(lab)
for c in range(3):
    coef, *_ = np.linalg.lstsq(X[border.ravel()], lab[..., c].ravel()[border.ravel()], rcond=None)
    bg[..., c] = (X @ coef).reshape(h, w)
diff = lab - bg

# 2. figures
d = np.sqrt((diff[..., 0] * 0.35) ** 2 + diff[..., 1] ** 2 + (diff[..., 2] * 1.3) ** 2)
dark = diff[..., 0] < -40
fg = ((d > 7) | dark).astype(np.uint8)
fg = cv2.morphologyEx(fg, cv2.MORPH_OPEN, np.ones((5, 5), np.uint8))
fg = cv2.morphologyEx(fg, cv2.MORPH_CLOSE, np.ones((9, 9), np.uint8))
n, lbl, stats, _ = cv2.connectedComponentsWithStats(fg)

# 3. split touching pairs
next_label = n
for i in range(1, n):
    x, y, bw, bh, area = stats[i]
    if area < 0.008 * h * w or bw < 1.3 * bh:
        continue
    cols = (lbl[y:y + bh, x:x + bw] == i).sum(0)
    lo, hi = int(bw * 0.3), int(bw * 0.7)
    cut = x + lo + int(np.argmin(cols[lo:hi]))
    region = lbl == i
    right = region & (xx >= cut)
    lbl[right] = next_label
    next_label += 1

figs = []
for i in range(1, next_label):
    ys, xs = np.where(lbl == i)
    if len(ys) < 0.008 * h * w:
        continue
    figs.append((i, xs.min(), ys.min(), xs.max() + 1, ys.max() + 1))
figs.sort(key=lambda f: ((f[2] + f[4]) // 2 // (h // 3), f[1]))  # rows, then left to right
print('figures', len(figs))


def circle_from(p1, p2, p3):
    ax, ay = p1; bx, by = p2; cx, cy = p3
    dd = 2 * (ax * (by - cy) + bx * (cy - ay) + cx * (ay - by))
    if abs(dd) < 1e-6:
        return None
    ux = ((ax * ax + ay * ay) * (by - cy) + (bx * bx + by * by) * (cy - ay) + (cx * cx + cy * cy) * (ay - by)) / dd
    uy = ((ax * ax + ay * ay) * (cx - bx) + (bx * bx + by * by) * (ax - cx) + (cx * cx + cy * cy) * (bx - ax)) / dd
    return ux, uy, np.hypot(ax - ux, ay - uy)


rng = np.random.default_rng(1)
for k, (li, x0, y0, x1, y1) in enumerate(figs):
    pad = int(0.3 * max(x1 - x0, y1 - y0))  # the blob can miss a low-contrast head edge
    X0, Y0, X1, Y1 = max(0, x0 - pad), max(0, y0 - pad), min(w, x1 + pad), min(h, y1 + pad)
    crop = bgr[Y0:Y1, X0:X1].copy()
    dd, dk, lb = d[Y0:Y1, X0:X1], dark[Y0:Y1, X0:X1], lbl[Y0:Y1, X0:X1]
    own = lb == li

    # 4. GrabCut
    m = np.full(dd.shape, cv2.GC_PR_BGD, np.uint8)
    m[dd > 4] = cv2.GC_PR_FGD
    m[(dd > 9) & own] = cv2.GC_FGD
    m[dk & own] = cv2.GC_FGD
    # only call pixels certain background when they are well away from this figure
    near = cv2.distanceTransform((~own).astype(np.uint8), cv2.DIST_L2, 5) < 0.06 * max(x1 - x0, y1 - y0)
    m[(dd < 2) & ~near] = cv2.GC_BGD
    m[(lb > 0) & ~own] = cv2.GC_BGD
    m[:4], m[-4:], m[:, :4], m[:, -4:] = cv2.GC_BGD, cv2.GC_BGD, cv2.GC_BGD, cv2.GC_BGD
    bgd, fgd = np.zeros((1, 65)), np.zeros((1, 65))
    cv2.grabCut(crop, m, None, bgd, fgd, 6, cv2.GC_INIT_WITH_MASK)
    alpha = np.where((m == cv2.GC_FGD) | (m == cv2.GC_PR_FGD), 255, 0).astype(np.uint8)
    cc, cl, st, _ = cv2.connectedComponentsWithStats(alpha)
    if cc > 1:
        alpha = np.where(cl == 1 + np.argmax(st[1:, 4]), 255, 0).astype(np.uint8)

    # head = best circle through the upper outline (RANSAC), then fill it in
    cnts, _ = cv2.findContours(alpha, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_NONE)
    pts = max(cnts, key=cv2.contourArea)[:, 0, :].astype(np.float64)
    top, bottom = pts[:, 1].min(), pts[:, 1].max()
    fig_w = pts[:, 0].max() - pts[:, 0].min()
    upper = pts[pts[:, 1] < top + 0.5 * (bottom - top)]
    best, best_in = None, 0
    for _ in range(600):
        c = circle_from(*upper[rng.choice(len(upper), 3, replace=False)])
        if not c or not (0.25 * fig_w < c[2] < 0.62 * fig_w):
            continue
        inl = np.abs(np.hypot(upper[:, 0] - c[0], upper[:, 1] - c[1]) - c[2]) < 2.0
        if inl.sum() > best_in:
            best, best_in = c, inl.sum()
    if best:
        disc = np.zeros_like(alpha)
        cv2.circle(disc, (int(round(best[0])), int(round(best[1]))), int(best[2] - 1), 255, -1)
        disc[int(best[1]):] = 0  # heads are a little wider than tall: only mend the upper half
        alpha = alpha | disc

    # fill enclosed holes
    ff = alpha.copy()
    cv2.floodFill(ff, np.zeros((ff.shape[0] + 2, ff.shape[1] + 2), np.uint8), (0, 0), 255)
    alpha = alpha | cv2.bitwise_not(ff)

    # 5. floor shadow: it spreads sideways along the floor while feet are round, so in the
    #    bottom band keep only what sits under the figure's own footprint
    ys, xs = np.where(alpha > 0)
    fig_h = ys.max() - ys.min()
    band_top = int(ys.max() - 0.15 * fig_h)
    # footprint: the narrower of the spans just above the floor and a little higher up
    spans = [np.where(alpha[int(ys.max() - f * fig_h)] > 0)[0] for f in (0.1, 0.16)]
    spans = [c for c in spans if len(c)]
    cols = np.array([max(c.min() for c in spans), min(c.max() for c in spans)]) if spans else np.array([])
    if len(cols):
        margin = int(0.03 * (xs.max() - xs.min()))
        fl, fr = cols.min() - margin, cols.max() + margin
        alpha[band_top:, :max(0, fl)] = 0
        alpha[band_top:, fr + 1:] = 0
    # what is left of the shadow is a thin flat sliver; feet are round and much taller,
    # so a vertical opening in the bottom band removes the sliver and keeps the feet
    kh = max(3, int(0.04 * fig_h))
    band = alpha[band_top:].copy()
    alpha[band_top:] = cv2.morphologyEx(band, cv2.MORPH_OPEN, np.ones((kh, 1), np.uint8))
    alpha = cv2.morphologyEx(alpha, cv2.MORPH_OPEN, np.ones((5, 5), np.uint8))
    cc, cl, st, _ = cv2.connectedComponentsWithStats(alpha)
    if cc > 1:
        alpha = np.where(cl == 1 + np.argmax(st[1:, 4]), 255, 0).astype(np.uint8)

    alpha = cv2.erode(alpha, np.ones((3, 3), np.uint8))
    alpha = cv2.GaussianBlur(alpha, (0, 0), 0.9)
    ys, xs = np.where(alpha > 8)
    rgba = cv2.cvtColor(crop, cv2.COLOR_BGR2BGRA)
    rgba[..., 3] = alpha
    rgba = rgba[ys.min():ys.max() + 1, xs.min():xs.max() + 1]
    if max_h and rgba.shape[0] > max_h:
        s = max_h / rgba.shape[0]
        rgba = cv2.resize(rgba, (int(rgba.shape[1] * s), max_h), interpolation=cv2.INTER_AREA)
    out = f'{outdir}/{prefix}-{k + 1}.png'
    cv2.imwrite(out, rgba, [cv2.IMWRITE_PNG_COMPRESSION, 9])
    print(out, rgba.shape[1], 'x', rgba.shape[0])
