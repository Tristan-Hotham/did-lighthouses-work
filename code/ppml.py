"""Poisson pseudo-maximum likelihood with two sets of fixed effects and site-clustered
standard errors. Small and dependency-light (numpy only), so it can be checked line by line.

Model: E[y] = exp(a[f1] + g[f2] + X b)
"""
import numpy as np


def _drop_uninformative(y, f1, f2):
    keep = np.ones(len(y), bool)
    while True:
        s1 = np.bincount(f1[keep], y[keep], minlength=f1.max() + 1)
        s2 = np.bincount(f2[keep], y[keep], minlength=f2.max() + 1)
        new = keep & (s1[f1] > 0) & (s2[f2] > 0)
        if new.sum() == keep.sum():
            return keep
        keep = new


def _reindex(v):
    _, inv = np.unique(v, return_inverse=True)
    return inv


def _demean(X, w, f1, f2, n1, n2, tol=1e-10, maxit=2000):
    """Weighted two-way within transformation by alternating projections."""
    Z = X.copy()
    sw1 = np.bincount(f1, w, n1)
    sw2 = np.bincount(f2, w, n2)
    for _ in range(maxit):
        old = Z.copy()
        for f, sw, n in ((f1, sw1, n1), (f2, sw2, n2)):
            for k in range(Z.shape[1]):
                m = np.bincount(f, w * Z[:, k], n) / sw
                Z[:, k] -= m[f]
        if np.max(np.abs(Z - old)) < tol:
            break
    return Z


def fit(y, X, f1, f2, cluster, maxit=5000, tol=1e-9):
    y = np.asarray(y, float)
    X = np.asarray(X, float)
    if X.ndim == 1:
        X = X[:, None]
    keep = _drop_uninformative(y, _reindex(f1), _reindex(f2))
    y, X = y[keep], X[keep]
    f1, f2, cl = _reindex(np.asarray(f1)[keep]), _reindex(np.asarray(f2)[keep]), _reindex(np.asarray(cluster)[keep])
    n1, n2, k = f1.max() + 1, f2.max() + 1, X.shape[1]
    # drop regressors with no variation in the kept sample
    ok = np.array([X[:, j].std() > 0 for j in range(k)])
    b = np.zeros(k)
    a = np.log(np.bincount(f1, y, n1) / np.bincount(f1, minlength=n1))
    g = np.zeros(n2)
    sy1, sy2 = np.bincount(f1, y, n1), np.bincount(f2, y, n2)
    ll_old = -np.inf
    for it in range(maxit):
        xb = X[:, ok] @ b[ok]
        mu = np.exp(a[f1] + g[f2] + xb)
        a += np.log(sy1 / np.bincount(f1, mu, n1))
        mu = np.exp(a[f1] + g[f2] + xb)
        g += np.log(sy2 / np.bincount(f2, mu, n2))
        mu = np.exp(a[f1] + g[f2] + xb)
        if ok.any():
            Xk = X[:, ok]
            Xt = _demean(Xk, mu, f1, f2, n1, n2, tol=1e-8, maxit=200) if it % 5 == 0 or it < 3 else Xt
            grad = Xk.T @ (y - mu)
            H = Xt.T @ (Xt * mu[:, None])
            step = np.linalg.solve(H, grad)
            b[ok] += np.clip(step, -2, 2)
        ll = np.sum(y * np.log(np.where(mu > 0, mu, 1)) - mu)
        if abs(ll - ll_old) < tol * (1 + abs(ll)) and it > 5:
            break
        ll_old = ll
    mu = np.exp(a[f1] + g[f2] + X[:, ok] @ b[ok])
    Xt = _demean(X[:, ok], mu, f1, f2, n1, n2)
    bread = np.linalg.inv(Xt.T @ (Xt * mu[:, None]))
    sc = Xt * (y - mu)[:, None]
    G = cl.max() + 1
    S = np.zeros((G, ok.sum()))
    for j in range(ok.sum()):
        S[:, j] = np.bincount(cl, sc[:, j], G)
    meat = S.T @ S * G / (G - 1)
    V = bread @ meat @ bread
    se = np.full(k, np.nan)
    se[ok] = np.sqrt(np.diag(V))
    b[~ok] = np.nan
    return dict(b=b, se=se, n=int(len(y)), clusters=int(G), iters=it + 1, events=float(y.sum()))
