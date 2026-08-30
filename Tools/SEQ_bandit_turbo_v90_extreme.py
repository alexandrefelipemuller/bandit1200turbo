import tkinter as tk
from tkinter import filedialog, messagebox, ttk
import pandas as pd
import numpy as np
import io
import math

# =================================================================
# VIC QUANTUM V90 - BOOSTBANDITOS PASS32 CAUSAL ANALYTICS
# Preserves V80 UI while adding traceable parsing, causal convergence,
# confidence/authority separation and Bandit-specific event intelligence.
# =================================================================

class QuantumEngineCore:
    SCHEMA_VERSION = "PASS32-167"
    STOICH_DEFAULT = 9.5
    # Current Bandit injector-end map from the active sequential calibration.
    # Angles are crank degrees and must be changed only if the MSQ map changes.
    BANDIT_INJ_END_MAP = ((800, 358.0), (3200, 400.0), (5500, 418.0), (7000, 430.0))
    BANDIT_SCHEDULE_ORDER = ('C1', 'C2', 'C4', 'C3')
    BANDIT_CYCLE_OFFSETS = (0.0, 180.0, 360.0, 540.0)

    @staticmethod
    def interpolate_end_angle(rpm):
        xs, ys = zip(*QuantumEngineCore.BANDIT_INJ_END_MAP)
        return float(np.interp(rpm, xs, ys))

    @staticmethod
    def injection_timing_insight(rpm, pw_channels, ecu_end, ecu_starts):
        """Return ECU timing when logged, otherwise a clearly labelled estimate.

        The estimate is scheduling geometry only; it never claims valve-event
        timing because exact cam opening/closing values are not in a datalog.
        """
        ecu_valid = ecu_end > 0.0 or any(angle > 0.0 for angle in ecu_starts)
        end_local = ecu_end if ecu_end > 0.0 else QuantumEngineCore.interpolate_end_angle(rpm)
        deg_per_ms = rpm * 0.006
        windows = []
        for channel, offset, pw, ecu_start in zip(QuantumEngineCore.BANDIT_SCHEDULE_ORDER,
                                                   QuantumEngineCore.BANDIT_CYCLE_OFFSETS,
                                                   pw_channels, ecu_starts):
            end_global = (end_local + offset) % 720.0
            span = pw * deg_per_ms
            start_global = ecu_start if ecu_start > 0.0 else (end_global - span) % 720.0
            windows.append({'channel': channel, 'start': start_global, 'end': end_global, 'span': span})
        return {
            'source': 'ECU' if ecu_valid else 'PERFIL BANDIT (estimado)',
            'ecu_valid': ecu_valid,
            'end_local': end_local,
            'deg_per_ms': deg_per_ms,
            'windows': windows,
        }

    @staticmethod
    def get_col(df_columns, targets):
        """Deterministic resolver: exact normalized names only.

        Loose substring matching was intentionally removed: `PW` must never
        silently resolve to PW2, PW Modelo Ar or a legacy staging channel.
        """
        normalized = {QuantumEngineCore.clean_name(c): c for c in df_columns}
        for t in targets:
            exact = normalized.get(QuantumEngineCore.clean_name(t))
            if exact:
                return exact
        return None

    @staticmethod
    def clean_name(name):
        return "".join(ch for ch in str(name).lower() if ch.isalnum())

    @staticmethod
    def numeric(row, name, default=0.0):
        try:
            value = float(row.get(name, default))
            return value if math.isfinite(value) else default
        except (TypeError, ValueError):
            return default

    @staticmethod
    def canonicalize_log(df):
        """Create stable Q_* channels from TunerStudio / BoostBanditOS headers.

        PW Final is the global command / C1 reference in current sequential logs;
        PW2, PW3 and PW4 are individual scheduled channels. Older logs may only
        expose PW1 or PW, so each canonical field has a deterministic fallback.
        """
        aliases = {
            'Q_TIME': ['Time', 'Seconds', 'SecL'],
            'Q_SECL': ['SecL'], 'Q_ENGINE': ['Engine'], 'Q_DFCO': ['DFCO'],
            'Q_RPM': ['RPM'], 'Q_MAP': ['MAP'], 'Q_TPS': ['TPS'],
            'Q_TPS_RAW': ['TPS ADC'], 'Q_BARO': ['Baro Pressure', 'Baro'],
            'Q_CLT': ['CLT', 'Coolant'], 'Q_IAT': ['IAT'],
            'Q_GAMMAE': ['Gammae', 'Gamma E'], 'Q_GEGO': ['Gego', 'GEGO'],
            'Q_GAIR': ['Gair'], 'Q_GBATTERY': ['Gbattery'], 'Q_GWARM': ['Gwarm'], 'Q_GBARO': ['Gbaro'],
            'Q_LAMBDA': ['Lambda'], 'Q_AFR': ['AFR'],
            'Q_LAMBDA_TARGET': ['Lambda Target'], 'Q_AFR_TARGET': ['AFR Target'],
            'Q_ADVANCE': ['Advance (Current)', 'Advance (Current', 'Advance'],
            'Q_ADVANCE1': ['Advance 1'], 'Q_ADVANCE2': ['Advance 2'],
            'Q_DWELL': ['Dwell'], 'Q_DWELL_MEASURED': ['Dwell (Measured)', 'Dwell Measured'],
            'Q_VBAT': ['Battery V', 'Vbatt', 'VBat'],
            'Q_RPM_DOT': ['rpm/s', 'RPM DOT Raw'], 'Q_TPS_DOT_LOG': ['TPS DOT Raw'],
            'Q_MAP_DOT_LOG': ['MAP DOT Raw'], 'Q_AE_HYBRID_DOT': ['AE DOT Hibrido', 'AE DOT Híbrido'],
            'Q_VE1': ['VE1', 'VE 1'],
            'Q_VE2': ['VE2 Base', 'VE2', 'VE 2'],
            'Q_VE2_VECTOR': ['VE2 Vetor Final', 'VE2 Vector Final'],
            'Q_VE2_REQUEST': ['VE2 Vetor Add Solicitado', 'VE2 Vector Add Requested'],
            'Q_VE2_ADD': ['VE2 Vetor Add Efetivo', 'VE2 Vector Add Effective'],
            'Q_VE2_ACTIVE': ['VE2 Vetor Ativo', 'VE2 Vector Active'],
            'Q_AE_FINAL': ['AE Final'], 'Q_AE_NATIVE': ['AE Nativo', 'AE Native'],
            'Q_SPOOL_ADD': ['Spool Add'], 'Q_SPOOL_HOLD': ['Spool Hold ms'],
            'Q_SPOOL_RECOVERY': ['Spool Recuperacao', 'Spool Recovery'],
            'Q_DFCO_REENTRY': ['DFCO Reentrada Add'], 'Q_DFCO_REENTRY_HOLD': ['DFCO Reentrada Hold ms'],
            'Q_PW_FINAL': ['PW Final', 'PW1', 'PW'],
            'Q_PW2': ['PW2'], 'Q_PW3': ['PW3'], 'Q_PW4': ['PW4'],
            'Q_DUTY_LOGGED': ['Duty Final', 'Injector Duty', 'Duty Cycle'],
            'Q_PW_MODEL_AIR': ['PW Modelo Ar', 'PW Model Air'],
            'Q_PW_EFFECTIVE': ['PW efetivo base', 'PW Effective Base'],
            'Q_INJ_END': ['Angulo fim injecao', 'Injector End Angle'],
            'Q_INJ_START1': ['Inicio injecao C1', 'Injector Start C1'],
            'Q_INJ_START2': ['Inicio injecao C2', 'Injector Start C2'],
            'Q_INJ_START3': ['Inicio injecao C3', 'Injector Start C3'],
            'Q_INJ_START4': ['Inicio injecao C4', 'Injector Start C4'],
            'Q_TRIM_C1': ['Trim C1 final'], 'Q_TRIM_C2': ['Trim C2 final'],
            'Q_TRIM_C4': ['Trim C4 final'], 'Q_TRIM_C3': ['Trim C3 final'],
            'Q_BALANCE_REGION': ['Regiao balanceamento', 'Região balanceamento'],
            'Q_BALANCE_WEIGHT': ['Peso balanceamento'], 'Q_TRIM_LIMIT': ['Limitador trim'],
            'Q_THERMAL_STATE': ['Assistente termico estado', 'Assistente térmico estado'],
            'Q_THERMAL_WEIGHT': ['Assistente termico peso', 'Assistente térmico peso'],
            'Q_THERMAL_FUEL': ['Assistente termico combustivel', 'Assistente térmico combustível'],
            'Q_THERMAL_ANGLE': ['Assistente termico angulo', 'Assistente térmico ângulo'],
            'Q_FUEL_PRESSURE': ['Fuel Pressure', 'PS10'], 'Q_OIL_PRESSURE': ['Oil Pressure'],
            'Q_VSS': ['Wheel Speed (kph)', 'Wheel Speed'], 'Q_EGT': ['EGT'],
            'Q_FUEL_LEVEL': ['Nivel Combustivel', 'Nível Combustível', 'Fuel Level'],
            'Q_SYNC_LOSS': ['Sync Loss #'], 'Q_SYNC_STATUS': ['Sync status'],
            'Q_LOOPS': ['Loops/s'], 'Q_LOOPS_REV': ['Loops/rev'],
            'Q_BOOST_CUT': ['Boost cut'], 'Q_HARD_LAUNCH': ['Hard Launch'],
            'Q_HARD_LIMITER': ['Hard Limiter'],
            'Q_PROT_RPM': ['Engine Prot. RPM'], 'Q_PROT_MAP': ['Engine Prot. MAP'],
            'Q_PROT_OIL': ['Engine Prot. Oil'], 'Q_PROT_AFR': ['Engine Prot. AFR'],
            'Q_PROT_CLT': ['Engine Prot. CLT'],
        }
        source = {}
        for canonical, candidates in aliases.items():
            found = QuantumEngineCore.get_col(df.columns, candidates)
            source[canonical] = found
            if found:
                df[canonical] = pd.to_numeric(df[found], errors='coerce').fillna(0.0)
            else:
                df[canonical] = 0.0

        # Current custom sequential logs label C1 as PW Final. Preserve that
        # fact rather than silently inventing a separate PW1 header.
        df['Q_PW1'] = df['Q_PW_FINAL']
        for channel in ('Q_PW2', 'Q_PW3', 'Q_PW4'):
            if source[channel] is None:
                df[channel] = df['Q_PW_FINAL']

        # Lambda may be absent, disabled, or logged as AFR only.
        if source['Q_LAMBDA'] is None and source['Q_AFR'] is not None:
            df['Q_LAMBDA'] = df['Q_AFR'] / QuantumEngineCore.STOICH_DEFAULT
        if source['Q_LAMBDA_TARGET'] is None and source['Q_AFR_TARGET'] is not None:
            df['Q_LAMBDA_TARGET'] = df['Q_AFR_TARGET'] / QuantumEngineCore.STOICH_DEFAULT

        # Formula is a fallback and an independent cross-check of logged duty:
        # duty % = PW(ms) * RPM / 1200 for a four-stroke sequential channel.
        df['Q_DUTY_DERIVED'] = (df['Q_PW_FINAL'] * df['Q_RPM'] / 1200.0).clip(0.0, 100.0)
        df['Q_DUTY'] = df['Q_DUTY_LOGGED'].where(df['Q_DUTY_LOGGED'] > 0.0, df['Q_DUTY_DERIVED'])
        provenance = {key: ('ECU' if col else 'INDISPONIVEL') for key, col in source.items()}
        provenance['Q_DUTY_DERIVED'] = 'DERIVADO'
        provenance['Q_DUTY'] = 'ECU' if source['Q_DUTY_LOGGED'] else 'DERIVADO'
        if source['Q_LAMBDA'] is None and source['Q_AFR'] is not None:
            provenance['Q_LAMBDA'] = 'DERIVADO'
        df.attrs['quantum_sources'] = source
        df.attrs['quantum_provenance'] = provenance
        df.attrs['quantum_schema'] = QuantumEngineCore.SCHEMA_VERSION
        return df

    @staticmethod
    def analyze_frame(history, mix_params, dt=None):
        delay_frames = int(mix_params.get('delay_frames', 0))
        if len(history) < delay_frames + 1:
            return None

        current = history[-1]
        past = history[-(delay_frames + 1)]
        prev = history[-2]

        try:
            # Real timestamp delta. Logged sample rate is not the firmware tick;
            # never inflate DOT by assuming a fixed 12 ms frame.
            t_now = QuantumEngineCore.numeric(current, 'Q_TIME')
            t_prev = QuantumEngineCore.numeric(prev, 'Q_TIME')
            fallback_dt = max(0.001, float(mix_params.get('sample_period_ms', 12.0)) / 1000.0)
            frame_dt = t_now - t_prev
            if not (0.001 <= frame_dt <= 1.0):
                frame_dt = fallback_dt if dt is None else float(dt)

            # Tratamento de Target
            if mix_params['use_custom_target']:
                target_lambda = float(mix_params['custom_target_val'])
            else:
                target_lambda = QuantumEngineCore.numeric(past, 'Q_LAMBDA_TARGET', 0.0)
                if target_lambda <= 0.3:
                    target_lambda = QuantumEngineCore.numeric(past, 'Q_AFR_TARGET', QuantumEngineCore.STOICH_DEFAULT)
                if target_lambda > 5: target_lambda /= float(mix_params.get('stoich', QuantumEngineCore.STOICH_DEFAULT))
                if target_lambda <= 0.3: target_lambda = 1.0

            # Tratamento da Lambda Atual (Resiliente a falta de sensor)
            has_lambda_sensor = mix_params.get('has_lambda_sensor', True)
            raw_lambda = QuantumEngineCore.numeric(current, 'Q_LAMBDA', 0.0)
            
            if not has_lambda_sensor or raw_lambda <= 0.3 or raw_lambda >= 3.0:
                actual_lambda = target_lambda # Assume neutro se o sensor não estiver ativo
                lambda_valid = False
            else:
                actual_lambda = raw_lambda
                if actual_lambda > 5: actual_lambda /= float(mix_params.get('stoich', QuantumEngineCore.STOICH_DEFAULT))
                lambda_valid = True

            rpm_curr = QuantumEngineCore.numeric(current, 'Q_RPM')
            rpm_prev = QuantumEngineCore.numeric(prev, 'Q_RPM')
            rpm_dot = (rpm_curr - rpm_prev) / frame_dt
            
            suggested_target = target_lambda
            if lambda_valid and mix_params.get('enable_target_search', False) and rpm_dot > 200:
                if actual_lambda < target_lambda and rpm_dot > 500:
                    suggested_target = actual_lambda * 0.98
            
            gamma_factor = QuantumEngineCore.numeric(current, 'Q_GAMMAE', 100) / 100.0
            gego_factor = QuantumEngineCore.numeric(current, 'Q_GEGO', 100) / 100.0
            
            # Causal state: this is the operating point whose combustion reaches
            # the lambda sensor at the current frame.
            causal_rpm = QuantumEngineCore.numeric(past, 'Q_RPM')
            causal_map = QuantumEngineCore.numeric(past, 'Q_MAP')
            causal_tps = QuantumEngineCore.numeric(past, 'Q_TPS')
            causal_time = QuantumEngineCore.numeric(past, 'Q_TIME')
            ve1_orig = QuantumEngineCore.numeric(past, 'Q_VE1')
            ve2_orig = QuantumEngineCore.numeric(past, 'Q_VE2')
            
            ve1_pure, ve2_pure = ve1_orig, ve2_orig
            
            if mix_params['ignore_gammae']:
                divisor = gamma_factor * gego_factor
                if divisor > 0.05:
                    ve1_pure = ve1_orig / divisor
                    ve2_pure = ve2_orig / divisor

            l_error = (actual_lambda / target_lambda) - 1.0 if (lambda_valid and target_lambda > 0) else 0.0
            learn_rate = mix_params.get('learn_rate', 0.8)
            total_corr = l_error * learn_rate
            
            clamp = mix_params.get('clamp_matrix', 0.01)
            raw_corr = total_corr
            if abs(total_corr) < clamp: 
                effective_corr = 0.0
            else:
                effective_corr = total_corr

            max_clamp_val = mix_params.get('max_clamp', 0.25)
            clamped_corr = np.clip(effective_corr, -max_clamp_val, max_clamp_val)
            
            weight_ve1 = mix_params['w_ve1']
            sug_ve1 = ve1_pure * (1.0 + (clamped_corr * weight_ve1))
            sug_ve2 = ve2_pure * (1.0 + (clamped_corr * (1.0 - weight_ve1)))

            pw = QuantumEngineCore.numeric(current, 'Q_PW_FINAL')
            pw_channels = [QuantumEngineCore.numeric(current, f'Q_PW{i}') for i in range(1, 5)]
            duty_logged = QuantumEngineCore.numeric(current, 'Q_DUTY_LOGGED')
            duty_derived = QuantumEngineCore.numeric(current, 'Q_DUTY_DERIVED')
            duty = duty_logged if duty_logged > 0 else duty_derived

            timing = QuantumEngineCore.injection_timing_insight(
                rpm_curr, pw_channels,
                QuantumEngineCore.numeric(current, 'Q_INJ_END'),
                [QuantumEngineCore.numeric(current, key) for key in
                 ('Q_INJ_START1', 'Q_INJ_START2', 'Q_INJ_START4', 'Q_INJ_START3')]
            )

            adv_curr = QuantumEngineCore.numeric(current, 'Q_ADVANCE')
            spark_status = "STABLE" if abs(rpm_dot) < 300 else "DYNAMIC"

            map_val = QuantumEngineCore.numeric(current, 'Q_MAP')
            tps_val = QuantumEngineCore.numeric(current, 'Q_TPS')
            map_dot = (map_val - QuantumEngineCore.numeric(prev, 'Q_MAP')) / frame_dt
            tps_dot = (tps_val - QuantumEngineCore.numeric(prev, 'Q_TPS')) / frame_dt
            ae_final = QuantumEngineCore.numeric(current, 'Q_AE_FINAL', 100.0)
            vector_active = QuantumEngineCore.numeric(current, 'Q_VE2_ACTIVE')
            spool_add = QuantumEngineCore.numeric(current, 'Q_SPOOL_ADD')
            reentry_add = QuantumEngineCore.numeric(current, 'Q_DFCO_REENTRY')
            dfco = QuantumEngineCore.numeric(current, 'Q_DFCO') > 0
            sync_raw = QuantumEngineCore.numeric(current, 'Q_SYNC_STATUS')
            sync_known = 'Q_SYNC_STATUS' in current and sync_raw > 0
            full_sync = (sync_raw >= 2) if sync_known else rpm_curr > 0
            cut_active = any(QuantumEngineCore.numeric(current, key) > 0 for key in
                             ('Q_BOOST_CUT', 'Q_HARD_LIMITER', 'Q_PROT_RPM', 'Q_PROT_MAP',
                              'Q_PROT_OIL', 'Q_PROT_AFR', 'Q_PROT_CLT'))
            base_valid = rpm_curr >= 300 and pw > 0 and full_sync and not dfco and not cut_active
            layer_active = (abs(ae_final - 100.0) > 1.0 or vector_active != 0.0 or
                            spool_add != 0.0 or reentry_add != 0.0)
            steady_fuel_cell = (base_valid and abs(tps_dot) < 5.0 and abs(map_dot) < 5.0 and
                                abs(rpm_dot) < 250.0 and not layer_active)

            brutal = base_valid and (abs(tps_dot) >= 60.0 or abs(map_dot) >= 40.0 or
                                     abs(rpm_dot) >= 900.0 or spool_add >= 12.0)
            if not base_valid:
                event_class, authority = 'INVALIDO', 0.0
            elif steady_fuel_cell:
                event_class, authority = 'ESTAVEL', 1.0
            elif brutal:
                event_class, authority = 'BRUTAL', 0.22
            else:
                event_class, authority = 'TRANSITORIO', 0.48

            if not lambda_valid:
                authority *= 0.35
            evidence_score = 100.0
            evidence_score -= min(35.0, abs(rpm_dot) / 40.0)
            evidence_score -= min(25.0, abs(map_dot) / 4.0)
            evidence_score -= min(20.0, abs(tps_dot) / 8.0)
            if not lambda_valid: evidence_score -= 20.0
            if not full_sync: evidence_score = 0.0
            evidence_score = float(np.clip(evidence_score, 0.0, 100.0))
            
            surge_pts = (max(0.0, map_dot) * (rpm_curr / 1000.0)) / 1.5 if rpm_curr > 0 else 0
            ae_mult = 1.0 + (max(0.0, tps_dot) / 500.0) + (max(0.0, map_dot) / 1000.0)
            ae_add = (surge_pts / 60.0) * (pw * 0.10) if pw > 0 else 0

            cycle_time_720 = (120.0 / rpm_curr) if rpm_curr > 0 else 1.0
            current_time = QuantumEngineCore.numeric(current, 'Q_TIME')
            phase_720_deg = ((current_time % cycle_time_720) / cycle_time_720) * 720.0

            mass_inflow = (pw * rpm_curr) / 1200.0
            past_mass_inflow = (QuantumEngineCore.numeric(prev, 'Q_PW_FINAL') * rpm_prev) / 1200.0 if rpm_prev > 0 else 0.0
            mass_delta = mass_inflow - past_mass_inflow

            bridge_factor = float(np.exp(-abs(map_dot) / 50.0)) if map_dot > 0 else 1.0
            sug_ve1_bridged = (sug_ve1 * bridge_factor) + (ve1_pure * (1.0 - bridge_factor))
            sug_ve2_bridged = (sug_ve2 * bridge_factor) + (ve2_pure * (1.0 - bridge_factor))

            if map_val < 30: phase = "🧊 OVERRUN"
            elif map_val < 95: phase = "☁️ VACUUM"
            elif 95 <= map_val <= 105: phase = "🌀 ATMOS"
            else: phase = f"⚡ BOOST ({(map_val-100)/100:.2f}bar)"

            violence = {'ESTAVEL':'⚖️ ESTÁVEL', 'TRANSITORIO':'🚀 TRANSIENTE',
                        'BRUTAL':'🔥 BRUTAL', 'INVALIDO':'⛔ INVÁLIDO'}[event_class]

            baro = QuantumEngineCore.numeric(current, 'Q_BARO', 100.0)
            if baro < 60.0: baro = 100.0
            fuel_psi = QuantumEngineCore.numeric(current, 'Q_FUEL_PRESSURE')
            fuel_bar = fuel_psi * 0.06894757
            fuel_base_bar = float(mix_params.get('fuel_base_bar', 2.0))
            fuel_expected_bar = max(0.0, fuel_base_bar + (map_val - baro) / 100.0)
            ps10_valid = fuel_psi > 1.0
            fuel_error_bar = fuel_bar - fuel_expected_bar if ps10_valid else 0.0
            ps10_stable = (not ps10_valid) or abs(fuel_error_bar) <= float(mix_params.get('ps10_tolerance_bar', 0.18))
            if not ps10_stable:
                authority *= 0.25

            thermal_state = int(QuantumEngineCore.numeric(current, 'Q_THERMAL_STATE'))
            thermal_names = {0:'OFF', 1:'CRANK CAPTURE', 2:'HOLD', 3:'DECAY', 4:'PS10 VETO'}
            thermal_class = thermal_names.get(thermal_state, 'UNKNOWN')

            # Relative fuel/air-flow proxy, never presented as measured mass.
            pw_effective = QuantumEngineCore.numeric(current, 'Q_PW_EFFECTIVE')
            mass_proxy = max(0.0, pw_effective) * rpm_curr / 1200.0

            return {
                'l_error_pct': l_error * 100.0,
                'raw_corr': raw_corr,
                'effective_corr': effective_corr,
                'clamped_corr': clamped_corr,
                've1_curr': ve1_orig, 've2_curr': ve2_orig,
                've1_pure': ve1_pure, 've2_pure': ve2_pure,
                'sug_ve1': sug_ve1_bridged, 'sug_ve2': sug_ve2_bridged,
                'sug_ve1_raw': sug_ve1, 'sug_ve2_raw': sug_ve2,
                'duty_cycle': duty, 'target_used': target_lambda,
                'lambda': actual_lambda, 'lambda_valid': lambda_valid,
                'suggested_target': suggested_target,
                'gamma_val': gamma_factor * 100.0, 'gego': gego_factor * 100.0,
                'iat': QuantumEngineCore.numeric(current, 'Q_IAT'), 'clt': QuantumEngineCore.numeric(current, 'Q_CLT'),
                'vbat': QuantumEngineCore.numeric(current, 'Q_VBAT'),
                'adv': adv_curr, 'spark_status': spark_status,
                'surge_index': surge_pts, 'phase': phase, 'violence': violence,
                'tps_dot': tps_dot, 'map_dot': map_dot, 'rpm_dot': rpm_dot,
                'frame_dt_ms': frame_dt * 1000.0,
                'event_class': event_class, 'authority': authority * 100.0,
                'evidence_score': evidence_score, 'base_valid': base_valid,
                'causal_tps': causal_tps, 'causal_map': causal_map, 'causal_rpm': causal_rpm,
                'causal_time': causal_time,
                'ae_mult': ae_mult, 'ae_add': ae_add,
                'tps': tps_val, 'map': map_val, 'rpm': rpm_curr, 'pw': pw,
                'time': current_time, 'pw_channels': pw_channels,
                'duty_logged': duty_logged, 'duty_derived': duty_derived,
                'pw_model_air': QuantumEngineCore.numeric(current, 'Q_PW_MODEL_AIR'),
                'pw_effective': pw_effective,
                'inj_end': timing['end_local'], 'timing': timing,
                'steady_fuel_cell': steady_fuel_cell,
                've2_vector': QuantumEngineCore.numeric(current, 'Q_VE2_VECTOR'),
                've2_add': QuantumEngineCore.numeric(current, 'Q_VE2_ADD'),
                've2_active': vector_active,
                'phase_720': phase_720_deg,
                'mass_delta': mass_delta,
                'mass_proxy': mass_proxy, 'bridge_factor': bridge_factor,
                'advance1': QuantumEngineCore.numeric(current, 'Q_ADVANCE1'),
                'advance2': QuantumEngineCore.numeric(current, 'Q_ADVANCE2'),
                'dwell': QuantumEngineCore.numeric(current, 'Q_DWELL'),
                'dwell_measured': QuantumEngineCore.numeric(current, 'Q_DWELL_MEASURED'),
                'fuel_pressure_bar': fuel_bar, 'fuel_expected_bar': fuel_expected_bar,
                'fuel_error_bar': fuel_error_bar, 'ps10_valid': ps10_valid, 'ps10_stable': ps10_stable,
                'thermal_state': thermal_state, 'thermal_class': thermal_class,
                'thermal_weight': QuantumEngineCore.numeric(current, 'Q_THERMAL_WEIGHT'),
                'thermal_fuel': QuantumEngineCore.numeric(current, 'Q_THERMAL_FUEL'),
                'thermal_angle': QuantumEngineCore.numeric(current, 'Q_THERMAL_ANGLE'),
                'spool_add': spool_add, 'spool_hold': QuantumEngineCore.numeric(current, 'Q_SPOOL_HOLD'),
                'spool_recovery': QuantumEngineCore.numeric(current, 'Q_SPOOL_RECOVERY'),
                'dfco_reentry': reentry_add,
                'balance_region': QuantumEngineCore.numeric(current, 'Q_BALANCE_REGION'),
                'balance_weight': QuantumEngineCore.numeric(current, 'Q_BALANCE_WEIGHT'),
                'trims': [QuantumEngineCore.numeric(current, k) for k in ('Q_TRIM_C1','Q_TRIM_C2','Q_TRIM_C4','Q_TRIM_C3')],
                'sync_status': sync_raw,
                'sync_loss': QuantumEngineCore.numeric(current, 'Q_SYNC_LOSS'),
                'sync_loss_delta': max(0.0, QuantumEngineCore.numeric(current, 'Q_SYNC_LOSS') -
                                       QuantumEngineCore.numeric(prev, 'Q_SYNC_LOSS')),
            }
        except Exception as exc:
            # Analyzer must remain tolerant during hover, but retain the cause
            # for diagnostics and tests instead of silently swallowing it.
            QuantumEngineCore.last_error = str(exc)
            return None

    @staticmethod
    def analyze_dataframe(df, start, end, params):
        """Chronological causal analysis shared by every view."""
        start, end = sorted((max(0, int(start)), min(len(df), int(end))))
        if end <= start: start, end = 0, len(df)
        history, results = [], []
        lookback = int(params.get('delay_frames', 0)) + 8
        for _, row in df.iloc[start:end].iterrows():
            history.append(row.to_dict())
            if len(history) > lookback: history.pop(0)
            ans = QuantumEngineCore.analyze_frame(history, params)
            if ans: results.append(ans)
        return results

    @staticmethod
    def event_label(ans):
        if not ans['base_valid']: return 'INVALIDO'
        if ans['sync_loss_delta'] > 0: return 'SYNC LOSS'
        if ans['thermal_state'] in (1, 2, 3, 4): return f"TERMICO:{ans['thermal_class']}"
        if ans['spool_add'] > 0: return 'SPOOL'
        if ans['dfco_reentry'] > 0: return 'DFCO REENTRY'
        if ans['event_class'] == 'BRUTAL': return 'BRUTAL'
        if ans['event_class'] == 'TRANSITORIO': return 'TRANSITORIO'
        return 'ESTAVEL'


class IgnitionVectorWindow(tk.Toplevel):
    """Bandit-specific spark surface plus 720-degree injection/spark view."""
    def __init__(self, parent, df, start, end, params):
        super().__init__(parent)
        self.title("IGNITION VECTOR • SPARK / INJECTION / 720°")
        self.geometry("1280x780")
        self.configure(bg="#050505")
        self.frames = QuantumEngineCore.analyze_dataframe(df, start, end, params)
        self.nb = ttk.Notebook(self); self.nb.pack(fill="both", expand=True)
        self.map_page = tk.Frame(self.nb, bg="#050505")
        self.cycle_page = tk.Frame(self.nb, bg="#050505")
        self.nb.add(self.map_page, text="  SPARK • MAP × RPM  ")
        self.nb.add(self.cycle_page, text="  CICLO 720°  ")
        self.map_canvas = tk.Canvas(self.map_page, bg="#020608", highlightthickness=0)
        self.map_canvas.pack(fill="both", expand=True)
        self.cycle_canvas = tk.Canvas(self.cycle_page, bg="#020608", highlightthickness=0)
        self.cycle_canvas.pack(fill="both", expand=True)
        self.index = tk.IntVar(value=max(0, len(self.frames)-1))
        self.slider = tk.Scale(self.cycle_page, from_=0, to=max(0, len(self.frames)-1),
                               variable=self.index, orient="horizontal", showvalue=False,
                               bg="#080808", fg="#0ff", command=lambda _v:self.draw_cycle())
        self.slider.pack(fill="x")
        self.map_canvas.bind("<Configure>", lambda _e:self.draw_map())
        self.cycle_canvas.bind("<Configure>", lambda _e:self.draw_cycle())

    def draw_map(self):
        c=self.map_canvas; c.delete('all')
        if not self.frames: return
        data=pd.DataFrame(self.frames); w,h=c.winfo_width(),c.winfo_height()
        if w<200 or h<150:return
        left,top,right,bottom=55,25,15,35; nx,ny=24,18
        r0,r1=float(data.causal_rpm.min()),float(data.causal_rpm.max()); m0,m1=float(data.causal_map.min()),float(data.causal_map.max())
        if r1<=r0:r1=r0+1
        if m1<=m0:m1=m0+1
        cw=(w-left-right)/nx; ch=(h-top-bottom)/ny
        vals=[]; cells=[]
        for gy in range(ny):
            ml=m1-(gy+1)*(m1-m0)/ny; mh=m1-gy*(m1-m0)/ny
            for gx in range(nx):
                rl=r0+gx*(r1-r0)/nx; rh=r0+(gx+1)*(r1-r0)/nx
                hits=data[data.causal_rpm.between(rl,rh)&data.causal_map.between(ml,mh)&data.base_valid]
                value=float(hits.adv.median()) if len(hits) else np.nan
                if np.isfinite(value): vals.append(value)
                cells.append((gx,gy,value,len(hits),float(hits.authority.median()) if len(hits) else 0))
        lo,hi=(min(vals),max(vals)) if vals else (0,1)
        for gx,gy,value,count,auth in cells:
            x1=left+gx*cw;y1=top+gy*ch
            color=DualVectorMapWindow.matrix_color(value,lo,hi) if np.isfinite(value) else '#0b0e12'
            c.create_rectangle(x1,y1,x1+cw,y1+ch,fill=color,outline='#17232a')
            if np.isfinite(value) and cw>28 and ch>17:
                c.create_text(x1+cw/2,y1+ch/2,text=f"{value:.1f}",fill='white',font=('Consolas',7,'bold'))
        for i in range(0,nx,3): c.create_text(left+(i+.5)*cw,h-14,text=f"{r0+i*(r1-r0)/nx:.0f}",fill='#0f0',font=('Consolas',7))
        for i in range(0,ny,2): c.create_text(left-5,top+(i+.5)*ch,text=f"{m1-i*(m1-m0)/ny:.0f}",fill='#0ff',anchor='e',font=('Consolas',7))
        c.create_text(8,8,text="MAP kPa",fill='#0ff',anchor='w',font=('Consolas',9,'bold'))
        c.create_text(w-8,8,text="Avanço final observado • RPM →",fill='#ff9900',anchor='e',font=('Consolas',9,'bold'))

    def draw_cycle(self):
        c=self.cycle_canvas;c.delete('all')
        if not self.frames:return
        fr=self.frames[min(int(self.index.get()),len(self.frames)-1)];w,h=c.winfo_width(),c.winfo_height()
        left,right=85,25; usable=w-left-right
        for deg in range(0,721,90):
            x=left+usable*deg/720;c.create_line(x,35,x,h-30,fill='#173038');c.create_text(x,20,text=f"{deg}°",fill='#0cc',font=('Consolas',8))
        colors=['#00ffcc','#66aaff','#ffcc00','#ff6688']
        for i,window in enumerate(fr['timing']['windows']):
            y=85+i*75; start,end=window['start'],window['end']
            c.create_text(12,y,text=window['channel'],fill=colors[i],anchor='w',font=('Consolas',10,'bold'))
            segments=[(start,end)] if start<=end else [(start,720),(0,end)]
            for a,b in segments:
                c.create_rectangle(left+usable*a/720,y-12,left+usable*b/720,y+12,fill=colors[i],outline='white')
            # Channel cycle offset is the cylinder TDC reference in the
            # sequential 1-2-4-3 schedule; advance is degrees BTDC.
            spark=(QuantumEngineCore.BANDIT_CYCLE_OFFSETS[i]-fr['adv'])%720
            sx=left+usable*spark/720;c.create_line(sx,y-25,sx,y+25,fill='#ff3300',width=3)
            c.create_text(sx,y-31,text=f"SPK {spark:.1f}°",fill='#ff7755',font=('Consolas',7))
        info=(f"RPM {fr['rpm']:.0f} | MAP {fr['map']:.1f} | ADV {fr['adv']:.1f}° "
              f"(S1 {fr['advance1']:.1f} / S2 {fr['advance2']:.1f}) | DWELL {fr['dwell']:.2f} ms | "
              f"{fr['event_class']} • evidência {fr['evidence_score']:.0f}% • autoridade {fr['authority']:.0f}%")
        c.create_text(left,h-18,text=info,fill='#eee',anchor='w',font=('Consolas',9,'bold'))


class AnalysisTextWindow(tk.Toplevel):
    def __init__(self, parent, title, text):
        super().__init__(parent);self.title(title);self.geometry('1050x720');self.configure(bg='#050505')
        box=tk.Text(self,bg='#050505',fg='#00ff88',font=('Consolas',10),wrap='word',padx=12,pady=12)
        box.pack(fill='both',expand=True);box.insert('1.0',text);box.config(state='disabled')


class DualVectorMapWindow(tk.Toplevel):
    def __init__(self, parent, df, sel_start, sel_end, mix_params):
        super().__init__(parent)
        self.title("QUANTUM BATTLEFIELD 3D & 2D VECTOR MATRIX")
        self.geometry("1400x900")
        self.configure(bg="#050505")

        self.df = df
        self.sel_start, self.sel_end = sorted([sel_start, sel_end])
        if self.sel_start == self.sel_end: self.sel_end = len(df)
        self.mix_params = mix_params.copy()
        self.analysis_cache = []

        self._replay_after_id = None
        self._anim_after_id = None

        self.protocol("WM_DELETE_WINDOW", self.on_close)

        self.nb = ttk.Notebook(self)
        self.nb.pack(fill="both", expand=True)

        self.tab_2d = tk.Frame(self.nb, bg="#050505")
        self.tab_3d = tk.Frame(self.nb, bg="#050505")

        self.nb.add(self.tab_2d, text="  MATRIZES 2D (TPS / MAP)  ")
        self.nb.add(self.tab_3d, text="  MAPA 3D ANIMADA & REPLAY  ")

        self.setup_3d_view()
        self.setup_2d_view()

    def on_close(self):
        self.is_playing = False
        self.is_animating = False
        if self._replay_after_id:
            self.after_cancel(self._replay_after_id)
            self._replay_after_id = None
        if self._anim_after_id:
            self.after_cancel(self._anim_after_id)
            self._anim_after_id = None
        self.destroy()

    def build_analysis_cache(self, params=None):
        """Analyze the log in chronological order once; never synthesize a
        history by duplicating one frame. This is the source for 2D and 3D."""
        params = params or self.mix_params
        cache = QuantumEngineCore.analyze_dataframe(self.df, self.sel_start, self.sel_end, params)
        self.analysis_cache = cache
        return cache

    def setup_2d_view(self):
        self.cell_field_var = tk.StringVar(value="VE sugerida")
        self.cell_filter_var = tk.StringVar(value="Estáveis preferidos")
        self.rpm_bins_var = tk.StringVar(value="32")
        self.load_bins_var = tk.StringVar(value="20")

        tools_bar = tk.Frame(self.tab_2d, bg="#080b0d")
        tools_bar.pack(fill="x", padx=5, pady=(4, 0))
        controls = [
            ("Campo", self.cell_field_var,
             ["VE sugerida", "Delta VE", "Correção %", "Confiança", "Hits",
              "Erro lambda %", "Lambda média", "PW ms", "Duty %", "VE2 vetor add",
              "Autoridade %", "Evidência %", "Avanço °", "PS10 erro bar", "IAT °C", "CLT °C"], 16),
            ("Filtro", self.cell_filter_var,
             ["Estáveis preferidos", "Somente estáveis", "Todas as amostras", "Transitórias", "Brutais"], 18),
            ("Colunas RPM", self.rpm_bins_var, ["16", "24", "32", "40"], 5),
            ("Linhas carga", self.load_bins_var, ["12", "16", "20", "24"], 5),
        ]
        for label, variable, values, width in controls:
            tk.Label(tools_bar, text=f"{label}:", bg="#080b0d", fg="#7f9696",
                     font=("Consolas", 8)).pack(side="left", padx=(8, 2))
            combo = ttk.Combobox(tools_bar, textvariable=variable, values=values,
                                 width=width, state="readonly")
            combo.pack(side="left", padx=(0, 4), pady=3)
            combo.bind("<<ComboboxSelected>>", lambda _e: self.redraw_all_2d())
        self.matrix_legend = tk.Label(tools_bar, text="", bg="#080b0d", fg="#00ffcc",
                                      font=("Consolas", 8), anchor="e")
        self.matrix_legend.pack(side="right", fill="x", expand=True, padx=8)

        self.vector_tabs = ttk.Notebook(self.tab_2d)
        self.vector_tabs.pack(expand=True, fill="both", padx=5, pady=(2, 5))
        self.map_views = []
        for title, source_key, value_key, y_label in [
            ("VE1 • TPS × RPM", 'causal_tps', 'sug_ve1', 'TPS causal %'),
            ("VE2 • MAP × RPM", 'causal_map', 'sug_ve2', 'MAP causal kPa'),
        ]:
            page = tk.Frame(self.vector_tabs, bg="#050505")
            self.vector_tabs.add(page, text=f"  {title}  ")
            bar = tk.Label(page, text="Uma métrica por célula. Use Campo e Filtro para trocar a leitura sem perder resolução dos eixos.",
                           bg="#050505", fg="#9aa", font=("Consolas", 8), anchor="w")
            bar.pack(fill="x", padx=8, pady=(4, 0))
            canvas = tk.Canvas(page, bg="#000", highlightthickness=1, highlightbackground="#163030")
            canvas.pack(expand=True, fill="both", padx=8, pady=6)
            self.map_views.append((canvas, source_key, value_key, y_label))
            canvas.bind("<Configure>", lambda e, c=canvas, sk=source_key, vk=value_key, yl=y_label: self.draw_2d_map(c, sk, vk, yl))

    def redraw_all_2d(self):
        if not hasattr(self, 'map_views'):
            return
        for canvas, source_key, value_key, y_label in self.map_views:
            self.draw_2d_map(canvas, source_key, value_key, y_label)

    @staticmethod
    def matrix_color(value, low, high, palette="sequential"):
        """Compact, dependency-free color mapping for a selected cell field."""
        if not np.isfinite(value):
            return "#0b0e12"
        if palette == "diverging":
            extent = max(abs(low), abs(high), 1e-9)
            ratio = max(-1.0, min(1.0, value / extent))
            if abs(ratio) < 0.04:
                return "#06452f"
            intensity = int(38 + 105 * abs(ratio))
            return f"#{intensity:02x}2020" if ratio > 0 else f"#173a{intensity:02x}"
        ratio = 0.5 if high <= low else max(0.0, min(1.0, (value-low)/(high-low)))
        # dark teal -> green -> amber -> red; readable behind white text
        stops = [(8, 35, 48), (4, 78, 55), (105, 76, 12), (125, 25, 23)]
        pos = ratio * (len(stops)-1)
        idx = min(len(stops)-2, int(pos))
        frac = pos-idx
        rgb = tuple(int(stops[idx][i] + (stops[idx+1][i]-stops[idx][i])*frac) for i in range(3))
        return "#%02x%02x%02x" % rgb

    def cell_metric(self, chosen, hits, value_key):
        field = self.cell_field_var.get()
        base_key = 've1_curr' if value_key == 'sug_ve1' else 've2_curr'
        suggested = float(chosen[value_key].median())
        base = float(chosen[base_key].median())
        coverage = min(100.0, 100.0 * (1.0 - math.exp(-len(chosen) / 12.0)))
        corr_spread = float(chosen['clamped_corr'].std(ddof=0) * 100.0) if len(chosen) > 1 else 8.0
        repeatability = max(0.0, 100.0 - corr_spread * 14.0)
        stability = float(chosen['evidence_score'].median())
        lambda_quality = 100.0 * float(chosen['lambda_valid'].mean())
        confidence = 0.30*coverage + 0.30*repeatability + 0.25*stability + 0.15*lambda_quality
        lambda_valid = bool(chosen['lambda_valid'].any())
        metrics = {
            "VE sugerida": (suggested, f"{suggested:.0f}", "diverging", suggested-base, "azul reduz • verde neutro • vermelho soma"),
            "Delta VE": (suggested-base, f"{suggested-base:+.1f}", "diverging", suggested-base, "delta sobre a VE atual"),
            "Correção %": (float(chosen['clamped_corr'].median())*100.0, f"{float(chosen['clamped_corr'].median())*100.0:+.1f}", "diverging", None, "correção final limitada"),
            "Confiança": (confidence, f"{confidence:.0f}%", "sequential", None, "0–100%"),
            "Hits": (float(len(chosen)), f"{len(chosen)}", "sequential", None, "amostras aceitas"),
            "Erro lambda %": ((float(chosen['l_error_pct'].median()), f"{float(chosen['l_error_pct'].median()):+.1f}", "diverging", None, "positivo = pobre • negativo = rico")
                               if lambda_valid else (np.nan, "N/D", "diverging", None, "lambda ausente/inválida")),
            "Lambda média": ((float(chosen['lambda'].median()), f"{float(chosen['lambda'].median()):.3f}", "sequential", None, "lambda medida")
                              if lambda_valid else (np.nan, "N/D", "sequential", None, "lambda ausente/inválida")),
            "PW ms": (float(chosen['pw'].median()), f"{float(chosen['pw'].median()):.2f}", "sequential", None, "PW final em ms"),
            "Duty %": (float(chosen['duty_cycle'].median()), f"{float(chosen['duty_cycle'].median()):.1f}", "sequential", None, "duty dos injetores"),
            "VE2 vetor add": (float(chosen['ve2_add'].median()), f"{float(chosen['ve2_add'].median()):+.1f}", "diverging", None, "adição efetiva do vetor VE2"),
            "Autoridade %": (float(chosen['authority'].median()), f"{float(chosen['authority'].median()):.0f}%", "sequential", None, "limite de influência da evidência"),
            "Evidência %": (float(chosen['evidence_score'].median()), f"{float(chosen['evidence_score'].median()):.0f}%", "sequential", None, "qualidade física/temporal"),
            "Avanço °": (float(chosen['adv'].median()), f"{float(chosen['adv'].median()):.1f}", "sequential", None, "avanço final observado"),
            "PS10 erro bar": (float(chosen['fuel_error_bar'].median()), f"{float(chosen['fuel_error_bar'].median()):+.2f}", "diverging", None, "medido menos esperado"),
            "IAT °C": (float(chosen['iat'].median()), f"{float(chosen['iat'].median()):.0f}", "sequential", None, "temperatura do ar"),
            "CLT °C": (float(chosen['clt'].median()), f"{float(chosen['clt'].median()):.0f}", "sequential", None, "temperatura do motor"),
        }
        return metrics[field]

    def draw_2d_map(self, canvas, source_key, value_key, y_label):
        canvas.delete("all")
        if not self.analysis_cache:
            return
        w, h = canvas.winfo_width(), canvas.winfo_height()
        if w < 150 or h < 150:
            return
        data = pd.DataFrame(self.analysis_cache)
        y_values = data[source_key]
        min_r, max_r = float(data['causal_rpm'].min()), float(data['causal_rpm'].max())
        min_y, max_y = float(y_values.min()), float(y_values.max())
        if max_r <= min_r: max_r = min_r + 1
        if max_y <= min_y: max_y = min_y + 1
        rpm_bins = int(self.rpm_bins_var.get())
        load_bins = int(self.load_bins_var.get())
        left, top, right, bottom = 46, 22, 8, 28
        cw, ch = (w-left-right)/float(rpm_bins), (h-top-bottom)/float(load_bins)
        r_step, y_step = (max_r-min_r)/float(rpm_bins), (max_y-min_y)/float(load_bins)

        filter_mode = self.cell_filter_var.get()
        field = self.cell_field_var.get()
        populated = []
        cells = []

        for gy in range(load_bins):
            y_hi = max_y - gy*y_step
            if gy % max(1, load_bins//10) == 0:
                canvas.create_text(left-4, top+(gy+.5)*ch, text=f"{y_hi:.0f}", fill="#0cc", anchor="e", font=("Consolas", 7))
            for gx in range(rpm_bins):
                r_lo, r_hi = min_r+gx*r_step, min_r+(gx+1)*r_step
                y_lo = max_y-(gy+1)*y_step
                hits = data[(data['causal_rpm'].between(r_lo, r_hi)) & (data[source_key].between(y_lo, y_hi))]
                x1, y1 = left+gx*cw, top+gy*ch
                x2, y2 = x1+cw, y1+ch
                color, label, metric_value, palette, color_value = "#0b0e12", "", None, "sequential", None
                if not hits.empty:
                    stable = hits[hits['steady_fuel_cell']]
                    if filter_mode == "Somente estáveis": chosen = stable
                    elif filter_mode == "Transitórias": chosen = hits[hits['event_class'] == 'TRANSITORIO']
                    elif filter_mode == "Brutais": chosen = hits[hits['event_class'] == 'BRUTAL']
                    elif filter_mode == "Todas as amostras": chosen = hits
                    else: chosen = stable if not stable.empty else hits
                    if not chosen.empty:
                        metric_value, label, palette, color_value, legend = self.cell_metric(chosen, hits, value_key)
                        sample_for_scale = color_value if color_value is not None else metric_value
                        if np.isfinite(sample_for_scale): populated.append(float(sample_for_scale))
                        cells.append((x1, y1, x2, y2, label, sample_for_scale, palette))
                    else:
                        cells.append((x1, y1, x2, y2, "", np.nan, palette))
                else:
                    cells.append((x1, y1, x2, y2, "", np.nan, palette))

        if populated:
            lo, hi = np.percentile(populated, [5, 95]) if len(populated) > 2 else (min(populated), max(populated))
            extent = max(abs(lo), abs(hi), 0.1)
            div_lo, div_hi = -extent, extent
        else:
            lo, hi, div_lo, div_hi = 0.0, 1.0, -1.0, 1.0
            legend = "sem dados para o filtro"
        for x1, y1, x2, y2, label, sample, palette in cells:
            if np.isfinite(sample):
                color = self.matrix_color(sample, div_lo, div_hi, "diverging") if palette == "diverging" else self.matrix_color(sample, lo, hi)
            else:
                color = "#0b0e12"
            canvas.create_rectangle(x1, y1, x2, y2, fill=color, outline="#17232a")
            if label and cw >= 20 and ch >= 13:
                font_size = 7 if cw >= 34 and ch >= 20 else 6
                canvas.create_text((x1+x2)/2, (y1+y2)/2, text=label, fill="#f1f8f8", font=("Consolas", font_size, "bold"))

        tick_every = max(1, rpm_bins//10)
        for gx in range(0, rpm_bins, tick_every):
            canvas.create_text(left+(gx+.5)*cw, h-12, text=f"{min_r+gx*r_step:.0f}", fill="#0f0", font=("Consolas", 7))
        canvas.create_text(8, 8, text=y_label, fill="#00ffcc", anchor="w", font=("Consolas", 8, "bold"))
        canvas.create_text(w-8, 8, text="RPM →", fill="#00ffcc", anchor="e", font=("Consolas", 8, "bold"))
        self.matrix_legend.config(text=f"{field} • {legend} • grade {rpm_bins}×{load_bins}")

    def setup_3d_view(self):
        self.angle_x = 35; self.angle_y = -45
        self.morph_factor = 0.0
        self.is_animating = False
        self.is_playing = False
        self.replay_idx = 0
        self.replay_speed = 1.0
        self.replay_loop = True
        self.trail_length = tk.StringVar(value="50")
        
        self.surface_mode = tk.StringVar(value="VE Sugerida (Tratada)")
        self.color_mode = tk.StringVar(value="Lambda Error")
        self.show_vectors = tk.BooleanVar(value=False)
        self.pipeline_stage = tk.StringVar(value="FINAL")

        self.whatif_params = self.mix_params.copy()
        self.whatif_enabled = tk.BooleanVar(value=False)

        self.smooth_val = tk.DoubleVar(value=0.0)
        self.aggr_val = tk.DoubleVar(value=1.0)
        self.noise_gate = tk.DoubleVar(value=0.5)

        ctrl = tk.Frame(self.tab_3d, bg="#0a0a0a")
        ctrl.pack(side="top", fill="x", padx=5, pady=2)

        btn_grp = tk.Frame(ctrl, bg="#0a0a0a")
        btn_grp.pack(side="left", padx=5)
        tk.Button(btn_grp, text="3D ISOMÉTRICO", command=lambda: self.set_3d_angles(35, -45), bg="#222", fg="#00ffcc", font=("Consolas", 8, "bold")).pack(side="left", padx=2)
        tk.Button(btn_grp, text="VISTA DE TOPO", command=lambda: self.set_3d_angles(89, 0), bg="#222", fg="#00ffcc", font=("Consolas", 8, "bold")).pack(side="left", padx=2)

        anim_grp = tk.Frame(ctrl, bg="#0a0a0a", highlightthickness=1, highlightbackground="#222")
        anim_grp.pack(side="left", padx=5, pady=2)
        tk.Button(anim_grp, text="▶ MORPH", command=self.toggle_animation, bg="#004433", fg="#00ffcc", font=("Consolas", 8, "bold")).pack(side="left", padx=2)
        self.sld_morph = tk.Scale(anim_grp, from_=0.0, to=1.0, resolution=0.01, orient="horizontal", length=80, bg="#0a0a0a", fg="#00ffcc", highlightthickness=0, command=self.on_morph_change)
        self.sld_morph.pack(side="left", padx=2)

        tk.Label(ctrl, text="Superfície:", fg="#888", bg="#0a0a0a", font=("Consolas", 8)).pack(side="left", padx=(5,0))
        cb_surf = ttk.Combobox(ctrl, textvariable=self.surface_mode, values=[
            "VE Sugerida (Tratada)", "VE Original (Atual)", "Delta de Correção (Calor)", 
            "REAL", "SUGERIDA", "BOTH", "DIFFERENCE", "MORPH"
        ], width=20, state="readonly")
        cb_surf.pack(side="left", padx=2)
        cb_surf.bind("<<ComboboxSelected>>", lambda e: self.draw_3d_mesh())

        tk.Label(ctrl, text="Color Map:", fg="#888", bg="#0a0a0a", font=("Consolas", 8)).pack(side="left", padx=(5,0))
        cb_col = ttk.Combobox(ctrl, textvariable=self.color_mode, values=["Lambda Error", "VE Delta", "Correction %", "RPM Dot", "MAP Dot", "TPS Dot", "Gammae", "Gego", "Confidence", "Sample Count"], width=12, state="readonly")
        cb_col.pack(side="left", padx=2)
        cb_col.bind("<<ComboboxSelected>>", lambda e: self.draw_3d_mesh())

        cb_vec = tk.Checkbutton(ctrl, text="Vetores", variable=self.show_vectors, command=self.draw_3d_mesh, bg="#0a0a0a", fg="#0ff", selectcolor="#000", font=("Consolas", 8))
        cb_vec.pack(side="left", padx=2)

        tk.Label(ctrl, text="Rastro:", fg="#888", bg="#0a0a0a", font=("Consolas", 8)).pack(side="left", padx=(5,0))
        cb_tr = ttk.Combobox(ctrl, textvariable=self.trail_length, values=["OFF", "10", "25", "50", "100", "250", "ALL"], width=5, state="readonly")
        cb_tr.pack(side="left", padx=2)
        cb_tr.bind("<<ComboboxSelected>>", lambda e: self.draw_3d_mesh())

        self.sld_rot = tk.Scale(ctrl, from_=-180, to=180, orient="horizontal", length=70, bg="#0a0a0a", fg="#fff", highlightthickness=0, command=self.update_3d)
        self.sld_rot.set(self.angle_y); self.sld_rot.pack(side="right", padx=2)
        tk.Label(ctrl, text="Rot:", fg="#888", bg="#0a0a0a", font=("Consolas", 8)).pack(side="right")

        self.sld_elev = tk.Scale(ctrl, from_=0, to=90, orient="horizontal", length=70, bg="#0a0a0a", fg="#fff", highlightthickness=0, command=self.update_3d)
        self.sld_elev.set(self.angle_x); self.sld_elev.pack(side="right", padx=2)
        tk.Label(ctrl, text="Elev:", fg="#888", bg="#0a0a0a", font=("Consolas", 8)).pack(side="right")

        replay_bar = tk.Frame(self.tab_3d, bg="#0d0d12", height=35)
        replay_bar.pack(side="top", fill="x", padx=5, pady=2)

        tk.Button(replay_bar, text="|<", command=self.replay_first, bg="#1a1a24", fg="#00ffcc", width=3, font=("Consolas", 8, "bold")).pack(side="left", padx=1)
        tk.Button(replay_bar, text="<<", command=lambda: self.replay_step(-10), bg="#1a1a24", fg="#00ffcc", width=3, font=("Consolas", 8, "bold")).pack(side="left", padx=1)
        tk.Button(replay_bar, text="<", command=lambda: self.replay_step(-1), bg="#1a1a24", fg="#00ffcc", width=3, font=("Consolas", 8, "bold")).pack(side="left", padx=1)
        
        self.btn_play = tk.Button(replay_bar, text="PLAY", command=self.toggle_play, bg="#004433", fg="#00ffcc", width=6, font=("Consolas", 8, "bold"))
        self.btn_play.pack(side="left", padx=3)

        tk.Button(replay_bar, text=">", command=lambda: self.replay_step(1), bg="#1a1a24", fg="#00ffcc", width=3, font=("Consolas", 8, "bold")).pack(side="left", padx=1)
        tk.Button(replay_bar, text=">>", command=lambda: self.replay_step(10), bg="#1a1a24", fg="#00ffcc", width=3, font=("Consolas", 8, "bold")).pack(side="left", padx=1)
        tk.Button(replay_bar, text=">|", command=self.replay_last, bg="#1a1a24", fg="#00ffcc", width=3, font=("Consolas", 8, "bold")).pack(side="left", padx=1)

        tk.Button(replay_bar, text="⏮ PREV EVENT", command=lambda: self.jump_event(-1), bg="#221500", fg="#ffaa00", font=("Consolas", 8, "bold")).pack(side="left", padx=5)
        tk.Button(replay_bar, text="NEXT EVENT ⏭", command=lambda: self.jump_event(1), bg="#221500", fg="#ffaa00", font=("Consolas", 8, "bold")).pack(side="left", padx=1)

        self.lbl_replay_info = tk.Label(replay_bar, text="FRAME [ 0 / 0 ] | TIME: 0.0s", fg="#00ffcc", bg="#0d0d12", font=("Consolas", 9, "bold"))
        self.lbl_replay_info.pack(side="left", padx=10)

        self.sld_timeline = tk.Scale(replay_bar, from_=0, to=100, orient="horizontal", bg="#0d0d12", fg="#0ff", highlightthickness=0, showvalue=False, command=self.on_timeline_slide)
        self.sld_timeline.pack(side="left", fill="x", expand=True, padx=5)

        tk.Label(replay_bar, text="Speed:", fg="#888", bg="#0d0d12", font=("Consolas", 8)).pack(side="left")
        self.cb_speed = ttk.Combobox(replay_bar, values=["0.1x", "0.25x", "0.5x", "1.0x", "2.0x", "4.0x", "8.0x"], width=5, state="readonly")
        self.cb_speed.set("1.0x")
        self.cb_speed.pack(side="left", padx=2)
        self.cb_speed.bind("<<ComboboxSelected>>", self.on_speed_change)

        main_body = tk.Frame(self.tab_3d, bg="#020204")
        main_body.pack(fill="both", expand=True)

        self.side_panel = tk.Frame(main_body, bg="#08080c", width=260)
        self.side_panel.pack(side="left", fill="y", padx=2, pady=2)
        self.side_panel.pack_propagate(False)

        tk.Label(self.side_panel, text="SIMULADOR WHAT-IF (A/B)", fg="#ffaa00", bg="#08080c", font=("Consolas", 9, "bold")).pack(pady=5)
        
        cb_wif = tk.Checkbutton(self.side_panel, text="Ativar Simulação What-If", variable=self.whatif_enabled, command=self.on_whatif_toggle, bg="#08080c", fg="#ffaa00", selectcolor="#000", font=("Consolas", 8))
        cb_wif.pack(anchor="w", padx=10)

        weight_f = tk.LabelFrame(self.side_panel, text=" Peso Fusão VE1 / VE2 ", fg="#00ffcc", bg="#08080c", font=("Consolas", 8))
        weight_f.pack(fill="x", padx=5, pady=5)
        
        self.sld_weight_panel = tk.Scale(weight_f, from_=0.0, to=1.0, resolution=0.05, orient="horizontal", bg="#08080c", fg="#0ff", highlightthickness=0, command=self.on_weight_change)
        self.sld_weight_panel.set(self.mix_params.get('w_ve1', 0.70))
        self.sld_weight_panel.pack(fill="x", padx=5)

        adj_f = tk.LabelFrame(self.side_panel, text=" Ajustes de Superfície ", fg="#888", bg="#08080c", font=("Consolas", 8))
        adj_f.pack(fill="x", padx=5, pady=5)

        tk.Label(adj_f, text="Suavização:", fg="#aaa", bg="#08080c", font=("Consolas", 7)).pack(anchor="w", padx=5)
        tk.Scale(adj_f, from_=0.0, to=1.0, resolution=0.05, variable=self.smooth_val, orient="horizontal", bg="#08080c", fg="#fff", highlightthickness=0, command=lambda e: self.draw_3d_mesh()).pack(fill="x", padx=5)

        tk.Label(adj_f, text="Agressividade:", fg="#aaa", bg="#08080c", font=("Consolas", 7)).pack(anchor="w", padx=5)
        tk.Scale(adj_f, from_=0.2, to=2.0, resolution=0.1, variable=self.aggr_val, orient="horizontal", bg="#08080c", fg="#fff", highlightthickness=0, command=lambda e: self.draw_3d_mesh()).pack(fill="x", padx=5)

        tk.Label(adj_f, text="Filtro Ruído%:", fg="#aaa", bg="#08080c", font=("Consolas", 7)).pack(anchor="w", padx=5)
        tk.Scale(adj_f, from_=0.0, to=3.0, resolution=0.1, variable=self.noise_gate, orient="horizontal", bg="#08080c", fg="#fff", highlightthickness=0, command=lambda e: self.draw_3d_mesh()).pack(fill="x", padx=5)

        pipe_f = tk.LabelFrame(self.side_panel, text=" Pipeline de Correção ", fg="#888", bg="#08080c", font=("Consolas", 8))
        pipe_f.pack(fill="x", padx=5, pady=5)

        tk.Label(pipe_f, text="Visualizar Estágio:", fg="#aaa", bg="#08080c", font=("Consolas", 7)).pack(anchor="w", padx=5)
        cb_pipe = ttk.Combobox(pipe_f, textvariable=self.pipeline_stage, values=["RAW", "POST-DEADBAND", "POST-CLAMP", "FINAL"], state="readonly")
        cb_pipe.pack(fill="x", padx=5, pady=2)
        cb_pipe.bind("<<ComboboxSelected>>", lambda e: self.draw_3d_mesh())

        self.cell_inspect_txt = tk.Text(self.side_panel, bg="#030305", fg="#00ffcc", font=("Consolas", 8), bd=0, relief="flat", padx=5, pady=5)
        self.cell_inspect_txt.pack(fill="both", expand=True, padx=5, pady=5)

        self.canv_container = tk.Frame(main_body, bg="#020204")
        self.canv_container.pack(side="right", fill="both", expand=True)

        self.canv_3d = tk.Canvas(self.canv_container, bg="#020204", highlightthickness=0)
        self.canv_3d.pack(fill="both", expand=True)

        self.canv_3d.bind("<Configure>", lambda e: self.draw_3d_mesh())
        self.canv_3d.bind("<Button-1>", self.on_3d_click)
        self.canv_3d.bind("<Motion>", self.on_3d_hover)

        self.process_3d_data()

    def on_weight_change(self, val):
        self.mix_params['w_ve1'] = float(val)
        self.process_3d_data()
        self.draw_3d_mesh()

    def set_3d_angles(self, elev, rot):
        self.angle_x = elev; self.angle_y = rot
        self.sld_elev.set(elev); self.sld_rot.set(rot)
        self.draw_3d_mesh()

    def update_3d(self, _=None):
        self.angle_x = float(self.sld_elev.get())
        self.angle_y = float(self.sld_rot.get())
        self.draw_3d_mesh()

    def on_morph_change(self, val):
        self.morph_factor = float(val)
        self.draw_3d_mesh()

    def toggle_animation(self):
        self.is_animating = not self.is_animating
        if self._anim_after_id:
            self.after_cancel(self._anim_after_id)
            self._anim_after_id = None
        if self.is_animating:
            self.run_animation()

    def run_animation(self):
        if not self.is_animating: return
        self.morph_factor += 0.03
        if self.morph_factor > 1.0:
            self.morph_factor = 0.0
        self.sld_morph.set(self.morph_factor)
        self.draw_3d_mesh()
        self._anim_after_id = self.after(30, self.run_animation)

    def on_speed_change(self, event):
        sp_str = self.cb_speed.get().replace("x", "")
        try: self.replay_speed = float(sp_str)
        except: self.replay_speed = 1.0

    def toggle_play(self):
        self.is_playing = not self.is_playing
        self.btn_play.config(text="PAUSE" if self.is_playing else "PLAY", bg="#884400" if self.is_playing else "#004433")
        
        if self._replay_after_id:
            self.after_cancel(self._replay_after_id)
            self._replay_after_id = None

        if self.is_playing:
            self.run_replay_loop()

    def replay_first(self):
        self.replay_idx = 0
        self.sync_replay_ui()

    def replay_last(self):
        if hasattr(self, 'replay_frames') and len(self.replay_frames) > 0:
            self.replay_idx = len(self.replay_frames) - 1
            self.sync_replay_ui()

    def replay_step(self, step):
        if not hasattr(self, 'replay_frames') or len(self.replay_frames) == 0: return
        self.replay_idx = int(np.clip(self.replay_idx + step, 0, len(self.replay_frames) - 1))
        self.sync_replay_ui()

    def jump_event(self, direction):
        if not hasattr(self, 'replay_frames') or len(self.replay_frames) == 0: return
        cur = self.replay_idx
        n = len(self.replay_frames)
        step = 1 if direction > 0 else -1
        idx = cur + step
        while 0 <= idx < n:
            fr = self.replay_frames[idx]
            if fr.get('event_marker'):
                self.replay_idx = idx
                self.sync_replay_ui()
                return
            idx += step

    def on_timeline_slide(self, val):
        if hasattr(self, 'replay_frames') and len(self.replay_frames) > 0:
            pct = float(val) / 100.0
            self.replay_idx = int(pct * (len(self.replay_frames) - 1))
            self.sync_replay_ui(from_slider=True)

    def run_replay_loop(self):
        if not self.is_playing: return
        if not hasattr(self, 'replay_frames') or len(self.replay_frames) == 0: return

        self.replay_idx += 1
        if self.replay_idx >= len(self.replay_frames):
            if self.replay_loop:
                self.replay_idx = 0
            else:
                self.is_playing = False
                self.btn_play.config(text="PLAY", bg="#004433")
                return

        self.sync_replay_ui()
        dt_ms = int(30 / max(0.1, self.replay_speed))
        
        if self._replay_after_id:
            self.after_cancel(self._replay_after_id)
        self._replay_after_id = self.after(dt_ms, self.run_replay_loop)

    def sync_replay_ui(self, from_slider=False):
        if not hasattr(self, 'replay_frames') or len(self.replay_frames) == 0: return
        total = len(self.replay_frames)
        curr_frame = self.replay_frames[self.replay_idx]
        
        if not from_slider:
            pct = (self.replay_idx / max(1, total - 1)) * 100.0
            self.sld_timeline.set(pct)

        self.lbl_replay_info.config(text=f"FRAME [ {self.replay_idx + 1} / {total} ] | TIME: {curr_frame['time']:.2f}s")
        self.draw_3d_mesh()

    def on_whatif_toggle(self):
        self.process_3d_data()
        self.draw_3d_mesh()

    def process_3d_data(self):
        active_params = self.whatif_params if self.whatif_enabled.get() else self.mix_params
        cache = self.build_analysis_cache(active_params)
        if not cache:
            return
        data = pd.DataFrame(cache)
        min_r, max_r = data['causal_rpm'].min(), data['causal_rpm'].max()
        min_m, max_m = data['causal_map'].min(), data['causal_map'].max()
        
        self.r_step = (max_r - min_r) / 15 if max_r > min_r else 1
        self.m_step = (max_m - min_m) / 15 if max_m > min_m else 1
        self.min_r, self.max_r = min_r, max_r
        self.min_m, self.max_m = min_m, max_m

        self.z_orig = np.zeros((16, 16))
        self.z_sug = np.zeros((16, 16))
        self.z_diff = np.zeros((16, 16))
        self.z_mask = np.zeros((16, 16), dtype=bool)
        self.cell_samples = np.zeros((16, 16), dtype=int)
        self.cell_confidence = np.zeros((16, 16))
        self.cell_history = [[[] for _ in range(16)] for _ in range(16)]

        for y in range(16):
            vm = max_m - (y * self.m_step)
            for x in range(16):
                vr = min_r + (x * self.r_step)
                hits = data[(data['causal_rpm'].between(vr - self.r_step*0.5, vr + self.r_step*0.5)) &
                            (data['causal_map'].between(vm - self.m_step*0.5, vm + self.m_step*0.5))]
                if not hits.empty:
                    self.cell_samples[y, x] = len(hits)
                    stable = hits[hits['steady_fuel_cell']]
                    chosen = stable if not stable.empty else hits
                    self.z_orig[y, x] = chosen['ve1_curr'].median()
                    self.z_sug[y, x] = chosen['sug_ve1'].median()
                    self.z_diff[y, x] = self.z_sug[y, x] - self.z_orig[y, x]
                    self.z_mask[y, x] = True

                    coverage = min(100.0, 100.0 * (1.0 - math.exp(-len(hits)/12.0)))
                    repeatability = max(0.0, 100.0 - float(hits['clamped_corr'].std(ddof=0))*1400.0)
                    stability = float(hits['evidence_score'].median())
                    lambda_quality = 100.0 * float(hits['lambda_valid'].mean())
                    conf = 0.30*coverage + 0.30*repeatability + 0.25*stability + 0.15*lambda_quality
                    self.cell_confidence[y, x] = conf

        self.replay_frames = []
        for cached in cache:
            ans = cached.copy()
            rx = int(np.clip((ans['causal_rpm'] - min_r) / self.r_step, 0, 15)) if self.r_step > 0 else 0
            ry = int(np.clip((max_m - ans['causal_map']) / self.m_step, 0, 15)) if self.m_step > 0 else 0
                
            ans['grid_x'] = rx
            ans['grid_y'] = ry

            event_m = None
            if ans['tps_dot'] > 60 or ans['map_dot'] > 40: event_m = "▲ ACCEL"
            elif ans['tps_dot'] < -50: event_m = "▼ DECEL"
            elif abs(ans['l_error_pct']) > 15: event_m = "✦ SEVERE ERROR"
            elif ans['map'] > 100: event_m = "⚡ BOOST"
            elif abs(ans['raw_corr']) > 0.01 and ans['effective_corr'] == 0: event_m = "■ DEADBAND"

            ans['event_marker'] = event_m
            self.replay_frames.append(ans)
            self.cell_history[ry][rx].append(ans)

        self.replay_idx = 0
        self.sld_timeline.set(0)

    def project_point(self, x, y, z, cx, cy):
        rad_x, rad_y = math.radians(self.angle_x), math.radians(self.angle_y)
        rx = x * math.cos(rad_y) - y * math.sin(rad_y)
        ry = x * math.sin(rad_y) + y * math.cos(rad_y)
        rz = z * math.cos(rad_x) - ry * math.sin(rad_x)
        r_depth = z * math.sin(rad_x) + ry * math.cos(rad_x)
        scale = 18.0
        px = cx + rx * scale
        py = cy - rz * scale
        return px, py, r_depth

    def get_spectrum_color(self, val, is_active, mode):
        if not is_active: return "#0c0d12", "#181a24"
        
        gate = self.noise_gate.get()
        if mode in ["Lambda Error", "VE Delta", "Correction %"]:
            if abs(val) < gate: return "#00ff88", "#004422"
            if val > 0:
                if val < 2.0: return "#ffcc00", "#554400"
                elif val < 5.0: return "#ff6600", "#662200"
                else: return "#ff0055", "#660022"
            else:
                if val > -2.0: return "#00ccff", "#004455"
                elif val > -5.0: return "#0066ff", "#002266"
                else: return "#7700ff", "#330066"
        elif mode in ["RPM Dot", "MAP Dot", "TPS Dot"]:
            v_norm = min(1.0, abs(val) / 100.0)
            r = int(v_norm * 255); b = int((1 - v_norm) * 255)
            return f"#{r:02x}88{b:02x}", f"#{int(r*0.4):02x}22{int(b*0.4):02x}"
        elif mode in ["Confidence", "Sample Count"]:
            v_norm = min(1.0, val / 100.0)
            g = int(v_norm * 255)
            return f"#00{g:02x}aa", f"#00{int(g*0.4):02x}44"
        else:
            return "#00ff88", "#004422"

    def draw_3d_mesh(self):
        self.canv_3d.delete("all")
        w, h = self.canv_3d.winfo_width(), self.canv_3d.winfo_height()
        if w < 100: return
        cx, cy = w / 2, h / 2 + 80

        aggr = self.aggr_val.get()
        smooth = self.smooth_val.get()
        s_mode = self.surface_mode.get()
        c_mode = self.color_mode.get()

        if s_mode in ["REAL", "VE Original (Atual)"]:
            z_current = self.z_orig.copy()
        elif s_mode in ["SUGERIDA", "VE Sugerida (Tratada)"]:
            z_current = self.z_sug.copy()
        elif s_mode in ["DIFFERENCE", "Delta de Correção (Calor)"]:
            z_current = self.z_diff.copy() + 40
        else:
            z_current = self.z_orig + ((self.z_sug - self.z_orig) * self.morph_factor * aggr)

        if smooth > 0:
            z_smoothed = z_current.copy()
            for y in range(1, 15):
                for x in range(1, 15):
                    if self.z_mask[y, x]:
                        neighbors = z_current[y-1:y+2, x-1:x+2]
                        avg = np.average(neighbors)
                        z_smoothed[y, x] = (z_current[y, x] * (1.0 - smooth)) + (avg * smooth)
            z_current = z_smoothed

        polygons = []
        self.poly_map = {}

        for y in range(15):
            for x in range(15):
                pts = []
                depths = []
                mask_act = self.z_mask[y:y+2, x:x+2].any()

                if c_mode == "Lambda Error": val_col = self.z_diff[y:y+2, x:x+2].mean() * (self.morph_factor if s_mode == "MORPH" else 1.0)
                elif c_mode == "VE Delta": val_col = self.z_diff[y:y+2, x:x+2].mean()
                elif c_mode == "Confidence": val_col = self.cell_confidence[y:y+2, x:x+2].mean()
                elif c_mode == "Sample Count": val_col = self.cell_samples[y:y+2, x:x+2].mean()
                else: val_col = self.z_diff[y:y+2, x:x+2].mean()

                for dx, dy in [(0,0), (1,0), (1,1), (0,1)]:
                    gx, gy = (x + dx) - 7.5, (y + dy) - 7.5
                    zc = (z_current[y+dy, x+dx] - 40) / 4.0
                    px, py, d = self.project_point(gx, gy, zc, cx, cy)
                    pts.extend([px, py])
                    depths.append(d)

                avg_depth = sum(depths) / 4.0
                fill_col, line_col = self.get_spectrum_color(val_col, mask_act, c_mode)
                
                poly_obj = {
                    'depth': avg_depth, 'pts': pts, 'fill': fill_col, 
                    'line': line_col, 'x': x, 'y': y, 'active': mask_act, 'val': val_col,
                    'z_orig': self.z_orig[y, x], 'z_sug': self.z_sug[y, x]
                }
                polygons.append(poly_obj)

        polygons.sort(key=lambda p: p['depth'])

        for p in polygons:
            fill_c = p['line'] if self.morph_factor < 0.05 and s_mode == "MORPH" else p['fill']
            out_c = p['fill'] if self.morph_factor < 0.05 and s_mode == "MORPH" else "#ffffff" if abs(p['val']) > 4.0 else p['line']
            pid = self.canv_3d.create_polygon(p['pts'], fill=fill_c, outline=out_c, width=1)
            self.poly_map[pid] = p

            if self.show_vectors.get() and p['active']:
                gx, gy = p['x'] - 7.5, p['y'] - 7.5
                px1, py1, _ = self.project_point(gx, gy, (p['z_orig'] - 40) / 4.0, cx, cy)
                px2, py2, _ = self.project_point(gx, gy, (p['z_sug'] - 40) / 4.0, cx, cy)
                self.canv_3d.create_line(px1, py1, px2, py2, fill="#00ffff", width=2, arrow=tk.LAST)

            if p['active'] and abs(p['val']) > self.noise_gate.get():
                pts = p['pts']
                top_x = (pts[0] + pts[2] + pts[4] + pts[6]) / 4
                top_y = (pts[1] + pts[3] + pts[5] + pts[7]) / 4
                self.canv_3d.create_rectangle(top_x-2, top_y-2, top_x+2, top_y+2, fill="#fff", outline="#000")

        if hasattr(self, 'replay_frames') and len(self.replay_frames) > 0:
            tr_opt = self.trail_length.get()
            if tr_opt != "OFF":
                max_tr = len(self.replay_frames) if tr_opt == "ALL" else int(tr_opt)
                start_tr = max(0, self.replay_idx - max_tr)
                trail_pts = []

                for idx in range(start_tr, self.replay_idx + 1):
                    fr = self.replay_frames[idx]
                    gx = fr['grid_x'] - 7.5
                    gy = fr['grid_y'] - 7.5
                    zc = (fr['ve1_curr'] - 40) / 4.0
                    px, py, _ = self.project_point(gx, gy, zc, cx, cy)
                    
                    alpha = (idx - start_tr + 1) / max(1, (self.replay_idx - start_tr + 1))
                    trail_pts.append((px, py, alpha, fr.get('event_marker')))

                for i in range(len(trail_pts) - 1):
                    x1, y1, a1, ev1 = trail_pts[i]
                    x2, y2, a2, ev2 = trail_pts[i+1]
                    c_val = int(a2 * 255)
                    color = f"#00{c_val:02x}{c_val:02x}"
                    self.canv_3d.create_line(x1, y1, x2, y2, fill=color, width=2)

                    if ev2:
                        self.canv_3d.create_text(x2, y2 - 8, text=ev2, fill="#ffaa00", font=("Consolas", 7, "bold"))

                curr_fr = self.replay_frames[self.replay_idx]
                gx = curr_fr['grid_x'] - 7.5
                gy = curr_fr['grid_y'] - 7.5
                zc = (curr_fr['ve1_curr'] - 40) / 4.0
                c_px, c_py, _ = self.project_point(gx, gy, zc, cx, cy)

                self.canv_3d.create_oval(c_px-6, c_py-6, c_px+6, c_py+6, fill="#ff0055", outline="#ffffff", width=2)
                self.canv_3d.create_oval(c_px-12, c_py-12, c_px+12, c_py+12, outline="#ff0055", width=1)

                self.draw_tactical_hud(curr_fr)

    def draw_tactical_hud(self, fr):
        l_status = f"{fr['lambda']:.3f}" if fr.get('lambda_valid', True) else "OFF / N/A"
        hud_txt = (
            f" [ HUD TÁTICO TEMPO REAL - V90 PASS32 CAUSAL ]\n"
            f" RPM: {fr['rpm']:.0f} | MAP: {fr['map']:.1f} kPa | TPS: {fr['tps']:.1f}%\n"
            f" LAMBDA: {l_status} (TGT: {fr['target_used']:.3f}) | ERR: {fr['l_error_pct']:+.1f}%\n"
            f" VE CURR: {fr['ve1_curr']:.1f} -> SUG: {fr['sug_ve1']:.1f} (DELTA: {fr['sug_ve1']-fr['ve1_curr']:+.1f})\n"
            f" STATE: {fr['phase']} | VIOLENCE: {fr['violence']}\n"
            f" GAMMAE: {fr['gamma_val']:.1f}% | GEGO: {fr['gego']:.1f}%\n"
            f" RPM_DOT: {fr['rpm_dot']:.0f} | MAP_DOT: {fr['map_dot']:.1f} | TPS_DOT: {fr['tps_dot']:.1f}\n"
            f" 720 DEG PHASE: {fr['phase_720']:.1f}° | MASS DELTA: {fr['mass_delta']:+.3f}"
        )
        self.canv_3d.create_rectangle(10, 10, 380, 145, fill="#08080c", outline="#00ffcc", width=1)
        self.canv_3d.create_text(20, 20, text=hud_txt, fill="#00ffcc", font=("Consolas", 8), anchor="nw")

    def on_3d_click(self, event):
        item = self.canv_3d.find_withtag("current")
        if item and item[0] in self.poly_map:
            p = self.poly_map[item[0]]
            x, y = p['x'], p['y']
            samples = self.cell_samples[y, x]
            conf = self.cell_confidence[y, x]
            diff = self.z_diff[y, x]
            
            info = (
                f"=== INSPEÇÃO DE CÉLULA [{x},{y}] ===\n"
                f"> Amostras Totais: {samples}\n"
                f"> Confiança: {conf:.1f}%\n"
                f"> VE Atual: {p['z_orig']:.1f}\n"
                f"> VE Sugerida: {p['z_sug']:.1f}\n"
                f"> Delta VE: {diff:+.1f}\n\n"
                f"Histórico Replay nesta célula:\n"
                f"Ativações: {len(self.cell_history[y][x])} frames"
            )
            self.cell_inspect_txt.delete("1.0", tk.END)
            self.cell_inspect_txt.insert(tk.END, info)

    def on_3d_hover(self, event):
        item = self.canv_3d.find_withtag("current")
        if item and item[0] in self.poly_map:
            self.canv_3d.config(cursor="hand2")
        else:
            self.canv_3d.config(cursor="")


class VIC_Quantum_V90:
    def __init__(self, root):
        self.root = root
        self.root.title("VIC QUANTUM V90 - PASS32 CAUSAL INTELLIGENCE")
        
        screen_w = self.root.winfo_screenwidth()
        screen_h = self.root.winfo_screenheight()
        win_w, win_h = min(1420, screen_w - 26), min(900, screen_h - 44)
        self.root.geometry(f"{win_w}x{win_h}")
        self.root.configure(bg="#050505")
        
        self.df = None
        self.sample_period_ms = 12.0
        self.view_start = 0; self.view_range = 100
        self.sel_start = 0; self.sel_end = 0
        self.cursor_line = None; self.zoom_rect = None
        self.ab_segment_a = None
        
        self.mix_params = {
            'w_ve1': 0.7, 'use_custom_target': False,
            'custom_target_val': 0.85, 'ignore_gammae': True, 
            'clamp_matrix': 0.01, 'max_clamp': 0.25, 'delay_frames': 4, 'delay_ms': 50,
            'learn_rate': 0.8, 'enable_target_search': False,
            'has_lambda_sensor': True, 'sample_period_ms': 12.0,
            'fuel_base_bar': 2.0, 'ps10_tolerance_bar': 0.18,
            'stoich': QuantumEngineCore.STOICH_DEFAULT
        }
        
        self.setup_styles()
        self.create_widgets()

    def setup_styles(self):
        style = ttk.Style()
        style.theme_use('clam')
        style.configure("Quantum.Horizontal.TScrollbar", background="#111", bordercolor="#000", arrowcolor="#0f0")
        style.configure("TNotebook", background="#0a0a0a", borderwidth=0)
        style.configure("TNotebook.Tab", background="#151515", foreground="#888", padding=[10, 5], font=("Consolas", 9, "bold"))
        style.map("TNotebook.Tab", background=[("selected", "#004433")], foreground=[("selected", "#00ffcc")])

    def create_widgets(self):
        self.header = tk.Frame(self.root, bg="#000", height=52)
        self.header.pack(side="top", fill="x", padx=5, pady=2)
        self.monitors = {}
        channels = [("RPM", "#0f0"), ("MAP", "#0ff"), ("TPS", "#ff0"), ("PW", "#fff"), 
                    ("ADV", "#f80"), ("L_ACT", "#f0f"), ("L_TGT", "#aaa"), ("DUTY", "#f44")]
        
        for name, color in channels:
            f = tk.Frame(self.header, bg="#0a0a0a", highlightthickness=1, highlightbackground="#222")
            f.pack(side="left", fill="both", expand=True, padx=1)
            tk.Label(f, text=name, font=("Consolas", 7), fg="#555", bg="#0a0a0a").pack()
            v = tk.Label(f, text="---", font=("Consolas", 12, "bold"), fg=color, bg="#0a0a0a")
            v.pack(); self.monitors[name] = v

        self.paned = tk.PanedWindow(self.root, orient="horizontal", bg="#111", bd=0, sashwidth=4)
        self.paned.pack(expand=True, fill="both")

        self.left_panel = tk.Frame(self.paned, bg="#0a0a0a", width=225)
        self.left_panel.pack_propagate(False)
        self.paned.add(self.left_panel)
        
        tk.Label(self.left_panel, text="BANDIT 1200 TURBO", font=("Impact", 17), fg="#00ffcc", bg="#0a0a0a").pack(pady=5)

        # SELEÇÃO MANUAL / STATUS DA LAMBDA
        l_status_frame = tk.LabelFrame(self.left_panel, text=" LAMBDA ", font=("Consolas", 8), fg="#666", bg="#0a0a0a", padx=5, pady=2)
        l_status_frame.pack(fill="x", padx=6, pady=3)
        
        self.has_lambda_var = tk.BooleanVar(value=True)
        tk.Checkbutton(l_status_frame, text="Disponível no log", variable=self.has_lambda_var, command=self.sync_params, bg="#0a0a0a", fg="#f0f", selectcolor="#000", font=("Consolas", 8, "bold")).pack(anchor="w")

        d_frame = tk.LabelFrame(self.left_panel, text=" CONVERGÊNCIA ", font=("Consolas", 8), fg="#666", bg="#0a0a0a", padx=5, pady=2)
        d_frame.pack(fill="x", padx=6, pady=3)
        
        self.delay_caption = tk.StringVar(value="LAMBDA DELAY (ms) | 50 ms ≈ 4f")
        tk.Label(d_frame, textvariable=self.delay_caption, font=("Consolas", 8), fg="#0ff", bg="#0a0a0a").pack(anchor="w")
        self.sld_delay = tk.Scale(d_frame, from_=0, to=500, resolution=5, orient="horizontal", bg="#0a0a0a", fg="#fff", highlightthickness=0, command=self.on_delay_ms)
        self.sld_delay.set(50); self.sld_delay.pack(fill="x")

        tk.Label(d_frame, text="LEARN RATE (AGRESSIVIDADE)", font=("Consolas", 8), fg="#0ff", bg="#0a0a0a").pack(anchor="w")
        self.sld_learn = tk.Scale(d_frame, from_=0.1, to=1.5, resolution=0.1, orient="horizontal", bg="#0a0a0a", fg="#fff", highlightthickness=0, command=lambda v: self.update_param('learn_rate', v))
        self.sld_learn.set(0.8); self.sld_learn.pack(fill="x")

        t_frame = tk.LabelFrame(self.left_panel, text=" ALVO ", font=("Consolas", 8), fg="#666", bg="#0a0a0a", padx=5, pady=2)
        t_frame.pack(fill="x", padx=6, pady=3)
        
        self.target_toggle = tk.BooleanVar(value=False)
        tk.Checkbutton(t_frame, text="FORCE GHOST TARGET", variable=self.target_toggle, command=self.sync_params, bg="#0a0a0a", fg="#0ff", selectcolor="#000", font=("Consolas", 8)).pack(anchor="w")
        
        self.search_toggle = tk.BooleanVar(value=False)
        tk.Checkbutton(t_frame, text="ENABLE TARGET SEARCH (AI)", variable=self.search_toggle, command=self.sync_params, bg="#0a0a0a", fg="#ff0", selectcolor="#000", font=("Consolas", 8)).pack(anchor="w")

        self.target_val = tk.DoubleVar(value=0.85)
        tk.Scale(t_frame, from_=0.70, to=1.10, resolution=0.01, orient="horizontal", variable=self.target_val, command=lambda v: self.sync_params(), bg="#0a0a0a", fg="#fff", highlightthickness=0).pack(fill="x")

        self.w_scale = tk.Scale(self.left_panel, from_=0, to=1, resolution=0.01, orient="horizontal", bg="#0a0a0a", fg="#0f0", label="VE1 ← peso → VE2", highlightthickness=0, command=lambda v: self.update_param('w_ve1', v))
        self.w_scale.set(0.70); self.w_scale.pack(fill="x", padx=6, pady=3)
        
        btn_f = tk.Frame(self.left_panel, bg="#0a0a0a")
        btn_f.pack(fill="x", side="bottom", pady=5)
        tk.Button(btn_f, text="ABRIR LOG", command=self.load_log, bg="#1a1a1a", fg="#00ffcc", font=("Consolas", 9, "bold"), height=1, relief="flat").pack(fill="x", padx=8, pady=2)
        tk.Button(btn_f, text="VECTOR 2D / 3D", command=self.open_dual_vector_map, bg="#1a1a1a", fg="#ff0", font=("Consolas", 9, "bold"), relief="flat").pack(fill="x", padx=8, pady=2)
        tk.Button(btn_f, text="VECTOR IGNIÇÃO / 720°", command=self.open_ignition_vector, bg="#1a1a1a", fg="#ff8800", font=("Consolas", 8, "bold"), relief="flat").pack(fill="x", padx=8, pady=2)
        tk.Button(btn_f, text="MOTO PROFILE / EVENTOS", command=self.open_moto_profile, bg="#1a1a1a", fg="#66ff99", font=("Consolas", 8, "bold"), relief="flat").pack(fill="x", padx=8, pady=2)
        abf=tk.Frame(btn_f,bg="#0a0a0a");abf.pack(fill="x",padx=8,pady=1)
        tk.Button(abf,text="CAPT A",command=self.capture_ab_a,bg="#1a1a1a",fg="#66aaff",font=("Consolas",8,"bold"),relief="flat").pack(side="left",fill="x",expand=True,padx=(0,1))
        tk.Button(abf,text="CAPT B + COMPARA",command=self.capture_ab_b,bg="#1a1a1a",fg="#ff66aa",font=("Consolas",8,"bold"),relief="flat").pack(side="left",fill="x",expand=True,padx=(1,0))
        tk.Button(btn_f, text="RESET ZOOM", command=self.reset_zoom, bg="#1a1a1a", fg="#0ff", font=("Consolas", 8), relief="flat").pack(fill="x", padx=8, pady=2)

        self.right_panel = tk.Frame(self.paned, bg="#050505")
        self.paned.add(self.right_panel)

        self.canvas = tk.Canvas(self.right_panel, bg="#000", height=225, highlightthickness=1, highlightbackground="#222")
        self.canvas.pack(fill="x", padx=6, pady=(5,0))
        self.scrollbar = ttk.Scrollbar(self.right_panel, orient="horizontal", style="Quantum.Horizontal.TScrollbar", command=self.on_scroll)
        self.scrollbar.pack(fill="x", padx=6, pady=(0, 3))

        self.canvas.bind("<ButtonPress-1>", self.on_zoom_start)
        self.canvas.bind("<B1-Motion>", self.on_zoom_draw)
        self.canvas.bind("<ButtonRelease-1>", self.on_zoom_end)
        self.canvas.bind("<Button-3>", self.set_selection_point)
        self.canvas.bind("<Motion>", self.on_canvas_hover)

        self.data_tabs = ttk.Notebook(self.right_panel)
        self.data_tabs.pack(fill="both", expand=True, padx=6, pady=3)
        summary_page = tk.Frame(self.data_tabs, bg="#000")
        telemetry_page = tk.Frame(self.data_tabs, bg="#080808")
        self.data_tabs.add(summary_page, text="  CONTEXTO / DECISÃO  ")
        self.data_tabs.add(telemetry_page, text="  TELEMETRIA  ")
        self.matrix_box = tk.Text(summary_page, bg="#000", fg="#00ff41", font=("Consolas", 9), bd=0, relief="flat", padx=8, pady=6)
        self.matrix_box.pack(fill="both", expand=True)
        self.telemetry_advanced = tk.Text(telemetry_page, bg="#080808", fg="#0ff", font=("Consolas", 8), bd=0, relief="flat", padx=8, pady=6)
        self.telemetry_advanced.pack(fill="both", expand=True)

    def update_param(self, param, val): 
        try: 
            if param == 'delay_frames':
                self.mix_params[param] = int(float(val))
            else:
                self.mix_params[param] = float(val)
        except: pass

    def on_delay_ms(self, value):
        delay_ms = float(value)
        self.mix_params['delay_ms'] = delay_ms
        frames = max(0, int(round(delay_ms / max(self.sample_period_ms, 1.0))))
        self.mix_params['delay_frames'] = frames
        self.delay_caption.set(f"LAMBDA DELAY (ms) | {delay_ms:.0f} ms ≈ {frames}f")

    def sync_params(self):
        self.mix_params['has_lambda_sensor'] = self.has_lambda_var.get()
        self.mix_params['use_custom_target'] = self.target_toggle.get()
        self.mix_params['enable_target_search'] = self.search_toggle.get()
        self.mix_params['custom_target_val'] = self.target_val.get()
        self.mix_params['ignore_gammae'] = True 
        self.on_delay_ms(self.sld_delay.get())
        self.mix_params['learn_rate'] = float(self.sld_learn.get())
        self.mix_params['sample_period_ms'] = self.sample_period_ms

    def load_log(self):
        path = filedialog.askopenfilename(filetypes=[("Log Files", "*.csv *.msl *.txt")])
        if not path: return
        try:
            with open(path, 'r', errors='ignore') as f: lines = f.readlines()
            header_idx = -1
            for i, line in enumerate(lines):
                if "Time" in line and ("RPM" in line or "MAP" in line):
                    header_idx = i; break
            if header_idx == -1:
                messagebox.showerror("Engine Fault", "Datalog inválido.")
                return
            data_content = lines[header_idx:]
            skip_rows = [1] if header_idx + 1 < len(lines) and any(u in lines[header_idx+1].lower() for u in ['sec', 'rpm', 'kpa']) else []
            self.df = pd.read_csv(io.StringIO("".join(data_content)), sep=None, engine='python', skiprows=skip_rows)
            self.df.columns = [c.strip() for c in self.df.columns]
            self.df = QuantumEngineCore.canonicalize_log(self.df)
            valid_dt = self.df['Q_TIME'].diff()
            valid_dt = valid_dt[(valid_dt > 0.001) & (valid_dt < 1.0)]
            if not valid_dt.empty:
                self.sample_period_ms = float(valid_dt.median() * 1000.0)
            self.mix_params['sample_period_ms'] = self.sample_period_ms
            
            # Detecção e tratamento automático de presença de Lambda
            lambda_col = 'Q_LAMBDA'
            if lambda_col in self.df:
                self.df[lambda_col] = pd.to_numeric(self.df[lambda_col], errors='coerce').fillna(0)
                # Verifica se há dados válidos de Lambda (> 0.3)
                valid_count = (self.df[lambda_col] > 0.3).sum()
                if valid_count > 10:
                    self.has_lambda_var.set(True)
                else:
                    self.has_lambda_var.set(False)
            else:
                self.has_lambda_var.set(False)

            cols = ['RPM', 'MAP', 'TPS', 'CLT', 'IAT', 'Gammae', 'Gego', 'PW', 'Time']
            for t in cols:
                c = QuantumEngineCore.get_col(self.df.columns, [t])
                if c: self.df[c] = pd.to_numeric(self.df[c], errors='coerce')

            self.sync_params()
            self.reset_zoom()
            
            l_msg = "Com dados de Lambda." if self.has_lambda_var.get() else "SEM Lambda ativa (Modo Tolerante Ativado)."
            src = self.df.attrs.get('quantum_sources', {})
            pw_src = src.get('Q_PW_FINAL') or 'ausente'
            duty_src = src.get('Q_DUTY_LOGGED') or 'calculado por PW × RPM'
            available=sum(1 for v in src.values() if v)
            messagebox.showinfo("Quantum V90", f"Log carregado: {len(self.df)} quadros.\n{l_msg}\nAmostragem real: {self.sample_period_ms:.1f} ms\nParser: {available}/{len(src)} canais canônicos\nPW: {pw_src}\nDuty: {duty_src}")
        except Exception as e: messagebox.showerror("Engine Fault", f"Data Error: {e}")

    def reset_zoom(self):
        if self.df is None: return
        self.view_start = 0; self.view_range = len(self.df)
        self.sel_start = 0; self.sel_end = len(self.df)
        self.draw_waves()

    def on_scroll(self, *args):
        if self.df is None: return
        try:
            val = float(args[1])
            self.view_start = int(val * (len(self.df) - self.view_range))
            self.draw_waves()
        except: pass

    def set_selection_point(self, event):
        if self.df is None: return
        w = self.canvas.winfo_width()
        idx = self.view_start + int((event.x / w) * self.view_range)
        if not hasattr(self, 'sel_toggle'): self.sel_toggle = True
        if self.sel_toggle: 
            self.sel_start = idx; self.sel_toggle = False
        else: 
            self.sel_end = idx; self.sel_toggle = True
        self.draw_waves()

    def draw_waves(self):
        if self.df is None: return
        self.canvas.delete("all")
        w, h = self.canvas.winfo_width(), self.canvas.winfo_height()
        if w < 10: return

        s_rel = (self.sel_start - self.view_start) / self.view_range * w
        e_rel = (self.sel_end - self.view_start) / self.view_range * w
        self.canvas.create_rectangle(s_rel, 0, e_rel, h, fill="#001a1a", outline="#003333")
        
        slice_df = self.df.iloc[self.view_start:self.view_start+self.view_range]
        n = len(slice_df)
        if n < 2: return

        # Statistics and vertical scale belong to the analysis selection, not
        # to the temporary zoom viewport. Right-click selection is allowed in
        # either order, so always normalize and clamp its limits here.
        analysis_start, analysis_end = sorted((self.sel_start, self.sel_end))
        analysis_start = max(0, min(int(analysis_start), len(self.df)))
        analysis_end = max(0, min(int(analysis_end), len(self.df)))
        if analysis_end <= analysis_start:
            analysis_start, analysis_end = 0, len(self.df)
        analysis_df = self.df.iloc[analysis_start:analysis_end]
        
        self.scrollbar.set(self.view_start/len(self.df), (self.view_start+self.view_range)/len(self.df))
        configs = [('Q_RPM', 'RPM', '#0f0', 8000, 0.7), ('Q_MAP', 'MAP', '#0ff', 250, 0.6),
                   ('Q_TPS', 'TPS', '#ff0', 100, 0.5), ('Q_PW_FINAL', 'PW', '#fff', 4, 0.45),
                   ('Q_DUTY', 'DUTY', '#f44', 10, 0.35), ('Q_LAMBDA', 'Lambda', '#f0f', 1.5, 0.8)]
        
        for found, label, color, scale, h_fact in configs:
            if found in self.df.columns and (found != 'Q_LAMBDA' or self.has_lambda_var.get()):
                # PW/Duty scale and range are locked to the selected analysis
                # interval. Zooming only changes what is drawn, never these
                # statistics. Use the real extrema; do not hide peaks with p99.
                if label in ('PW', 'DUTY'):
                    selected_values = pd.to_numeric(analysis_df[found], errors='coerce')
                    selected_values = selected_values[np.isfinite(selected_values)]
                    if not selected_values.empty:
                        selected_min = float(selected_values.min())
                        selected_max = float(selected_values.max())
                        floor = 2.0 if label == 'PW' else 3.0
                        scale = max(floor, math.ceil(selected_max * 1.05 * 10.0) / 10.0)
                    else:
                        selected_min = selected_max = 0.0
                    self.canvas.create_text(8, 12 + (18 if label == 'DUTY' else 0),
                                            text=f"{label} {selected_min:.1f}–{selected_max:.1f}{'%' if label == 'DUTY' else 'ms'}",
                                            fill=color, anchor='w', font=('Consolas', 8, 'bold'))
                pts = []
                step = max(1, n // 1200)
                for i in range(0, n, step):
                    try:
                        val = float(slice_df[found].iloc[i])
                        if label == 'Lambda' and val > 5: val /= float(self.mix_params.get('stoich', QuantumEngineCore.STOICH_DEFAULT))
                        y_pos = h - (val/scale * h * h_fact) - 20
                        pts.extend([(i/n)*w, y_pos])
                    except: continue
                if len(pts) > 4: 
                    self.canvas.create_line(pts, fill=color, width=1 if label != 'Lambda' else 2)

    def on_zoom_start(self, event):
        self.zoom_x1 = event.x
        if self.zoom_rect: self.canvas.delete(self.zoom_rect)
        self.zoom_rect = self.canvas.create_rectangle(event.x, 0, event.x, 500, outline="#0ff", dash=(4,4))

    def on_zoom_draw(self, event): 
        if self.zoom_rect: self.canvas.coords(self.zoom_rect, self.zoom_x1, 0, event.x, 500)

    def on_zoom_end(self, event):
        if self.df is None: return
        x1, x2 = sorted([self.zoom_x1, event.x])
        w = self.canvas.winfo_width()
        if (x2 - x1) > 5 and w > 0:
            start_p = int((x1 / w) * self.view_range)
            end_p = int((x2 / w) * self.view_range)
            self.view_start += start_p
            self.view_range = max(10, end_p - start_p)
            self.draw_waves()
        if self.zoom_rect:
            self.canvas.delete(self.zoom_rect); self.zoom_rect = None

    def on_canvas_hover(self, event):
        if self.df is None: return
        w = self.canvas.winfo_width()
        if w <= 0: return
        idx = self.view_start + int((event.x / w) * self.view_range)
        if 0 <= idx < len(self.df):
            hist = []
            lookback = int(self.mix_params['delay_frames']) + 5
            for i in range(max(0, idx - lookback), idx + 1):
                hist.append(self.df.iloc[i].to_dict())
            ans = QuantumEngineCore.analyze_frame(hist, self.mix_params)
            if ans: self.update_ui(ans, event.x)

    def update_ui(self, ans, x):
        if self.cursor_line: self.canvas.delete(self.cursor_line)
        self.cursor_line = self.canvas.create_line(x, 0, x, 500, fill="#fff", dash=(2,2))
        
        for n, val in [("RPM", ans['rpm']), ("MAP", ans['map']), ("TPS", ans['tps']), 
                        ("PW", ans['pw']), ("ADV", ans['adv'])]:
            self.monitors[n].config(text=f"{val:.1f}" if n != "RPM" else f"{val:.0f}")
            
        l_text = f"{ans['lambda']:.3f}" if ans.get('lambda_valid', True) else "OFF"
        self.monitors["L_ACT"].config(text=l_text)
        self.monitors["L_TGT"].config(text=f"{ans['target_used']:.3f}")
        self.monitors["DUTY"].config(text=f"{ans['duty_cycle']:.1f}%")

        self.telemetry_advanced.delete("1.0", tk.END)
        def fmt(l1, v1, l2, v2):
            return f" {l1:<14} {v1:<10} | {l2:<12} {v2}\n"

        timing_windows_text = " | ".join(
            "{channel} {start:.1f}→{end:.1f}°".format(**window)
            for window in ans['timing']['windows']
        )

        tel_data = (
            f" [ ADVANCED TELEMETRY X21 - VECTOR & MASS DYNAMICS ]\n"
            + fmt("01.STATE", ans['phase'], "02.VIOLENCE", ans['violence'])
            + fmt("03.PWR IDX", f"{ans['surge_index']:.1f}", "04.TPS DOT", f"{ans['tps_dot']:.1f}")
            + fmt("05.MAP DOT", f"{ans['map_dot']:.1f}", "06.RPM DOT", f"{ans['rpm_dot']:.0f}")
            + " " + "-"*58 + "\n"
            + fmt("07.AE MULT", f"{ans['ae_mult']:.2f}x", "08.AE ADD", f"{ans['ae_add']:.3f}ms")
            + fmt("09.DT / DELAY", f"{ans['frame_dt_ms']:.1f}/{self.mix_params['delay_ms']:.0f}ms", "10.AUTH/EVID", f"{ans['authority']:.0f}/{ans['evidence_score']:.0f}%")
            + fmt("11.CORR GAM", f"{ans['gamma_val']:.1f}%", "12.CORR GEGO", f"{ans['gego']:.1f}%")
            + " " + "-"*58 + "\n"
            + fmt("13.CLT/IAT", f"{ans['clt']:.0f}/{ans['iat']:.0f}C", "14.VBAT", f"{ans['vbat']:.2f}V")
            + fmt("15.SPARK", ans['spark_status'], "16.PW FINAL", f"{ans['pw']:.3f}ms")
            + fmt("17.DUTY LOG", f"{ans['duty_logged']:.2f}%", "18.DUTY CALC", f"{ans['duty_derived']:.2f}%")
            + " " + "-"*58 + "\n"
            + fmt("19.PW C1/C2", f"{ans['pw_channels'][0]:.3f}/{ans['pw_channels'][1]:.3f}", "20.PW C4/C3", f"{ans['pw_channels'][2]:.3f}/{ans['pw_channels'][3]:.3f}")
            + fmt("21.PW AR/EF", f"{ans['pw_model_air']:.3f}/{ans['pw_effective']:.3f}", "22.VE2 VETOR", f"{ans['ve2_vector']:.1f}%")
            + fmt("23.TIMING", ans['timing']['source'], "24.END LOCAL", f"{ans['inj_end']:.1f}°")
            + fmt("25.FUEL CELL", "ESTÁVEL" if ans['steady_fuel_cell'] else "DINÂMICA", "26.INJ SPAN C1", f"{ans['timing']['windows'][0]['span']:.1f}°")
            + fmt("27.PS10", (f"{ans['fuel_pressure_bar']:.2f}/{ans['fuel_expected_bar']:.2f}bar" if ans['ps10_valid'] else "N/D"), "28.THERMAL", ans['thermal_class'])
            + fmt("29.CAUSAL", f"{ans['causal_rpm']:.0f}rpm/{ans['causal_map']:.0f}kPa", "30.MASS PROXY", f"{ans['mass_proxy']:.3f}")
        )
        self.telemetry_advanced.insert(tk.END, tel_data)

        self.matrix_box.delete("1.0", tk.END)
        l_info = f"Lambda Real: {ans['lambda']:.3f}" if ans.get('lambda_valid', True) else "SENSOR LAMBDA DESATIVADO/AUSENTE NO LOG"
        status_msg = (
            f"--- [ QUANTUM CONVERGENCE: {ans['time']}s ] ---\n\n"
            f" STATUS DO SENSOR: {l_info}\n"
            f" Timing [{ans['timing']['source']}]: fim local {ans['inj_end']:.1f}° | {ans['timing']['deg_per_ms']:.2f}°/ms\n"
            f" Janelas C1/C2/C4/C3: {timing_windows_text}\n"
            f" PW C1/C2/C4/C3: {' / '.join(f'{v:.3f}' for v in ans['pw_channels'])} ms\n"
            f" Duty: log {ans['duty_logged']:.2f}% | calculado {ans['duty_derived']:.2f}%\n\n"
            f" EVENTO: {ans['event_class']} | EVIDÊNCIA {ans['evidence_score']:.0f}% | AUTORIDADE {ans['authority']:.0f}%\n"
            f" CÉLULA CAUSAL: {ans['causal_rpm']:.0f} rpm / TPS {ans['causal_tps']:.1f}% / MAP {ans['causal_map']:.1f} kPa @ {ans['causal_time']:.3f}s\n"
            f" CALIBRAÇÃO VE (Sugerida igual Atual sem Lambda):\n"
            f" > VE1: {ans['ve1_curr']:.1f}  -> {ans['sug_ve1']:.1f}\n"
            f" > VE2: {ans['ve2_curr']:.1f}  -> {ans['sug_ve2']:.1f}\n\n"
            f" AE LOGIC: MULT({ans['ae_mult']:.2f}) ADD({ans['ae_add']:.2f}ms)\n"
            f" FLAGS: [GHOST:{'ON' if self.mix_params['use_custom_target'] else 'OFF'}] "
            f" [DELAY:{int(self.mix_params['delay_frames'])}f]"
        )
        self.matrix_box.insert(tk.END, status_msg)

    def open_dual_vector_map(self):
        if self.df is None: return
        DualVectorMapWindow(self.root, self.df, self.sel_start, self.sel_end, self.mix_params)

    def selected_bounds(self):
        if self.df is None:return (0,0)
        a,b=sorted((self.sel_start,self.sel_end))
        return (0,len(self.df)) if b<=a else (max(0,a),min(len(self.df),b))

    def open_ignition_vector(self):
        if self.df is None:return
        a,b=self.selected_bounds();IgnitionVectorWindow(self.root,self.df,a,b,self.mix_params)

    def capture_ab_a(self):
        if self.df is None:return
        self.ab_segment_a=self.selected_bounds()
        messagebox.showinfo('A/B',f"Trecho A capturado: frames {self.ab_segment_a[0]}–{self.ab_segment_a[1]}.\nMarque outro trecho com botão direito e capture B.")

    def capture_ab_b(self):
        if self.df is None or self.ab_segment_a is None:
            messagebox.showwarning('A/B','Capture primeiro o trecho A.');return
        seg_b=self.selected_bounds();text=self.build_ab_report(self.ab_segment_a,seg_b)
        AnalysisTextWindow(self.root,'COMPARAÇÃO A/B CAUSAL',text)

    def build_ab_report(self, seg_a, seg_b):
        fa=QuantumEngineCore.analyze_dataframe(self.df,*seg_a,self.mix_params)
        fb=QuantumEngineCore.analyze_dataframe(self.df,*seg_b,self.mix_params)
        if not fa or not fb:return 'Sem frames analisáveis em um dos trechos.'
        a=pd.DataFrame(fa);b=pd.DataFrame(fb)
        for d in (a,b):
            d['cell_r']=(d.causal_rpm/250).round()*250;d['cell_m']=(d.causal_map/5).round()*5;d['cell_t']=(d.causal_tps/2).round()*2
        keys=['cell_r','cell_m','cell_t','event_class']
        cols=['adv','advance1','pw_effective','mass_proxy','lambda','map_dot','rpm_dot','authority','evidence_score','fuel_error_bar']
        ga=a.groupby(keys)[cols].median();gb=b.groupby(keys)[cols].median();joined=ga.join(gb,lsuffix='_A',rsuffix='_B',how='inner')
        if joined.empty:return 'A e B não possuem células causais compatíveis. Faça tocadas mais semelhantes.'
        lines=["BOOSTBANDITOS • COMPARAÇÃO A/B POR CÉLULAS CAUSAIS", "",
               f"A: frames {seg_a[0]}–{seg_a[1]} ({len(a)} analisados)",f"B: frames {seg_b[0]}–{seg_b[1]} ({len(b)} analisados)",
               f"Células compatíveis: {len(joined)}", ""]
        for col,label,unit in [('adv','Avanço final','°'),('pw_effective','PW efetivo','ms'),('mass_proxy','Massa relativa',''),('lambda','Lambda',''),('rpm_dot','RPMdot','rpm/s'),('fuel_error_bar','Erro PS10','bar')]:
            delta=(joined[f'{col}_B']-joined[f'{col}_A']).median()
            lines.append(f"{label:<18} B−A: {delta:+.3f} {unit}")
        compat=float(np.minimum(joined.authority_A,joined.authority_B).median())
        evid=float(np.minimum(joined.evidence_score_A,joined.evidence_score_B).median())
        lines += ["",f"Compatibilidade/autoridade mediana: {compat:.0f}%",f"Evidência comum mediana: {evid:.0f}%","",
                  "INTERPRETAÇÃO:","O relatório mede associação em condições compatíveis; não declara ganho térmico absoluto.",
                  "Para validar avanço, repita A/B alternado e exija mesma lambda, temperatura, PS10 e carga."]
        return '\n'.join(lines)

    def open_moto_profile(self):
        if self.df is None:return
        a,b=self.selected_bounds();frames=QuantumEngineCore.analyze_dataframe(self.df,a,b,self.mix_params)
        if not frames:return
        d=pd.DataFrame(frames);counts=d.event_class.value_counts();events=[];last=None;start=0
        for i,row in d.iterrows():
            label=QuantumEngineCore.event_label(row)
            if label!=last:
                if last is not None: events.append((last,start,i-1))
                last=label;start=i
        events.append((last,start,len(d)-1))
        lines=["BOOSTBANDITOS • MOTO PROFILE / EVENTOS",f"Frames analisados: {len(d)} | dt mediano: {d.frame_dt_ms.median():.1f} ms","",
               "CLASSIFICAÇÃO:"]+[f"  {k:<12} {v:>6} frames ({100*v/len(d):5.1f}%)" for k,v in counts.items()]
        lines += ["",f"Evidência mediana: {d.evidence_score.median():.1f}%",f"Autoridade mediana: {d.authority.median():.1f}%",
                  f"PS10 válido: {100*d.ps10_valid.mean():.1f}% | estável: {100*d.ps10_stable.mean():.1f}%",
                  f"Faixa: {d.rpm.min():.0f}–{d.rpm.max():.0f} rpm | MAP {d['map'].min():.1f}–{d['map'].max():.1f} kPa | TPS {d.tps.min():.1f}–{d.tps.max():.1f}%","","EVENTOS CRONOLÓGICOS:"]
        for label,i0,i1 in events[:80]:
            seg=d.iloc[i0:i1+1];dur=seg.time.iloc[-1]-seg.time.iloc[0]
            if dur>=0.10 or label not in ('ESTAVEL','INVALIDO'):
                lines.append(f"  {seg.time.iloc[0]:8.3f}s  {label:<20} {dur:6.2f}s  pico MAP {seg['map'].max():6.1f}  auth {seg.authority.median():4.0f}%")
        lines += ["","MOTO PROFILE não grava mapas automaticamente: registra evidência, autoridade e repetibilidade para convergência futura."]
        AnalysisTextWindow(self.root,'MOTO PROFILE • EVENTOS', '\n'.join(lines))

if __name__ == "__main__":
    root = tk.Tk()
    try:
        from ctypes import windll
        windll.shcore.SetProcessDpiAwareness(1)
    except: pass
    app = VIC_Quantum_V90(root)
    root.mainloop()
