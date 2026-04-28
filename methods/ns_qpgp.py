from pathlib import Path

import numpy as np
import pandas as pd
import matplotlib.pyplot as plt

from scipy.integrate import cumulative_trapezoid
from scipy.linalg import cho_factor, cho_solve, LinAlgError
from scipy.optimize import minimize
from tqdm import tqdm


# ============================================================
# 1) 数值稳定的 Cholesky
# ============================================================
def stable_cholesky(K, initial_jitter=1e-10, max_tries=8):
    """
    对可能病态的协方差矩阵做稳定 Cholesky 分解。
    若失败则逐步增大 jitter。
    """
    K = np.asarray(K, dtype=float)
    jitter = initial_jitter
    diag_idx = np.diag_indices_from(K)
    base_diag = K[diag_idx].copy()

    for _ in range(max_tries):
        # 只复制一次当前尝试的矩阵，避免 K + jitter * I 的额外大数组构造
        Kj = np.array(K, order="F", copy=True)
        Kj[diag_idx] = base_diag + jitter
        try:
            c, lower = cho_factor(
                Kj,
                lower=True,
                check_finite=False,
                overwrite_a=True
            )
            return c, lower, jitter
        except LinAlgError:
            jitter *= 10.0

    raise LinAlgError("Cholesky decomposition failed even after increasing jitter.")


# ============================================================
# 2) 真实数据读取 / 清洗 / 标准化
# ============================================================
def _coerce_numeric_series(s):
    """
    把可能含有 '<'、空格、逗号等字符的列尽量转成数值。
    """
    s = s.astype(str).str.strip()
    s = s.str.replace(r"^[<≤]\s*", "", regex=True)
    s = s.str.replace(",", "", regex=False)
    return pd.to_numeric(s, errors="coerce")


def load_real_csv(file_path, time_idx=1, flux_idx=4, err_idx=5):
    """
    读取真实数据 CSV，并做基础清洗。

    参数
    ----
    time_idx, flux_idx, err_idx:
        分别是时间列、flux列、误差列的 0-based 列索引。

    返回
    ----
    t, y, yerr, df
    """
    df = pd.read_csv(file_path, header=0, na_values=["-", "--", "nan", "NaN"])

    max_idx = max(time_idx, flux_idx, err_idx)
    if df.shape[1] <= max_idx:
        raise ValueError(
            f"CSV 列数不足：需要至少 {max_idx + 1} 列，但当前只有 {df.shape[1]} 列。"
        )

    t = _coerce_numeric_series(df.iloc[:, time_idx]).to_numpy()
    y = _coerce_numeric_series(df.iloc[:, flux_idx]).to_numpy()
    yerr = _coerce_numeric_series(df.iloc[:, err_idx]).to_numpy()

    mask = np.isfinite(t) & np.isfinite(y) & np.isfinite(yerr) & (yerr > 0)
    t = t[mask]
    y = y[mask]
    yerr = yerr[mask]

    if len(t) < 10:
        raise ValueError("有效数据点太少，无法拟合。")

    order = np.argsort(t)
    t = t[order]
    y = y[order]
    yerr = yerr[order]

    return t, y, yerr, df


def standardize_flux(y, yerr):
    """
    对 flux 做标准化：
        y_norm = (y - mean) / std
        yerr_norm = yerr / std
    """
    y_mean = float(np.nanmean(y))
    y_std = float(np.nanstd(y))

    if not np.isfinite(y_std) or y_std <= 0:
        y_std = 1.0

    y_norm = (y - y_mean) / y_std
    yerr_norm = yerr / y_std

    return y_norm, yerr_norm, y_mean, y_std


def clip_theta_to_bounds(theta, bounds):
    """
    把 theta 裁剪到边界内。
    """
    theta = np.asarray(theta, dtype=float).copy()
    for i, (lo, hi) in enumerate(bounds):
        theta[i] = np.clip(theta[i], lo, hi)
    return theta


def build_period_initial_grid(
    span,
    lower=20.0,
    upper=2000.0,
    fixed_periods=None,
    span_ratios=None,
    use_fixed=True,
    use_span_ratios=True
):
    """
    为多起点重启构造 period_init 候选集。

    参数
    ----
    span : float
        时间跨度
    lower, upper : float
        周期搜索的上下界
    fixed_periods : list or None
        固定的周期候选值列表，None则使用默认值 [770, 1000, 1500]
    span_ratios : list or None
        基于时间跨度的比例列表，None则使用默认值 [0.04, 0.06, 0.08, 0.12, 0.20]
    use_fixed : bool
        是否启用固定周期，False则完全忽略fixed_periods
    use_span_ratios : bool
        是否启用跨度比例，False则完全忽略span_ratios

    返回
    ----
    cands : ndarray
        排序后的候选周期数组
    """
    candidates = []

    if use_fixed:
        if fixed_periods is None:
            fixed_periods = [770, 1000, 1500]
        fixed = np.array(fixed_periods, dtype=float)
        candidates.append(fixed)

    if use_span_ratios:
        if span_ratios is None:
            span_ratios = [0.04, 0.06, 0.08, 0.12, 0.20]
        span_based = np.array([ratio * span for ratio in span_ratios], dtype=float)
        candidates.append(span_based)

    if not candidates:
        return np.array([])

    cands = np.unique(np.clip(np.concatenate(candidates), lower, upper))
    cands.sort()
    return cands


# ============================================================
# 3) 非平稳 quasi-periodic GP
# ============================================================
class NonstationaryQuasiPeriodicGP:
    """
    非平稳 quasi-periodic GP（time-warped / phase-warped 版本）

    模型：
        y_i = m(t_i) + f(t_i) + eps_i
        f ~ GP(0, k(t,t'))

    核函数：
        k(t,t') = sigma_f^2 * exp(-(t-t')^2 / (2 ell_env^2))
                          * exp(-2 sin^2((phi(t)-phi(t'))/2) / w_per^2)

    其中：
        phi(t) = integral_{t0}^t 2*pi / P(s) ds
        log P(t) 用一组 knots + 线性插值表示，并加平滑正则
    """

    def __init__(
        self,
        t,
        y,
        yerr,
        n_knots=10,
        n_phase_grid=1200,
        period_init=150.0,
        period_bounds=(20.0, 2000.0),
        smoothness_weight=0.01,
        prior_weight=1e-5
    ):
        """
        参数
        ----
        t, y, yerr:
            非均匀采样数据
        n_knots:
            log P(t) 的 knot 数量
        n_phase_grid:
            计算相位积分时使用的内部网格密度
        period_init:
            局部周期初值
        period_bounds:
            周期上下界，(lower, upper)
        smoothness_weight:
            对 log P(t) 二阶差分的平滑惩罚系数
        prior_weight:
            对 knots 偏离 period_init 的弱惩罚系数
        """
        self.t = np.asarray(t, dtype=float).ravel()
        self.y = np.asarray(y, dtype=float).ravel()
        self.yerr = np.asarray(yerr, dtype=float).ravel()

        if not (len(self.t) == len(self.y) == len(self.yerr)):
            raise ValueError("t, y, yerr 必须长度一致。")
        if n_knots < 3:
            raise ValueError("n_knots 至少需要 3 个。")

        # ------------------------------------------------------------
        # 加速点：如果输入已经是非降序，就不要重复 argsort
        # ------------------------------------------------------------
        if np.any(np.diff(self.t) < 0):
            order = np.argsort(self.t)
            self.t = self.t[order]
            self.y = self.y[order]
            self.yerr = self.yerr[order]

        self.n = len(self.t)
        self.tmin = float(np.min(self.t))
        self.tmax = float(np.max(self.t))
        self.span = self.tmax - self.tmin

        if self.span <= 0:
            raise ValueError("时间跨度必须大于 0。")

        self.tmean = float(np.mean(self.t))
        self.tstd = float(np.std(self.t))
        if self.tstd <= 0:
            self.tstd = 1.0

        self.n_knots = int(n_knots)
        self.knots = np.linspace(self.tmin, self.tmax, self.n_knots)

        self.n_phase_grid = int(n_phase_grid)
        self.base_phase_grid = np.linspace(self.tmin, self.tmax, self.n_phase_grid)

        self.smoothness_weight = float(smoothness_weight)
        self.prior_weight = float(prior_weight)

        # 周期边界
        lower = float(max(period_bounds[0], 1e-6))
        upper = period_bounds[1]
        if upper is None:
            upper = max(self.span, 10.0 * period_init, 100.0)
        upper = float(max(upper, lower * 1.01))

        self.period_lower = lower
        self.period_upper = upper
        self.period_init = float(np.clip(period_init, self.period_lower * 1.01, self.period_upper * 0.99))
        self._log_period_init = float(np.log(self.period_init))
        self._log_2pi = float(np.log(2.0 * np.pi))

        # 预计算一些在优化里会反复用到的东西
        self._x_train = (self.t - self.tmean) / self.tstd
        self._yerr2 = self.yerr ** 2
        self._y_std = float(np.std(self.y))
        if not np.isfinite(self._y_std) or self._y_std <= 0:
            self._y_std = 1.0
        self._min_yerr = float(np.min(self.yerr))
        self._weighted_y_mean = float(
            np.average(self.y, weights=1.0 / np.maximum(self.yerr, 1e-12) ** 2)
        )

        self._diag_idx_train = np.diag_indices(self.n)
        self._dt_train = np.subtract.outer(self.t, self.t)

        # 训练集专用的相位积分网格：等价于原来的 unique(concat(base_grid, t_sorted))
        self._phase_dense_train = np.unique(np.concatenate([self.base_phase_grid, self.t]))

        # posterior cache：用于 predict() 连续调用时复用
        self._posterior_cache = None

        self.theta0 = self._initial_theta()
        self.bounds = self._build_bounds()

        self.theta_map = None
        self.fit_result = None

    # ----------------------------
    # 参数拆包
    # ----------------------------
    def _unpack_theta(self, theta):
        theta = np.asarray(theta, dtype=float).ravel()
        mu0 = theta[0]
        mu1 = theta[1]
        log_amp = theta[2]
        log_ell_env = theta[3]
        log_w_per = theta[4]
        log_jitter = theta[5]
        logP_knots = theta[6:]
        return mu0, mu1, log_amp, log_ell_env, log_w_per, log_jitter, logP_knots

    # ----------------------------
    # 初值
    # ----------------------------
    def _initial_theta(self):
        y_mean = self._weighted_y_mean
        y_std = self._y_std

        mu0 = y_mean
        mu1 = 0.0

        log_amp = np.log(max(0.5 * y_std, 1e-3))
        log_ell_env = np.log(max(self.span / 3.0, 1.0))
        log_w_per = np.log(1.0)
        log_jitter = np.log(max(np.median(self.yerr) * 0.3, 1e-6))

        logP_knots = np.full(self.n_knots, np.log(self.period_init), dtype=float)

        theta0 = np.concatenate([
            np.array([mu0, mu1, log_amp, log_ell_env, log_w_per, log_jitter], dtype=float),
            logP_knots
        ])
        return theta0

    # ----------------------------
    # 参数边界
    # ----------------------------
    def _build_bounds(self):
        y_std = self._y_std

        bounds = [
            (-10.0 * y_std, 10.0 * y_std),  # mu0
            (-10.0 * y_std, 10.0 * y_std),  # mu1
            (np.log(1e-4 * y_std + 1e-12), np.log(100.0 * y_std + 1e-12)),  # log_amp
            (np.log(max(self.span / 100.0, 1e-2)), np.log(max(self.span * 10.0, 1.0))),  # log_ell_env
            (np.log(0.05), np.log(10.0)),  # log_w_per
            (np.log(max(self._min_yerr * 0.05, 1e-6)), np.log(max(y_std, 1.0))),  # log_jitter
        ]

        logP_lower = np.log(self.period_lower)
        logP_upper = np.log(self.period_upper)
        bounds.extend([(logP_lower, logP_upper)] * self.n_knots)

        return bounds

    # ----------------------------
    # 线性插值得到 log P(t)
    # ----------------------------
    def _log_period(self, t, logP_knots):
        t = np.asarray(t, dtype=float)
        return np.interp(t, self.knots, logP_knots)

    def _period(self, t, logP_knots):
        return np.exp(self._log_period(t, logP_knots))

    # ----------------------------
    # 相位函数
    # ----------------------------
    def _phase_of_times_sorted(self, t_sorted, logP_knots, dense_grid):
        """
        已经排序好的 t_sorted 上计算 phi(t)。
        dense_grid 必须是升序。
        """
        t_sorted = np.asarray(t_sorted, dtype=float).ravel()
        dense_grid = np.asarray(dense_grid, dtype=float).ravel()

        P_dense = self._period(dense_grid, logP_knots)
        omega_dense = 2.0 * np.pi / P_dense

        phi_dense = cumulative_trapezoid(omega_dense, dense_grid, initial=0.0)
        phi_sorted = np.interp(t_sorted, dense_grid, phi_dense)
        return phi_sorted

    def _phase_of_times(self, t, logP_knots, dense_grid=None):
        """
        计算 phi(t) = ∫ 2π / P(s) ds
        这里对时间做数值积分，然后在目标点上插值。

        注意：
        这里不对相位做 mod，保留 unwrapped phase 更利于优化稳定性。
        """
        t = np.asarray(t, dtype=float).ravel()
        order = np.argsort(t)
        t_sorted = t[order]

        if dense_grid is None:
            dense = np.unique(np.concatenate([self.base_phase_grid, t_sorted]))
        else:
            dense = np.asarray(dense_grid, dtype=float).ravel()

        phi_sorted = self._phase_of_times_sorted(t_sorted, logP_knots, dense)
        phi = np.empty_like(phi_sorted)
        phi[order] = phi_sorted
        return phi

    # ----------------------------
    # 核函数（使用已计算好的相位）
    # ----------------------------
    def _kernel_from_phase(self, dt, phi1, phi2, log_amp, log_ell_env, log_w_per):
        """
        k(t,t') = sigma_f^2 * k_env * k_per
        """
        dt = np.asarray(dt, dtype=float)
        phi1 = np.asarray(phi1, dtype=float).ravel()
        phi2 = np.asarray(phi2, dtype=float).ravel()

        amp2 = np.exp(2.0 * log_amp)
        ell_env = np.exp(log_ell_env)
        w_per = np.exp(log_w_per)

        dt_scaled = dt / ell_env
        k_env = np.exp(-0.5 * dt_scaled * dt_scaled)

        dphi = np.subtract.outer(phi1, phi2)
        s = np.sin(0.5 * dphi)
        k_per = np.exp(-2.0 * (s * s) / (w_per * w_per))

        return amp2 * k_env * k_per

    # ----------------------------
    # 均值函数
    # ----------------------------
    def _mean(self, t, mu0, mu1):
        t = np.asarray(t, dtype=float).ravel()
        x = (t - self.tmean) / self.tstd
        return mu0 + mu1 * x

    # ----------------------------
    # 构造/缓存 posterior 所需的训练集分解
    # ----------------------------
    def _posterior_terms(self, theta):
        """
        缓存 theta 对应的训练集 Cholesky 和 alpha。
        predict() 连续调用时可以直接复用，避免重复做一次训练集 factorization。
        """
        theta = np.asarray(theta, dtype=float).ravel()

        cache = self._posterior_cache
        if cache is not None:
            cached_theta = cache.get("theta", None)
            if cached_theta is not None and cached_theta.shape == theta.shape and np.array_equal(cached_theta, theta):
                return cache

        mu0, mu1, log_amp, log_ell_env, log_w_per, log_jitter, logP_knots = self._unpack_theta(theta)

        m_train = mu0 + mu1 * self._x_train
        r = self.y - m_train

        phi_train = self._phase_of_times_sorted(self.t, logP_knots, self._phase_dense_train)

        K_train = self._kernel_from_phase(
            self._dt_train,
            phi_train,
            phi_train,
            log_amp,
            log_ell_env,
            log_w_per
        )

        noise_var = self._yerr2 + np.exp(2.0 * log_jitter)
        K_train = np.array(K_train, copy=True)
        K_train[self._diag_idx_train] += noise_var

        try:
            c, lower, _ = stable_cholesky(K_train, initial_jitter=1e-10)
            alpha = cho_solve((c, lower), r, check_finite=False)
        except LinAlgError:
            # 这里返回 None 由上层决定如何处理
            return None

        cache = {
            "theta": theta.copy(),
            "mu0": mu0,
            "mu1": mu1,
            "log_amp": log_amp,
            "log_ell_env": log_ell_env,
            "log_w_per": log_w_per,
            "log_jitter": log_jitter,
            "logP_knots": logP_knots,
            "m_train": m_train,
            "phi_train": phi_train,
            "K_train": K_train,
            "c": c,
            "lower": lower,
            "alpha": alpha,
        }
        self._posterior_cache = cache
        return cache

    # ----------------------------
    # 负对数后验（= 负对数边际似然 + 正则项）
    # ----------------------------
    def _nll(self, theta):
        theta = np.asarray(theta, dtype=float).ravel()

        if not np.all(np.isfinite(theta)):
            return 1e25

        mu0, mu1, log_amp, log_ell_env, log_w_per, log_jitter, logP_knots = self._unpack_theta(theta)

        m = mu0 + mu1 * self._x_train
        r = self.y - m

        # 训练集的相位和核矩阵使用预计算网格，避免每次 unique/concat/sort
        phi_t = self._phase_of_times_sorted(self.t, logP_knots, self._phase_dense_train)

        K = self._kernel_from_phase(
            self._dt_train,
            phi_t,
            phi_t,
            log_amp,
            log_ell_env,
            log_w_per
        )

        noise_var = self._yerr2 + np.exp(2.0 * log_jitter)
        K = np.array(K, copy=True)
        K[self._diag_idx_train] += noise_var

        try:
            c, lower, _ = stable_cholesky(K, initial_jitter=1e-10)
            alpha = cho_solve((c, lower), r, check_finite=False)

            nll = (
                0.5 * np.dot(r, alpha)
                + np.sum(np.log(np.diag(c)))
                + 0.5 * self.n * self._log_2pi
            )
        except LinAlgError:
            return 1e25

        d2 = np.diff(logP_knots, n=2)
        smooth_pen = self.smoothness_weight * np.dot(d2, d2)

        anchor = logP_knots - self._log_period_init
        anchor_pen = self.prior_weight * np.dot(anchor, anchor)

        return nll + smooth_pen + anchor_pen

    # ----------------------------
    # 拟合
    # ----------------------------
    def fit(self, maxiter=300, disp=True, callback=None):
        """
        优化 MAP 参数。

        参数
        ----
        maxiter: 最大迭代次数
        disp: 是否显示优化过程
        callback: 每次迭代后调用的函数
        """
        result = minimize(
            self._nll,
            self.theta0,
            method="L-BFGS-B",
            bounds=self.bounds,
            callback=callback,
            options={
                "maxiter": maxiter,
                "disp": disp,
                "ftol": 1e-9,
                "gtol": 1e-5
            }
        )

        self.fit_result = result
        self.theta_map = result.x.copy()

        # 重新拟合后，旧的 posterior cache 失效
        self._posterior_cache = None

        return result

    # ----------------------------
    # 后验预测
    # ----------------------------
    def predict(self, t_star, theta=None):
        """
        返回 latent function 的 posterior mean / std / covariance
        """
        if theta is None:
            if self.theta_map is None:
                raise RuntimeError("请先调用 fit()。")
            theta = self.theta_map

        theta = np.asarray(theta, dtype=float).ravel()
        cache = self._posterior_terms(theta)
        if cache is None:
            raise LinAlgError("Predict failed because posterior factorization failed.")

        mu0 = cache["mu0"]
        mu1 = cache["mu1"]
        log_amp = cache["log_amp"]
        log_ell_env = cache["log_ell_env"]
        log_w_per = cache["log_w_per"]
        log_jitter = cache["log_jitter"]
        logP_knots = cache["logP_knots"]

        t_star = np.asarray(t_star, dtype=float).ravel()
        x_star = (t_star - self.tmean) / self.tstd
        m_star = mu0 + mu1 * x_star

        c = cache["c"]
        lower = cache["lower"]
        alpha = cache["alpha"]
        phi_train = cache["phi_train"]

        # 如果是训练集本身，直接复用缓存中的 K_train，避免重复构建
        same_as_train = (t_star.shape == self.t.shape) and np.array_equal(t_star, self.t)

        if same_as_train:
            m_star = cache["m_train"]
            phi_star = phi_train
            K_train = cache["K_train"]

            Ks = K_train
            Kss = K_train
        else:
            order_star = np.argsort(t_star)
            t_star_sorted = t_star[order_star]

            # 这里用 dense_train + t_star，等价于原逻辑的 unique(base_grid + t_train + t_star)
            dense_star = np.unique(np.concatenate([self._phase_dense_train, t_star_sorted]))
            phi_star_sorted = self._phase_of_times_sorted(t_star_sorted, logP_knots, dense_star)

            phi_star = np.empty_like(phi_star_sorted)
            phi_star[order_star] = phi_star_sorted

            dt_ts = np.subtract.outer(self.t, t_star)
            Ks = self._kernel_from_phase(
                dt_ts,
                phi_train,
                phi_star,
                log_amp,
                log_ell_env,
                log_w_per
            )

            dt_ss = np.subtract.outer(t_star, t_star)
            Kss = self._kernel_from_phase(
                dt_ss,
                phi_star,
                phi_star,
                log_amp,
                log_ell_env,
                log_w_per
            )

        mu_star = m_star + Ks.T @ alpha
        v = cho_solve((c, lower), Ks, check_finite=False)
        cov_star = Kss - Ks.T @ v

        cov_star = 0.5 * (cov_star + cov_star.T)
        std_star = np.sqrt(np.maximum(np.diag(cov_star), 0.0))

        return mu_star, std_star, cov_star

    # ----------------------------
    # 直接输出拟合的 P(t)
    # ----------------------------
    def period_curve(self, t_grid, theta=None):
        if theta is None:
            if self.theta_map is None:
                raise RuntimeError("请先调用 fit()。")
            theta = self.theta_map

        _, _, _, _, _, _, logP_knots = self._unpack_theta(theta)
        t_grid = np.asarray(t_grid, dtype=float).ravel()
        return self._period(t_grid, logP_knots)

    # ----------------------------
    # 输出拟合的 knot 周期
    # ----------------------------
    def knot_periods(self, theta=None):
        if theta is None:
            if self.theta_map is None:
                raise RuntimeError("请先调用 fit()。")
            theta = self.theta_map

        _, _, _, _, _, _, logP_knots = self._unpack_theta(theta)
        return np.exp(logP_knots)


# ============================================================
# 4) 多起点重启拟合
# ============================================================
def fit_multistart_ns_qpgp(
    t,
    y,
    yerr,
    period_inits,
    model_kwargs,
    maxiter=300,
    n_random_restarts=1,
    seed=2026,
):
    """
    多起点拟合 NS-QPGP：
    - 对每个 period_init 拟合一次
    - 额外做 n_random_restarts 次轻微扰动重启
    - 返回最优模型、最优结果、restart 表
    """
    rng = np.random.default_rng(seed)
    candidates = []

    # 外层总体进度条：每个 start period 一个块
    for p0 in tqdm(period_inits, desc="Period starts", unit="start"):
        # 内层：同一个 period_init 下的随机重启
        for rr in tqdm(range(n_random_restarts + 1), desc=f"P0={p0:.1f}", leave=False, unit="restart"):
            model = NonstationaryQuasiPeriodicGP(
                t=t,
                y=y,
                yerr=yerr,
                period_init=float(p0),
                **model_kwargs
            )

            theta0 = model.theta0.copy()

            if rr > 0:
                perturb = np.zeros_like(theta0)
                perturb[0:2] = rng.normal(0.0, 0.10, size=2)
                perturb[2:6] = rng.normal(0.0, 0.20, size=4)
                perturb[6:] = rng.normal(0.0, 0.25, size=model.n_knots)
                theta0 = theta0 + perturb
                theta0 = clip_theta_to_bounds(theta0, model.bounds)

            model.theta0 = theta0

            # 每次优化一个自己的 tqdm 进度条
            pbar = tqdm(total=maxiter, desc=f"Fit P0={p0:.1f}, r={rr}", leave=False, unit="iter")

            def cb(_xk):
                pbar.update(1)

            try:
                result = model.fit(maxiter=maxiter, disp=False, callback=cb)
            finally:
                pbar.close()

            mu0, mu1, log_amp, log_ell_env, log_w_per, log_jitter, logP_knots = model._unpack_theta(result.x)

            record = {
                "start_period": float(p0),
                "restart_id": int(rr),
                "success": bool(result.success),
                "nit": int(getattr(result, "nit", -1)),
                "nfev": int(getattr(result, "nfev", -1)),
                "fun": float(result.fun),
                "message": str(result.message),
                "mu0": float(mu0),
                "mu1": float(mu1),
                "amp": float(np.exp(log_amp)),
                "ell_env": float(np.exp(log_ell_env)),
                "w_per": float(np.exp(log_w_per)),
                "jitter": float(np.exp(log_jitter)),
                "knot_period_min": float(np.exp(np.min(logP_knots))),
                "knot_period_max": float(np.exp(np.max(logP_knots))),
                "model": model,
                "result": result,
            }
            candidates.append(record)

            print(
                f"[multistart] P0={p0:.3f}, restart={rr}, "
                f"fun={result.fun:.4f}, success={result.success}, message={result.message}"
            )

    best_idx = int(np.argmin([c["fun"] for c in candidates]))
    best = candidates[best_idx]

    restart_rows = []
    for c in candidates:
        restart_rows.append({k: v for k, v in c.items() if k not in ("model", "result")})
    restart_df = pd.DataFrame(restart_rows).sort_values(["fun", "success"], ascending=[True, False]).reset_index(drop=True)

    return best["model"], best["result"], restart_df, candidates


# ============================================================
# 5) 真实数据绘图
# ============================================================
def plot_ns_qpgp_real_results(
    t,
    y,
    yerr,
    t_grid,
    mu_pred,
    std_pred,
    P_fit,
    knot_times,
    knot_periods,
    source_name=None,
    use_relative_time=True,
    annotation_text=None,
    save_png=None,
    save_pdf=None,
    show=True,
    dpi=300,
):
    """
    真实数据版绘图：
    - 上图：观测数据 + posterior mean + 1σ / 2σ
    - 下图：MAP local period + knot points
    """
    t = np.asarray(t, dtype=float).ravel()
    y = np.asarray(y, dtype=float).ravel()
    yerr = np.asarray(yerr, dtype=float).ravel()
    t_grid = np.asarray(t_grid, dtype=float).ravel()
    mu_pred = np.asarray(mu_pred, dtype=float).ravel()
    std_pred = np.asarray(std_pred, dtype=float).ravel()
    P_fit = np.asarray(P_fit, dtype=float).ravel()
    knot_times = np.asarray(knot_times, dtype=float).ravel()
    knot_periods = np.asarray(knot_periods, dtype=float).ravel()

    if use_relative_time:
        t0 = np.min(t)
        t_plot = t - t0
        t_grid_plot = t_grid - t0
        knot_times_plot = knot_times - t0
        x_label = f"Time - {t0:.1f} (day)"
    else:
        t_plot = t
        t_grid_plot = t_grid
        knot_times_plot = knot_times
        x_label = "Time (day)"

    plt.style.use("seaborn-v0_8-whitegrid")
    plt.rcParams.update({
        "font.size": 11,
        "axes.titlesize": 13,
        "axes.labelsize": 12,
        "legend.fontsize": 10,
        "xtick.labelsize": 10,
        "ytick.labelsize": 10,
    })

    fig, (ax1, ax2) = plt.subplots(
        2, 1,
        figsize=(14, 8),
        sharex=True,
        gridspec_kw={"height_ratios": [1.15, 1.0]},
        constrained_layout=True
    )

    # ----------------------------
    # 上图：观测 + 后验均值 + 置信带
    # ----------------------------
    ax1.errorbar(
        t_plot, y, yerr=yerr,
        fmt="o", ms=3.0, lw=0.8, capsize=2,
        color="tab:blue", alpha=0.70,
        label="Observed data"
    )

    ax1.plot(
        t_grid_plot, mu_pred,
        color="crimson", lw=2.2,
        label="NS-QPGP posterior mean"
    )

    ax1.fill_between(
        t_grid_plot,
        mu_pred - 2.0 * std_pred,
        mu_pred + 2.0 * std_pred,
        color="crimson", alpha=0.10,
        label=r"GP $\pm 2\sigma$"
    )
    ax1.fill_between(
        t_grid_plot,
        mu_pred - 1.0 * std_pred,
        mu_pred + 1.0 * std_pred,
        color="crimson", alpha=0.18,
        label=r"GP $\pm 1\sigma$"
    )

    title = "Nonstationary quasi-periodic GP fit"
    if source_name is not None:
        title = f"{source_name} — {title}"
    ax1.set_title(title, fontsize=14)
    ax1.set_ylabel("Flux", fontsize=12)
    ax1.legend(loc="best", fontsize=10, frameon=True)
    ax1.grid(True, ls="--", alpha=0.25)

    ax1.text(
        0.015, 0.97, "(a)",
        transform=ax1.transAxes,
        fontsize=12, fontweight="bold",
        va="top", ha="left"
    )

    if annotation_text:
        ax1.text(
            0.015, 0.83, annotation_text,
            transform=ax1.transAxes,
            fontsize=9,
            va="top", ha="left",
            bbox=dict(boxstyle="round", facecolor="white", edgecolor="0.85", alpha=0.90)
        )

    # ----------------------------
    # 下图：周期曲线
    # ----------------------------
    ax2.plot(
        t_grid_plot, P_fit,
        color="crimson", lw=2.2,
        label=r"Recovered MAP $P(t)$"
    )

    ax2.scatter(
        knot_times_plot, knot_periods,
        s=42, color="navy", zorder=3,
        label="Fitted knot periods"
    )

    ax2.set_xlabel(x_label, fontsize=12)
    ax2.set_ylabel(r"Period $P(t)$ (day)", fontsize=12)
    ax2.set_title(r"Recovered local period", fontsize=13)
    ax2.legend(loc="best", fontsize=10, frameon=True)
    ax2.grid(True, ls="--", alpha=0.25)

    ax2.text(
        0.015, 0.97, "(b)",
        transform=ax2.transAxes,
        fontsize=12, fontweight="bold",
        va="top", ha="left"
    )

    if save_png is not None:
        fig.savefig(save_png, dpi=dpi, bbox_inches="tight")
    if save_pdf is not None:
        fig.savefig(save_pdf, bbox_inches="tight")

    if show:
        plt.show()

    return fig, (ax1, ax2)


# ============================================================
# 6) 主程序：真实数据版本
# ============================================================
if __name__ == "__main__":

    # ============================================================
    # 真实数据文件
    # ============================================================
    file_map = r"G:\fuxian\data\1_4FGL_J1555.7+1111_weekly_2026_3_17.csv"

    # 输出目录
    source_name = Path(file_map).stem
    out_dir = Path(file_map).parent / f"{source_name}_ns_qpgp_outputs"
    out_dir.mkdir(parents=True, exist_ok=True)

    # ============================================================
    # 读取真实数据
    # ============================================================
    t_raw, y_raw, yerr_raw, df = load_real_csv(
        file_map,
        time_idx=1,   # 你的原代码：第2列是时间
        flux_idx=4,   # 第5列是 flux
        err_idx=5     # 第6列是 flux error
    )

    # 时间平移到从 0 开始
    t0 = float(np.min(t_raw))
    t_rel = t_raw - t0

    # flux 标准化
    y_norm, yerr_norm, y_mean, y_std = standardize_flux(y_raw, yerr_raw)

    print(f"Loaded {len(t_raw)} valid points.")
    print(f"Time span: {t_raw.min():.3f} to {t_raw.max():.3f}")
    print(f"Flux mean = {y_mean:.6g}, std = {y_std:.6g}")

    # ============================================================
    # 多起点重启配置
    # ============================================================
    period_bounds = (20.0, 2000.0)
    span = float(np.max(t_rel) - np.min(t_rel))

    # ===== 在这里自定义初始周期配置 =====

    # 方式1: 默认配置（固定周期 + 跨度比例，约8个周期）
    # period_inits = build_period_initial_grid(
    #     span=span,
    #     lower=period_bounds[0],
    #     upper=period_bounds[1]
    # )

    # 方式2: 只用固定的3个周期（关闭跨度比例）
    period_inits = build_period_initial_grid(
        span=span,
        lower=period_bounds[0],
        upper=period_bounds[1],
        fixed_periods=[500, 800, 1200],
        use_span_ratios=False  # ← 关键：关闭跨度比例
    )

    # 方式3: 只用跨度比例（关闭固定周期）
    # period_inits = build_period_initial_grid(
    #     span=span,
    #     lower=period_bounds[0],
    #     upper=period_bounds[1],
    #     use_fixed=False,  # ← 关键：关闭固定周期
    #     span_ratios=[0.03, 0.05, 0.08, 0.12, 0.18, 0.25]
    # )

    # 方式4: 增加密度（更多固定周期 + 更多跨度比例）
    # period_inits = build_period_initial_grid(
    #     span=span,
    #     lower=period_bounds[0],
    #     upper=period_bounds[1],
    #     fixed_periods=[400, 600, 800, 1000, 1200, 1500, 1800],
    #     span_ratios=[0.03, 0.05, 0.08, 0.12, 0.18, 0.25, 0.30, 0.35]
    # )

    # 方式5: 完全自定义
    # period_inits = build_period_initial_grid(
    #     span=span,
    #     lower=period_bounds[0],
    #     upper=period_bounds[1],
    #     fixed_periods=[400, 600, 900, 1200],
    #     span_ratios=[0.05, 0.10, 0.20, 0.30]
    # )

    # ====================================

    print("Candidate initial periods (days):")
    print(np.array2string(period_inits, precision=3, separator=", "))
    print(f"Total candidate periods: {len(period_inits)}")

    model_kwargs = dict(
        n_knots=15,
        n_phase_grid=1200,
        period_bounds=period_bounds,
        smoothness_weight=0.01,
        prior_weight=1e-5
    )

    # ============================================================
    # 多起点拟合
    # ============================================================
    print("\nStarting multi-start MAP optimization ...")
    best_model, best_result, restart_df, candidates = fit_multistart_ns_qpgp(
        t=t_rel,
        y=y_norm,
        yerr=yerr_norm,
        period_inits=period_inits,
        model_kwargs=model_kwargs,
        maxiter=300,
        n_random_restarts=1,   # 每个 period_init 再做 1 次轻微扰动重启
        seed=2026
    )

    print("\n========== Restart table (top 10) ==========")
    print(restart_df.head(10).to_string(index=False))

    print("\n========== Best fit ==========")
    print("Optimization success:", best_result.success)
    print("Message:", best_result.message)
    print("Final posterior objective:", best_result.fun)

    mu0, mu1, log_amp, log_ell_env, log_w_per, log_jitter, logP_knots = best_model._unpack_theta(best_result.x)
    print(f"amp      = {np.exp(log_amp)}")
    print(f"ell_env  = {np.exp(log_ell_env)}")
    print(f"w_per    = {np.exp(log_w_per)}")
    print(f"jitter   = {np.exp(log_jitter)}")
    print(f"P knots  = {np.exp(logP_knots)}")
    print(f"mu0, mu1 = {mu0}, {mu1}")

    # ============================================================
    # 训练集拟合诊断
    # ============================================================
    mu_train_norm, std_train_norm, _ = best_model.predict(t_rel)
    mu_train = mu_train_norm * y_std + y_mean
    std_train = std_train_norm * y_std

    resid = y_raw - mu_train
    pull = resid / np.maximum(yerr_raw, 1e-12)

    wrms = float(np.sqrt(np.mean(pull ** 2)))
    chi2 = float(np.sum(pull ** 2))
    dof = max(int(len(y_raw) - len(best_model.theta_map)), 1)
    red_chi2 = chi2 / dof
    resid_mean = float(np.mean(resid))
    resid_std = float(np.std(resid))

    print(f"Weighted RMS residual (sigma units): {wrms:.3f}")
    print(f"Reduced chi2 (approx.): {red_chi2:.3f}")
    print(f"Residual mean: {resid_mean:.6g}")
    print(f"Residual std : {resid_std:.6g}")

    # ============================================================
    # 预测网格
    # ============================================================
    t_grid_rel = np.linspace(np.min(t_rel), np.max(t_rel), 1500)
    t_grid_jd = t_grid_rel + t0

    mu_pred_norm, std_pred_norm, _ = best_model.predict(t_grid_rel)
    mu_pred = mu_pred_norm * y_std + y_mean
    std_pred = std_pred_norm * y_std

    P_fit = best_model.period_curve(t_grid_rel)
    knot_times_rel = best_model.knots
    knot_times_jd = knot_times_rel + t0
    knot_periods = best_model.knot_periods()

    # ============================================================
    # 输出表格
    # ============================================================
    summary_df = pd.DataFrame([{
        "source_name": source_name,
        "n_points": int(len(t_raw)),
        "time_start_jd": float(np.min(t_raw)),
        "time_end_jd": float(np.max(t_raw)),
        "time_span_days": float(np.max(t_raw) - np.min(t_raw)),
        "flux_mean_raw": float(y_mean),
        "flux_std_raw": float(y_std),
        "best_objective": float(best_result.fun),
        "best_success": bool(best_result.success),
        "best_message": str(best_result.message),
        "best_nit": int(getattr(best_result, "nit", -1)),
        "best_nfev": int(getattr(best_result, "nfev", -1)),
        "amp": float(np.exp(log_amp)),
        "ell_env": float(np.exp(log_ell_env)),
        "w_per": float(np.exp(log_w_per)),
        "jitter": float(np.exp(log_jitter)),
        "mu0": float(mu0),
        "mu1": float(mu1),
        "weighted_rms_residual_sigma": wrms,
        "reduced_chi2_approx": red_chi2,
        "residual_mean_raw": resid_mean,
        "residual_std_raw": resid_std,
    }])

    pred_df = pd.DataFrame({
        "time_jd": t_grid_jd,
        "time_rel_day": t_grid_rel,
        "posterior_mean": mu_pred,
        "posterior_std": std_pred,
        "posterior_minus_1sigma": mu_pred - std_pred,
        "posterior_plus_1sigma": mu_pred + std_pred,
        "posterior_minus_2sigma": mu_pred - 2.0 * std_pred,
        "posterior_plus_2sigma": mu_pred + 2.0 * std_pred,
        "local_period_map_day": P_fit,
    })

    train_df = pd.DataFrame({
        "time_jd": t_raw,
        "time_rel_day": t_rel,
        "flux_obs": y_raw,
        "flux_err": yerr_raw,
        "posterior_mean": mu_train,
        "posterior_std": std_train,
        "residual": resid,
        "pull": pull,
    })

    knot_df = pd.DataFrame({
        "knot_time_jd": knot_times_jd,
        "knot_time_rel_day": knot_times_rel,
        "knot_period_day": knot_periods,
    })

    restart_table_path = out_dir / f"{source_name}_restart_table.csv"
    summary_path = out_dir / f"{source_name}_summary.csv"
    pred_path = out_dir / f"{source_name}_predictions.csv"
    train_path = out_dir / f"{source_name}_train_fit.csv"
    knot_path = out_dir / f"{source_name}_knots.csv"
    report_path = out_dir / f"{source_name}_report.txt"

    restart_df.to_csv(restart_table_path, index=False)
    summary_df.to_csv(summary_path, index=False)
    pred_df.to_csv(pred_path, index=False)
    train_df.to_csv(train_path, index=False)
    knot_df.to_csv(knot_path, index=False)

    # ============================================================
    # 整合所有信息到一个综合CSV文件
    # ============================================================
    comprehensive_data = {}

    # 基本信息
    comprehensive_data["source_name"] = [source_name]
    comprehensive_data["n_points"] = [int(len(t_raw))]
    comprehensive_data["time_start_jd"] = [float(np.min(t_raw))]
    comprehensive_data["time_end_jd"] = [float(np.max(t_raw))]
    comprehensive_data["time_span_days"] = [float(np.max(t_raw) - np.min(t_raw))]

    t_raw_sorted = np.sort(t_raw)
    sampling_dt = np.diff(t_raw_sorted)
    comprehensive_data["sampling_cadence_mean"] = [float(np.mean(sampling_dt))]
    comprehensive_data["sampling_cadence_median"] = [float(np.median(sampling_dt))]

    comprehensive_data["flux_mean_raw"] = [float(y_mean)]
    comprehensive_data["flux_std_raw"] = [float(y_std)]
    comprehensive_data["flux_min"] = [float(np.min(y_raw))]
    comprehensive_data["flux_max"] = [float(np.max(y_raw))]
    comprehensive_data["flux_error_mean"] = [float(np.mean(yerr_raw))]
    comprehensive_data["flux_error_median"] = [float(np.median(yerr_raw))]

    # 优化结果
    comprehensive_data["optimization_success"] = [bool(best_result.success)]
    comprehensive_data["optimization_message"] = [str(best_result.message)]
    comprehensive_data["best_objective_value"] = [float(best_result.fun)]
    comprehensive_data["n_iterations"] = [int(getattr(best_result, "nit", -1))]
    comprehensive_data["n_function_evaluations"] = [int(getattr(best_result, "nfev", -1))]
    comprehensive_data["n_total_restarts"] = [len(restart_df)]
    comprehensive_data["n_successful_restarts"] = [int(restart_df["success"].sum())]
    comprehensive_data["best_restart_start_period"] = [float(restart_df.iloc[0]["start_period"])]
    comprehensive_data["best_restart_id"] = [int(restart_df.iloc[0]["restart_id"])]

    # GP超参数
    comprehensive_data["gp_amp"] = [float(np.exp(log_amp))]
    comprehensive_data["gp_ell_env"] = [float(np.exp(log_ell_env))]
    comprehensive_data["gp_w_per"] = [float(np.exp(log_w_per))]
    comprehensive_data["gp_jitter"] = [float(np.exp(log_jitter))]
    comprehensive_data["gp_mu0"] = [float(mu0)]
    comprehensive_data["gp_mu1"] = [float(mu1)]

    # 周期统计信息
    comprehensive_data["period_knot_min"] = [float(np.min(knot_periods))]
    comprehensive_data["period_knot_max"] = [float(np.max(knot_periods))]
    comprehensive_data["period_knot_mean"] = [float(np.mean(knot_periods))]
    comprehensive_data["period_knot_median"] = [float(np.median(knot_periods))]
    comprehensive_data["period_knot_std"] = [float(np.std(knot_periods))]
    comprehensive_data["period_grid_min"] = [float(np.min(P_fit))]
    comprehensive_data["period_grid_max"] = [float(np.max(P_fit))]
    comprehensive_data["period_grid_mean"] = [float(np.mean(P_fit))]
    comprehensive_data["period_variation_amplitude"] = [float(np.max(P_fit) - np.min(P_fit))]
    comprehensive_data["period_variation_relative"] = [float((np.max(P_fit) - np.min(P_fit)) / np.mean(P_fit) * 100)]

    # 拟合质量指标
    comprehensive_data["weighted_rms_residual_sigma"] = [wrms]
    comprehensive_data["reduced_chi2_approx"] = [red_chi2]
    comprehensive_data["chi2_total"] = [chi2]
    comprehensive_data["degrees_of_freedom"] = [dof]
    comprehensive_data["residual_mean_raw"] = [resid_mean]
    comprehensive_data["residual_std_raw"] = [resid_std]
    comprehensive_data["residual_skewness"] = [float(pd.Series(resid).skew())]
    comprehensive_data["residual_kurtosis"] = [float(pd.Series(resid).kurtosis())]
    comprehensive_data["pull_mean"] = [float(np.mean(pull))]
    comprehensive_data["pull_std"] = [float(np.std(pull))]
    comprehensive_data["fraction_within_1sigma"] = [float(np.sum(np.abs(resid) <= std_train) / len(resid))]
    comprehensive_data["fraction_within_2sigma"] = [float(np.sum(np.abs(resid) <= 2 * std_train) / len(resid))]

    # 模型配置
    comprehensive_data["n_knots"] = [best_model.n_knots]
    comprehensive_data["n_phase_grid"] = [best_model.n_phase_grid]
    comprehensive_data["period_lower_bound"] = [best_model.period_lower]
    comprehensive_data["period_upper_bound"] = [best_model.period_upper]
    comprehensive_data["smoothness_weight"] = [best_model.smoothness_weight]
    comprehensive_data["prior_weight"] = [best_model.prior_weight]
    comprehensive_data["n_candidate_periods"] = [len(period_inits)]
    comprehensive_data["candidate_periods_list"] = [",".join([f"{p:.1f}" for p in period_inits])]

    # Knot详细信息（JSON格式存储）
    import json
    comprehensive_data["knot_times_jd"] = [json.dumps(knot_times_jd.tolist())]
    comprehensive_data["knot_times_rel"] = [json.dumps(knot_times_rel.tolist())]
    comprehensive_data["knot_periods"] = [json.dumps(knot_periods.tolist())]

    # 重启优化统计
    comprehensive_data["restart_fun_min"] = [float(restart_df["fun"].min())]
    comprehensive_data["restart_fun_max"] = [float(restart_df["fun"].max())]
    comprehensive_data["restart_fun_mean"] = [float(restart_df["fun"].mean())]
    comprehensive_data["restart_fun_std"] = [float(restart_df["fun"].std())]
    comprehensive_data["restart_fun_best10_mean"] = [float(restart_df.head(10)["fun"].mean())]

    comprehensive_df = pd.DataFrame(comprehensive_data)
    comprehensive_path = out_dir / f"{source_name}_comprehensive_results.csv"
    comprehensive_df.to_csv(comprehensive_path, index=False, encoding="utf-8-sig")

    # ============================================================
    # 输出文字报告
    # ============================================================
    with open(report_path, "w", encoding="utf-8") as f:
        f.write("NS-QPGP real-data fit report\n")
        f.write("=" * 60 + "\n\n")
        f.write("=== COMPREHENSIVE SUMMARY ===\n")
        f.write(comprehensive_df.to_string(index=False))
        f.write("\n\n")
        f.write("=== BEST KNOT PERIODS (days) ===\n")
        f.write(np.array2string(knot_periods, precision=6, separator=", "))
        f.write("\n\n")
        f.write("=== BEST KNOT TIMES (JD) ===\n")
        f.write(np.array2string(knot_times_jd, precision=6, separator=", "))
        f.write("\n\n")
        f.write("=== TOP 10 RESTARTS ===\n")
        f.write(restart_df.head(10).to_string(index=False))
        f.write("\n\n")
        f.write("=== FITTING QUALITY METRICS ===\n")
        f.write(f"Weighted RMS residual (sigma units): {wrms:.4f}\n")
        f.write(f"Reduced chi-squared (approx.): {red_chi2:.4f}\n")
        f.write(f"Total chi-squared: {chi2:.4f}\n")
        f.write(f"Degrees of freedom: {dof}\n")
        f.write(f"Residual mean: {resid_mean:.6g}\n")
        f.write(f"Residual std: {resid_std:.6g}\n")
        f.write(f"Residual skewness: {pd.Series(resid).skew():.4f}\n")
        f.write(f"Residual kurtosis: {pd.Series(resid).kurtosis():.4f}\n")
        f.write(f"Pull mean: {np.mean(pull):.4f}\n")
        f.write(f"Pull std: {np.std(pull):.4f}\n")
        f.write(f"Fraction within 1-sigma: {np.sum(np.abs(resid) <= std_train) / len(resid):.2%}\n")
        f.write(f"Fraction within 2-sigma: {np.sum(np.abs(resid) <= 2 * std_train) / len(resid):.2%}\n")
        f.write("\n")
        f.write("=== PERIOD STATISTICS ===\n")
        f.write(f"Period range (knots): [{np.min(knot_periods):.4f}, {np.max(knot_periods):.4f}] days\n")
        f.write(f"Period mean (knots): {np.mean(knot_periods):.4f} ± {np.std(knot_periods):.4f} days\n")
        f.write(f"Period range (grid): [{np.min(P_fit):.4f}, {np.max(P_fit):.4f}] days\n")
        f.write(f"Period variation amplitude: {np.max(P_fit) - np.min(P_fit):.4f} days\n")
        f.write(f"Period variation (relative): {(np.max(P_fit) - np.min(P_fit)) / np.mean(P_fit) * 100:.2f}%\n")
        f.write("\n")

    print(f"\nSaved comprehensive results to: {comprehensive_path}")
    print(f"Saved summary to: {summary_path}")
    print(f"Saved predictions to: {pred_path}")
    print(f"Saved training fit to: {train_path}")
    print(f"Saved knot table to: {knot_path}")
    print(f"Saved restart table to: {restart_table_path}")
    print(f"Saved report to: {report_path}")

    # ============================================================
    # 画图
    # ============================================================
    annotation = (
        f"Best objective = {best_result.fun:.2f}\n"
        f"Weighted RMS = {wrms:.2f}\n"
        f"Reduced $\\chi^2$ ≈ {red_chi2:.2f}\n"
        f"Best start P0 = {restart_df.iloc[0]['start_period']:.1f} d"
    )

    png_path = out_dir / f"{source_name}_ns_qpgp_fit.png"
    pdf_path = out_dir / f"{source_name}_ns_qpgp_fit.pdf"

    plot_ns_qpgp_real_results(
        t=t_raw,
        y=y_raw,
        yerr=yerr_raw,
        t_grid=t_grid_jd,
        mu_pred=mu_pred,
        std_pred=std_pred,
        P_fit=P_fit,
        knot_times=knot_times_jd,
        knot_periods=knot_periods,
        source_name=source_name,
        use_relative_time=True,
        annotation_text=annotation,
        save_png=png_path,
        save_pdf=pdf_path,
        show=True,
        dpi=300,
    )

    print(f"\nSaved figure to: {png_path}")
    print(f"Saved figure to: {pdf_path}")