#!/usr/bin/env python3
"""Calculadora Req Fuel e sanidade de injetores para Bandit 1200 Turbo."""

import math
import tkinter as tk
from tkinter import ttk

R_AIR = 287.05  # J/(kg.K)

# Gasolina BR atual possui ~30% a 35% de Etanol (Stoich ~12.2, Densidade ~0.760)
# Etanol de Posto E100/E95 (Stoich ~9.0, Densidade ~0.789)
PRESETS_RABO_DE_GALO = {
    "Etanol Puro (E100)": (9.0, 0.789),
    "1L Gasolina + 19L Etanol (Tanque 20L)": (9.16, 0.788),
    "2L Gasolina + 18L Etanol (Tanque 20L)": (9.32, 0.786),
    "3L Gasolina + 17L Etanol (Tanque 20L)": (9.48, 0.785),
    "E85 (85% Etanol / 15% Gasolina)": (9.80, 0.780),
}


class Calculator(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("Bandit 1200 Turbo - Req Fuel & CALC INJETORES")
        self.resizable(False, False)
        self.configure(padx=12, pady=10)
        self.vars = {}
        self.build()
        self.recalculate()

    def add_entry(self, parent, row, col, label, key, value, unit=""):
        ttk.Label(parent, text=label).grid(row=row, column=col*3, sticky="w", pady=2, padx=(5, 2))
        var = tk.StringVar(value=value)
        var.trace_add("write", lambda *args: self.recalculate())
        self.vars[key] = var
        entry = ttk.Entry(parent, textvariable=var, width=8)
        entry.grid(row=row, column=col*3+1, sticky="e", pady=2)
        ttk.Label(parent, text=unit).grid(row=row, column=col*3+2, sticky="w", padx=(2, 8))

    def build(self):
        # Frame Fixo
        fixed = ttk.LabelFrame(self, text="Perfil do Motor")
        fixed.grid(row=0, column=0, sticky="ew")
        ttk.Label(
            fixed,
            text="Bandit 1200 | 1157 cc | 4 Cilindros | Sequencial | Dosador 1:1",
            font=("Helvetica", 9, "bold")
        ).grid(row=0, column=0, padx=8, pady=4)

        # Frame Combustível / Rabo de Galo
        fuel_frame = ttk.LabelFrame(self, text="Combustível & Rabo de Galo")
        fuel_frame.grid(row=1, column=0, sticky="ew", pady=(6, 0))

        ttk.Label(fuel_frame, text="Modo:").grid(row=0, column=0, sticky="w", padx=5)
        self.fuel_mode = tk.StringVar(value="Preset Rabo de Galo")
        mode_cb = ttk.Combobox(
            fuel_frame, 
            textvariable=self.fuel_mode, 
            values=["Preset Rabo de Galo", "Mistura Manual (Litros)"], 
            state="readonly", 
            width=20
        )
        mode_cb.grid(row=0, column=1, padx=5, pady=4)
        mode_cb.bind("<<ComboboxSelected>>", self.toggle_fuel_mode)

        # Combos e entradas de combustível
        self.preset_var = tk.StringVar(value="Etanol Puro (E100)")
        self.preset_cb = ttk.Combobox(
            fuel_frame, 
            textvariable=self.preset_var, 
            values=list(PRESETS_RABO_DE_GALO.keys()), 
            state="readonly", 
            width=32
        )
        self.preset_cb.grid(row=0, column=2, padx=5, pady=4)
        self.preset_cb.bind("<<ComboboxSelected>>", lambda e: self.recalculate())

        # Inputs de mistura no tanque manual
        self.mix_frame = ttk.Frame(fuel_frame)
        self.add_entry(self.mix_frame, 0, 0, " Gasolina BR:", "v_gas", "1.0", "L")
        self.add_entry(self.mix_frame, 0, 1, " Etanol:", "v_eth", "19.0", "L")

        # Inputs do Sistema
        inputs = ttk.LabelFrame(self, text="Parâmetros Operacionais")
        inputs.grid(row=2, column=0, sticky="ew", pady=(6, 0))

        # Coluna 1: Injeção & Pressão
        self.add_entry(inputs, 0, 0, "Vazão Ref. Bico:", "flow", "875", "cc/m")
        self.add_entry(inputs, 1, 0, "Pressão Ref. Bico:", "ref_bar", "3.0", "bar")
        self.add_entry(inputs, 2, 0, "Pressão Real Rail:", "rail_bar", "2.0", "bar")
        self.add_entry(inputs, 3, 0, "Dead Time (14V):", "dead_ms", "0.80", "ms")
        self.add_entry(inputs, 4, 0, "RPM Máxima:", "max_rpm", "10500", "RPM")

        # Coluna 2: Elétrica & Atmosfera
        self.add_entry(inputs, 0, 1, "Tensão Ref.:", "ref_v", "14.3", "V")
        self.add_entry(inputs, 1, 1, "Tensão Atual:", "vbat", "14.3", "V")
        self.add_entry(inputs, 2, 1, "VE Ref. (Base):", "ve", "100", "%")
        self.add_entry(inputs, 3, 1, "Temp. Ar (IAT):", "iat", "20", "°C")
        self.add_entry(inputs, 4, 1, "MAP Ref. (Local):", "map_kpa", "103", "kPa")

        # Resultados
        res_frame = ttk.LabelFrame(self, text="Resultados em Tempo Real")
        res_frame.grid(row=3, column=0, sticky="ew", pady=(6, 0))

        self.result_label = ttk.Label(res_frame, text="", justify="left", font=("Monospace", 9))
        self.result_label.pack(padx=8, pady=6, anchor="w")

    def toggle_fuel_mode(self, event=None):
        if self.fuel_mode.get() == "Preset Rabo de Galo":
            self.mix_frame.grid_forget()
            self.preset_cb.grid(row=0, column=2, padx=5, pady=4)
        else:
            self.preset_cb.grid_forget()
            self.mix_frame.grid(row=0, column=2, padx=5, pady=4)
        self.recalculate()

    def get_fuel_params(self):
        if self.fuel_mode.get() == "Preset Rabo de Galo":
            stoich, density = PRESETS_RABO_DE_GALO[self.preset_var.get()]
        else:
            v_gas = float(self.vars["v_gas"].get().replace(",", "."))
            v_eth = float(self.vars["v_eth"].get().replace(",", "."))
            v_total = v_gas + v_eth
            if v_total <= 0:
                raise ValueError("Volume do tanque deve ser > 0")
            
            frac_gas = v_gas / v_total
            frac_eth = v_eth / v_total
            
            # Gasolina BR (~12.2 Stoich, 0.760 g/ml) / Etanol (~9.0 Stoich, 0.789 g/ml)
            stoich = (frac_gas * 12.2) + (frac_eth * 9.0)
            density = (frac_gas * 0.760) + (frac_eth * 0.789)
            
        return stoich, density

    def recalculate(self):
        try:
            get_val = lambda k: float(self.vars[k].get().replace(",", "."))
            stoich, fuel_density = self.get_fuel_params()

            flow = get_val("flow")
            ref_bar = get_val("ref_bar")
            rail_bar = get_val("rail_bar")
            dead_ms = get_val("dead_ms")
            ref_v = get_val("ref_v")
            vbat = get_val("vbat")
            ve = get_val("ve") / 100.0
            iat_k = get_val("iat") + 273.15
            map_kpa = get_val("map_kpa")
            max_rpm = get_val("max_rpm")

            if min(flow, ref_bar, rail_bar, ve, map_kpa, max_rpm) <= 0:
                return

            # Vazão corrigida do bico pela pressão no rail
            flow_actual = flow * math.sqrt(rail_bar / ref_bar)

            # Densidade do ar via gás ideal e massa por cilindro
            air_density = (map_kpa * 1000.0) / (R_AIR * iat_k)
            cyl_vol_m3 = (1157.0 / 4.0) / 1_000_000.0

            air_mass_g = air_density * cyl_vol_m3 * ve * 1000.0
            fuel_mass_g = air_mass_g / stoich
            injector_g_s = (flow_actual / 60.0) * fuel_density

            effective_ms = (fuel_mass_g / injector_g_s) * 1000.0
            dead_correction = dead_ms + max(0.0, (ref_v - vbat) * 0.03)
            total_ms = effective_ms + dead_correction

            # Janela de tempo de 1 ciclo 4T (ms) e Duty Cycle na RPM máxima
            cycle_time_ms = (120 / max_rpm) * 1000.0
            duty_cycle = (total_ms / cycle_time_ms) * 100.0

            output = (
                f"Stoich Resultante:           {stoich:.2f} :1 | Densidade: {fuel_density:.3f} g/ml\n"
                f"Vazão Real do Bico ({rail_bar:.1f} bar):   {flow_actual:.1f} cc/min\n"
                f"─────────────────────────────────────────────────────────\n"
                f"Req Fuel Estimado (Base):    {total_ms:.2f} ms\n"
                f"  ├─ PW Efetivo:              {effective_ms:.2f} ms\n"
                f"  └─ Dead Time Corrigido:     {dead_correction:.2f} ms\n"
                f"Duty Cycle Máximo ({int(max_rpm)} RPM): {duty_cycle:.1f}%"
            )
            self.result_label.config(text=output)

        except (ValueError, ZeroDivisionError):
            self.result_label.config(text="Aguardando entradas válidas...")


if __name__ == "__main__":
    Calculator().mainloop()
