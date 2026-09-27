"""Scoring math. The per-question rules reproduce the legacy scorers exactly
(score.py, papers32_score.py, anyjev_score.py); everything else is additive:
baselines, bootstrap CIs, calibration and paired tests."""
import math
import random
from collections import Counter

from .battery import options

BORDER = (0.45, 0.55)


# ---------------------------------------------------------------- normalize
def normalize(ans, q):
    """Wire-format answer -> {'label', 'value', 'probs'} (probs keyed like battery.options)."""
    t = q["type"]
    if t == "choice":
        probs = ans.get("probabilities")
        return {"label": ans["choice"], "probs": {k: float(v) for k, v in probs.items()} if probs else None}
    if t == "score":
        probs = ans.get("probabilities")
        return {"value": float(ans["score"]), "probs": {str(k): float(v) for k, v in probs.items()} if probs else None}
    if t == "noul":
        return {"value": float(ans["noul"])}
    raise ValueError(t)


def level(value, n):
    return min(n - 1, max(0, round(value)))  # legacy used round() too (banker's rounding)


def point(q, pred, gt):
    """Legacy per-question credit: choice exact, score exact=1 / off-by-one=0.5, noul thr 0.5."""
    t = q["type"]
    if t == "choice":
        return float(pred["label"] == gt)
    if t == "score":
        d = abs(level(pred["value"], len(q["criteria"])) - gt)
        return 1.0 if d == 0 else (0.5 if d == 1 else 0.0)
    return float((1 if pred["value"] >= 0.5 else 0) == gt)


def exact(q, pred, gt):
    """Strict hit (score counts only exact level), used for paired tests."""
    return point(q, pred, gt) == 1.0


# ---------------------------------------------------------------- baselines
def majority_baseline(qs, cases):
    """Oracle majority class per question (fitted on the test GT itself: an upper
    bound for any constant predictor). Returns {question: points}."""
    out = {}
    for name, q in qs.items():
        mode = Counter(c.gt[name] for c in cases).most_common(1)[0][0]
        pred = ({"label": mode} if q["type"] == "choice" else {"value": float(mode)})
        out[name] = {"answer": mode, "points": sum(point(q, pred, c.gt[name]) for c in cases)}
    return out


# ---------------------------------------------------------------- stats
def bootstrap_ci(values, iters=2000, seed=0, alpha=0.05):
    if not values:
        return (float("nan"), float("nan"))
    rng = random.Random(seed)
    n = len(values)
    means = sorted(sum(values[rng.randrange(n)] for _ in range(n)) / n for _ in range(iters))
    return means[int(iters * alpha / 2)], means[int(iters * (1 - alpha / 2)) - 1]


def mcnemar(a_hits, b_hits):
    """Exact two-sided McNemar on paired booleans. Returns (b, c, p)."""
    b = sum(1 for x, y in zip(a_hits, b_hits) if x and not y)
    c = sum(1 for x, y in zip(a_hits, b_hits) if y and not x)
    n = b + c
    if n == 0:
        return b, c, 1.0
    k = min(b, c)
    p = 2 * sum(math.comb(n, i) for i in range(k + 1)) / 2 ** n
    return b, c, min(1.0, p)


def spearman(a, b):
    def rank(x):
        idx = sorted(range(len(x)), key=lambda i: x[i])
        r = [0.0] * len(x)
        i = 0
        while i < len(idx):
            j = i
            while j + 1 < len(idx) and x[idx[j + 1]] == x[idx[i]]:
                j += 1
            for k in range(i, j + 1):
                r[idx[k]] = (i + j) / 2 + 1
            i = j + 1
        return r
    ra, rb = rank(a), rank(b)
    ma, mb = sum(ra) / len(ra), sum(rb) / len(rb)
    num = sum((x - ma) * (y - mb) for x, y in zip(ra, rb))
    da = math.sqrt(sum((x - ma) ** 2 for x in ra))
    db = math.sqrt(sum((y - mb) ** 2 for y in rb))
    return num / (da * db) if da > 0 and db > 0 else float("nan")


# ---------------------------------------------------------------- calibration
def calibration(qs, preds, cases):
    """Brier / NLL per question plus pooled top-1 ECE (10 bins).
    Only questions whose model output carries probabilities are included."""
    per_q, conf_hits = {}, []
    for name, q in qs.items():
        briers, nlls = [], []
        for c in cases:
            p = preds.get(c.id)
            if p is None:
                continue
            pr, gt = p[name], c.gt[name]
            if q["type"] == "noul":
                v = min(1.0, max(0.0, pr["value"]))
                briers.append((v - gt) ** 2)
                nlls.append(-math.log(max(1e-6, v if gt == 1 else 1 - v)))
                conf_hits.append((max(v, 1 - v), (v >= 0.5) == (gt == 1)))
            elif pr.get("probs"):
                opts = options(q)
                target = gt if q["type"] == "choice" else str(gt)
                if target not in opts:  # GT outside the option set (see battery.gt_problems)
                    continue
                dist = [pr["probs"].get(o, 0.0) for o in opts]
                s = sum(dist) or 1.0
                dist = [x / s for x in dist]
                briers.append(sum((x - (o == target)) ** 2 for x, o in zip(dist, opts)))
                nlls.append(-math.log(max(1e-6, dist[opts.index(target)])))
                top = max(range(len(opts)), key=lambda i: dist[i])
                conf_hits.append((dist[top], opts[top] == target))
        if briers:
            per_q[name] = {"brier": sum(briers) / len(briers), "nll": sum(nlls) / len(nlls), "n": len(briers)}
    return per_q, ece(conf_hits)


def ece(conf_hits, bins=10):
    if not conf_hits:
        return None
    tot = 0.0
    for b in range(bins):
        lo, hi = b / bins, (b + 1) / bins
        sel = [(c, h) for c, h in conf_hits if lo < c <= hi or (b == 0 and c == 0)]
        if sel:
            tot += len(sel) * abs(sum(c for c, _ in sel) / len(sel) - sum(h for _, h in sel) / len(sel))
    return tot / len(conf_hits)


# ---------------------------------------------------------------- papers cascade
def depth_cascade(pred, skip_t):
    if pred["relevance"]["value"] < skip_t:
        return "skip"
    if pred["depth"]["label"] == "full" and pred["practice"]["value"] >= 0.5:
        return "full"
    return "abstract"


def best_skip_threshold(ids, preds, gts):
    rels = sorted(preds[i]["relevance"]["value"] for i in ids)
    cands = [0.0] + [(a + b) / 2 for a, b in zip(rels, rels[1:])] + [2.0]
    best_t, best_ok = 0.0, -1
    for t in cands:
        ok = sum(depth_cascade(preds[i], t) == gts[i]["depth"] for i in ids)
        if ok > best_ok:
            best_ok, best_t = ok, t
    return best_t


def cascade(ids, preds, gts):
    """Legacy protocol (2-fold, seed 7) + leave-one-out. Returns dict."""
    rng = random.Random(7)
    shuffled = ids[:]
    rng.shuffle(shuffled)
    folds = [shuffled[:len(shuffled) // 2], shuffled[len(shuffled) // 2:]]
    hits = skip_hits = 0
    for i in range(2):
        test, train = folds[i], folds[1 - i]
        t = best_skip_threshold(train, preds, gts)
        for p in test:
            out = depth_cascade(preds[p], t)
            hits += out == gts[p]["depth"]
            skip_hits += gts[p]["depth"] == "skip" and out == "skip"
    loo = loo_skip = 0
    for p in ids:
        t = best_skip_threshold([x for x in ids if x != p], preds, gts)
        out = depth_cascade(preds[p], t)
        loo += out == gts[p]["depth"]
        loo_skip += gts[p]["depth"] == "skip" and out == "skip"
    return {"cv2": hits, "skip_recall_cv2": skip_hits, "loo": loo, "skip_recall_loo": loo_skip,
            "n": len(ids), "n_skip": sum(gts[p]["depth"] == "skip" for p in ids)}
