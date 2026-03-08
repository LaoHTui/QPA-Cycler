import json
import os
import numpy as np
from numpy import ndarray

import jurkevich as jv
import lsp
import dcf
import wwz
import harmonic



def auto_filter_method(source_name:str, series:ndarray, flux:ndarray, flux_err:ndarray, config_map:str, save_path:str) -> tuple[bool, dict]:
    candidate_dict = {"source": source_name}
    with open(f'{config_map}.json') as f:
        config = json.load(f)
    # ======================================第一阶段：LSP快速粗筛与SNR,FAP判定筛选======================================
    # 计算LSP结果，SNR筛选内涵在里面
    lsp_periods_list, lsp_periods_err = [], []
    frequency, power = lsp.lsp_Method(series, flux, flux_err,
                                      multiple_freq_max=config["auto"]['lsp_params']['multiple_freq_max'],
                                      divide_freq_step=config["auto"]['lsp_params']['divide_freq_step'])
    lsp_candidate_periods, lsp_candidate_periods_err, lsp_snr, lsp_fhwm, lsp_peak_powers, lsp_prominences, lsp_frequency_index = (
        lsp.get_LSP_results(frequency, power,
                            peak_width_factor=config["auto"]['lsp_filter']['peak_width_factor'],
                            n_harmonics=config["auto"]['lsp_filter']['n_harmonics'],
                            snr_threshold=config["auto"]['lsp_filter']['snr_threshold'],
                            height=config["auto"]['lsp_filter']['height'],
                            min_prominence_rate=config["auto"]['lsp_filter']['min_prominence_rate'],
                            self_harmonic=config["auto"]['lsp_filter']['self_harmonic'],
                            reverse=config["auto"]['lsp_filter']['reverse'],
                            sigma_threshold=config["auto"]['lsp_filter']['sigma_threshold'])
    )
    # 进行FAP筛选
    M = config["auto"]['lsp_params']['M']
    n_jobs = config["auto"]['lsp_params']['n_jobs']
    fap_threshold = config["auto"]['lsp_filter']['fap_threshold']
    sigmas, mc_lsp = lsp.calculate_Lsp_FAP(series, flux, frequency, M=M, n_jobs=n_jobs)
    lsp.plot_LSP(source_name, frequency, power, lsp_candidate_periods, lsp_candidate_periods_err, lsp_snr,
                 series, flux, sigmas, save_path=save_path, plot_mode="save")
    for i, idx in enumerate(lsp_frequency_index):
        # 正在评估LSP方法测的周期的FAP
        fap_i = round(np.sum(mc_lsp[:, idx] >= power[idx]) / M, 4)
        if fap_i > fap_threshold:
            print(f'LSP-SNR: {idx:.3f} Hz, FAP: {fap_i:.3f} > {fap_threshold:.3f} skip')
            continue
        else:
            print(f'LSP-SNR: {idx:.3f} Hz, FAP: {fap_i:.3f} <= {fap_threshold:.3f}')
            lsp_periods_list.append(lsp_candidate_periods[i])
            lsp_periods_err.append(lsp_candidate_periods_err[i])
    print(f"LSP方法筛选得到{len(lsp_periods_list)}个LSP周期，{lsp_periods_list}+-{lsp_periods_err}")
    # ======================================第二阶段：DCF交叉判定======================================
    if not lsp_periods_list:
        candidate_dict[f"period_1"] = {
            "period": -1,
            "period_err": -1
        }
        # 直接略过该源，排除
        return False, candidate_dict
    else:
        dcf_value, dcf_err, taus = dcf.dcf_Method(series, flux,
                                                  delta_tau=config["auto"]['dcf_params']['delta_tau'],
                                                  c=config["auto"]['dcf_params']['c'],
                                                  max_tau=config["auto"]['dcf_params']['max_tau'],
                                                  normalize=config["auto"]['dcf_params']['normalize'],)
        dcf_candidate_periods, dcf_candidate_periods_err, dcf_snr = (
            dcf.get_DCF_results(dcf_value, dcf_err, taus,
                                height=config["auto"]['dcf_filter']['height'],
                                prominence=config["auto"]['dcf_filter']['prominence'],
                                snr_threshold=config["auto"]['dcf_filter']['snr_threshold'],
                                distance_rate=config["auto"]['dcf_filter']['distance_rate'],
                                self_harmonic=config["auto"]['dcf_filter']['self_harmonic'],
                                sigma_threshold=config["auto"]['dcf_filter']['sigma_threshold'],
                                reverse=config["auto"]['dcf_filter']['reverse'])
        )
        print(f"DCF方法得到{len(dcf_candidate_periods)}个DCF周期，{dcf_candidate_periods}+-{dcf_candidate_periods_err}")
        # if dcf_candidate_periods:
        dcf.plot_DCF(taus, dcf_value, dcf_err, config["auto"]['dcf_params']['delta_tau'] , dcf_candidate_periods,
                         dcf_candidate_periods_err, dcf_snr, source_name, save_path=save_path, plot_mode="save")

        # 评估两方法的结果

        the_2_layer_result = evaluate_two_periods_candidates(lsp_periods_list, lsp_periods_err,
                                                             dcf_candidate_periods, dcf_candidate_periods_err,
                                                             source_name, method1_name='LombScargle', method2_name='DCF' )
        print(the_2_layer_result)

    # ======================================第三阶段：JV交叉判定======================================
        # 访问特定结果
        the_2_layer_periods = get_all_value(the_2_layer_result, "period")
        print(the_2_layer_periods)
        the_2_layer_periods_err = get_all_value(the_2_layer_result, "period_err")

        jv_test_periods = np.arange(config["auto"]['jv_params']['test_periods_start'],
                                    config["auto"]['jv_params']['test_periods_end'],
                                    config["auto"]['jv_params']['test_periods_step'])
        v2, _ = jv.jurkevich_Method(series, flux, jv_test_periods, m=config["auto"]['jv_params']['m_bins'])

        jv_candidate_periods, jv_candidate_periods_err, jv_candidate_v2, jv_boundary_list = jv.get_Jurkevich_results(
            jv_test_periods, v2,
            max_serise=config["auto"]['jv_filter']['max_serise'],
            v2_threshold=config["auto"]['jv_filter']['v2_threshold'],
            min_peak_distance= config["auto"]['jv_filter']['min_peak_distance'],
            prominence=config["auto"]['jv_filter']['prominence'],
            self_harmonic=config["auto"]['jv_filter']['self_harmonic'],
            sigma_threshold=config["auto"]['jv_filter']['sigma_threshold'],
            reverse=config["auto"]['jv_filter']['reverse'])

        print(f"Jurkevich方法得到{len(jv_candidate_periods)}个JV周期，{jv_candidate_periods}+-{jv_candidate_periods_err}")
        if jv_candidate_periods:
            jv.plot_Vm2(source_name, jv_test_periods, v2, jv_candidate_periods, jv_candidate_periods_err, jv_boundary_list, plot_mode='save', save_path=save_path)

        the_3_layer_result = evaluate_two_periods_candidates(the_2_layer_periods, the_2_layer_periods_err,
                                                             jv_candidate_periods, jv_candidate_periods_err,
                                                             source_name, method1_name='LombScargle and DCF',
                                                             method2_name='Jurkevich')
        print(the_3_layer_result)
    # ======================================第四阶段：WZZ最终裁定======================================
    the_3_layer_periods = get_all_value(the_3_layer_result, "period")
    the_3_layer_periods_err = get_all_value(the_3_layer_result, "period_err")
    scan_range = config["auto"]['wwz_params']['scan_range']
    freq_step = config["auto"]['wwz_params']['freq_step']
    tau_number = config["auto"]['wwz_params']['tau_number']
    c = config["auto"]['wwz_params']['c']

    p_number=1

    for candidate_period, candidate_period_err in zip(the_3_layer_periods, the_3_layer_periods_err):
        print(f"正在处理{candidate_period:.4f}周期")

        candidate_ferq = 1 / candidate_period
        freq_start = max(candidate_ferq * (1 - scan_range), 0.00001)
        freq_end = candidate_ferq * (1 + scan_range)
        frequency_parameter_list = [freq_start, freq_end, freq_step]

        # 计算WWZ变换
        wwz_taus, wwz_freqs, wwz_Z, wwz_COI, wwz_A, wwz_N_eff = wwz.wwz_Method(series, flux, tau_number, frequency_parameter_list, c,
                                                                               z_height=config["auto"]['wwz_params']['z_height'])

        wwz_peak_freq, wwz_peak_tau, wwz_jumps, wwz_segments, wwz_freq_smooth = wwz.analyze_peak_frequency_variations(wwz_taus, wwz_freqs, wwz_Z, wwz_COI,
                                                                                min_size=config["auto"]['wwz_filter']['min_size'],
                                                                                confidence=config["auto"]['wwz_filter']['confidence'],
                                                                                peak_mode=config["auto"]['wwz_filter']['peak_mode'])
        # Print detected change points
        wwz.plot_wwz(wwz_taus, wwz_freqs, wwz_Z, wwz_COI, wwz_peak_freq, wwz_freq_smooth, wwz_peak_tau, wwz_jumps, wwz_segments, source_name+f"-{candidate_period:.4f}",save_path=save_path, plot_mode="save")
        wwz.print_segments(wwz_segments)

        jv_exist = f'Jurkecivh Method detected {len(jv_candidate_periods)} cycles:{jv_candidate_periods}+-{jv_candidate_periods_err}' if jv_candidate_periods else 'Jurkecivh Method did not detect cycle'
        dcf_exist = f'DCF Method detected {len(dcf_candidate_periods)} cycles:{dcf_candidate_periods}+-{dcf_candidate_periods_err}' if dcf_candidate_periods else 'DCF Method did not detect cycle'
        lsp_exist = f'LSP Method detected {len(lsp_periods_list)} cycles:{lsp_periods_list}+-{lsp_periods_err}'
        key = f"period_{p_number}"
        p_number += 1

        if wwz_segments:
            for j, seg in enumerate(wwz_segments):

                if max(candidate_period - candidate_period_err, 0) <= (
                        1.0 / seg['mean_freq']) <= candidate_period + candidate_period_err:
                    candidate_dict[key] = {
                        "period": round(float(candidate_period), 4),
                        "period_err": round(float(candidate_period_err), 4),
                        "start_time": seg["start_time"],
                        "end_time": seg["end_time"],
                        "duration": seg["duration"],
                        "label": f"WWZ method validation cycle successful：{1.0 / seg['mean_freq']:.4f},{lsp_exist},{dcf_exist},{jv_exist}"
                    }
                    break
                elif j != len(wwz_segments) - 1:
                    continue
                else:
                    candidate_dict[key] = {
                        "period": round(float(candidate_period), 4),
                        "period_err": round(float(candidate_period_err), 4),
                        "label": f"WWZ method did not detect this cycle,{lsp_exist},{dcf_exist},{jv_exist}"
                    }

        else:
            candidate_dict[key] = {
                "period": round(float(candidate_period), 4),
                "period_err": round(float(candidate_period_err), 4),
                "label": f"WWZ method has no results,{lsp_exist},{dcf_exist},{jv_exist}"
            }


    return True, candidate_dict




def _evaluate_Method(p1: float, p1_err: float, p2: float, p2_err: float, sigma_threshold: float = 2.0,
                     method1_name: str = "Method1", method2_name: str = "Method2") -> dict:
    if p1 <= 0 or p2 <= 0 or p1_err < 0 or p2_err < 0:
        return {
            "type": "ERROR",
            "period": np.nan,
            "period_err": np.nan,
            "label": "Invalid period input (non-positive value or negative error)",
        }
    if (p1 + p1_err >= p2 - p2_err) and (p1 - p1_err <= p2 + p2_err):
        # 根据误差进行加权平均
        w1 = 1 / max(p1_err ** 2, 10**-6)
        w2 = 1 / max(p2_err ** 2, 10**-6)
        P_final = round((w1 * p1 + w2 * p2) / (w1 + w2), 3)
        P_final_err = round(1/np.sqrt(w1 + w2), 3)
        return{
            "type": "weighted_average",
            "period": P_final,
            "period_err": P_final_err,
            "components": {
                "p1": p1,
                "p1_err": p1_err,
                "p1_method": method1_name,
                "p2": p2,
                "p2_err": p2_err,
                "p2_method": method2_name
            },
            "label": 'Weighted average of the same signal',
        }
    else:
        COMMON_RATIOS = [1/5, 1/4, 1/3, 1/2, 2/3, 1.0, 3/2, 2.0, 3.0, 4.0]
        is_harm, ratios, deviation_in_sigma = harmonic.is_harmonic(p1,p1_err,p2,p2_err,COMMON_RATIOS,
                                                              sigma_threshold=sigma_threshold)
        # 谐波检测，保留周期值较小的一个
        if is_harm:
            p2_bigger_p1 = p1 < p2
            base_period = p1 if p2_bigger_p1 else p2
            base_err = p1_err if p2_bigger_p1 else p2_err
            harm_period = p2 if p2_bigger_p1 else p1
            harm_err = p2_err if p2_bigger_p1 else p1_err
            base_period_method = method1_name if p2_bigger_p1 else method2_name
            harm_period_method = method2_name if p2_bigger_p1 else method1_name

            return{
            "type": "harmonic",
            "period": base_period,
            "period_err":base_err,
            "base_period_method": base_period_method,
            "harmonic_period_method": harm_period_method,
            "harmonic_period": harm_period,
            "harmonic_err": harm_err,
            "label": f'A suspected {ratios} harmonic signal was detected to be located at'
                     f' {harm_period} ± {harm_err}，deviation = {deviation_in_sigma:.2f}σ)',
            "ratios": round(p1 / p2,4) if p2 != 0 else None,
            "int_ratios": ratios,
            "deviation_in_sigma": round(deviation_in_sigma, 4),
            }
        else:
            return{
                    "type": "independent",
                    "periods": {
                        "p1": p1,
                        "p1_err": p1_err,
                        "p1_method": method1_name,
                        "p2": p2,
                        "p2_err": p2_err,
                        "p2_method": method2_name
                    },
                    "label": "Suspected to be multiple independent candidate cycles",
            }


def evaluate_two_periods_candidates(periods1: list[float], periods_err1: list[float],
                                    periods2: list[float], periods_err2: list[float],
                                    source_name: str, method1_name: str = "Method1", method2_name: str = "Method2") -> dict:
    results = {}
    # 数据格式错误处理
    if len(periods1) != len(periods_err1) or len(periods2) != len(periods_err2) :
        raise TypeError("The input of data length is incorrect!!!!")
    # 空输入处理
    if not periods1 and not periods2:
        return {
            f"{source_name}_period_0": {
                "type": "no_periods",
                "label": "No periods detected in either method",
            }
        }
    # 单方法策略
    elif not periods1 or not periods2:
        # 生成结果
        non_empty_periods = periods2 if not periods1 else periods1
        non_empty_errors = periods_err2 if not periods1 else periods_err1
        method_name = method2_name if not periods1 else method1_name

        # 为每个检测到的周期创建独立条目
        for j, (p, err) in enumerate(zip(non_empty_periods, non_empty_errors)):
            key = f"{source_name}_period_{j}"
            results[key] = {
                "type": "single_method",
                "method": method_name,
                "period": p,
                "period_err": err,
                "label": f"There is only one method ({method_name}) detected the periods",
            }
    # 双方法策略
    else:
        # 获取共同长度
        min_len = min(len(periods1), len(periods2))
        idx = 0
        # 共同部分
        for p1, p1_err, p2, p2_err in zip(periods1[:min_len], periods_err1[:min_len],
                                          periods2[:min_len], periods_err2[:min_len]):

            evaluate_result = _evaluate_Method(p1, p1_err, p2, p2_err, sigma_threshold=2.0)
            if evaluate_result["type"] == "independent":
                results[f"{source_name}_period_{idx}"] = {
                    "type": evaluate_result["type"],
                    "method": evaluate_result["periods"]["p1_method"],
                    "period": evaluate_result["periods"]["p1"],
                    "period_err": evaluate_result["periods"]["p1_err"],
                    "label": evaluate_result["label"],
                }
                results[f"{source_name}_period_{idx+1}"] = {
                    "type": evaluate_result["type"],
                    "method": evaluate_result["periods"]["p2_method"],
                    "period": evaluate_result["periods"]["p2"],
                    "period_err": evaluate_result["periods"]["p2_err"],
                    "label": evaluate_result["label"],
                }
                idx += 2
            else:
                results[f"{source_name}_period_{idx}"] = evaluate_result
                idx += 1

        # 截断部分（较长列表的剩余元素）
        if len(periods1) > len(periods2):
            for p1, p1_err in zip(periods1[min_len:], periods_err1[min_len:]):
                key = f"{source_name}_period_{idx}"
                results[key] = {
                    "type": "single_method",
                    "method": method1_name,
                    "period": p1,
                    "period_err": p1_err,
                    "label": f"No harmonics were detected in this period of the method{method1_name}, which is a possible candidate period",
                }
                idx += 1
        else:
            for p2, p2_err in zip(periods2[min_len:], periods_err2[min_len:]):
                key = f"{source_name}_period_{idx}"
                results[key] = {
                    "type": "single_method",
                    "method": method2_name,
                    "period": p2,
                    "period_err": p2_err,
                    "label": f"No harmonics were detected in this period of the method{method2_name}, which is a possible candidate period",
                }
                idx += 1
    return results

def get_all_value(results_dict: dict, key_name: str) -> list:
    """从结果字典中提取所有值"""
    all_values = []
    for key, result in results_dict.items():
        if type(result[key_name])== list:
            all_values += result[key_name]
        else:
            all_values.append(result[key_name])

    return all_values


if __name__ == '__main__':
    # 创建模拟数据
    np.random.seed(42)
    julian_dates = np.sort(np.random.uniform(0, 1000, 250))  # 200个时间点
    period = 58.0  # 真实周期
    amplitude = 1.0
    photon_fluxes = amplitude * np.sin(2 * np.pi * julian_dates / period) + np.random.normal(0, 0.2, len(julian_dates))
    photon_fluxes_err = np.full_like(photon_fluxes, 0.2)  # 固定误差

    # 运行测试
    print("=" * 50)
    print("开始测试周期检测流程")
    print("=" * 50)

    s = auto_filter_method(
        source_name="TestSource",
        series=julian_dates,
        flux=photon_fluxes,
        flux_err=photon_fluxes_err,
        config_map="G:/Python Program/QPA-Cycler0.3/config", # 去掉.json后缀
        save_path="./",
    )
    print("测试结果：")
    print( s)