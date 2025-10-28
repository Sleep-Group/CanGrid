# app/grid_core.py
from __future__ import annotations
import pandas as pd
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from specific_breakdowns import (
    hydro_breakdown, coal_breakdown, natgas_breakdown, oil_breakdown,
    solar_breakdown, wind_breakdown
)
from AESO_Data_Extract import DDprojections
from IESO_Data_Extract import IESO_natgas_breakdown

SECTORS = ['Canada','AB','BC','MB','NB','NL','NT','NS','NU','ON','PE','QC','SK','YT']
NEW_INDEX = ['Hydro / Wave / Tidal','Wind','Biomass / Geothermal','Solar','Uranium','Coal & Coke','Natural Gas','Oil']

def load_total_grid(xlsx_path: Path) -> list[pd.DataFrame]:
    Total_Grid = pd.read_excel(xlsx_path)
    for col in Total_Grid.columns:
        Total_Grid[col] = Total_Grid[col].fillna(0)

    slices = {
        "Canada": (7, 15), "AB": (95, 103), "BC": (106, 114), "MB": (84, 92),
        "NB": (51, 59), "NL": (18, 26), "NT": (139, 147), "NS": (40, 48),
        "NU": (150, 158), "ON": (73, 81), "PE": (29, 37), "QC": (62, 70),
        "SK": (117, 125), "YT": (128, 136),
    }
    years = [str(y) for y in range(2005, 2051)]
    grid_list = []
    for s in SECTORS:
        a, b = slices[s]
        df = Total_Grid.iloc[a:b].reset_index(drop=True).copy()
        df.columns = [s] + years
        grid_list.append(df)
    return grid_list

def build_breakdown() -> dict:
    bd = {}
    for s in SECTORS:
        bd[s] = {
            "hydro": {"res%": hydro_breakdown['res%'][s], "riv%": hydro_breakdown['riv%'][s]},
            "coal":  {"bit%": coal_breakdown['bit%'][s],  "sub%": coal_breakdown['sub%'][s], "lig%": coal_breakdown['lig%'][s]},
            "natgas":{"CC%": natgas_breakdown['CC%'][s],  "CO%":  natgas_breakdown['CO%'][s], "SC%":  natgas_breakdown['SC%'][s]},
            "oil":   {"heavy%": oil_breakdown['Heavy_Oil%'][s], "diesel%": oil_breakdown['Diesel%'][s]},
        }
    return bd

def _to_kg_factor(unit_in: str) -> float:
    """
    Convert *input* mass unit to kg.
    unit_in: 'kg' or 'g' (case-insensitive)
    Returns multiplier to get kg from the provided unit.
    """
    u = (unit_in or "kg").strip().lower()
    return 1.0 if u.startswith("kg") else 1.0*1000.0  # grams -> kg

def compute_structures(
    xlsx_path: Path,
    gwp: dict[str, float],
    emission_input_unit: str = "kg",   # <-- NEW: 'kg' or 'g' for model *inputs*
):
    """
    gwp: dict with keys 'CO2','CH4','N2O','SF6' (100-yr values)
    emission_input_unit: whether the hard-coded factors below are kg or g per kWh.
                         Internally we convert to kg for all computations.
    """
    # GWP100 factors
    CO2_GWP100 = float(gwp['CO2'])
    CH4_GWP100 = float(gwp['CH4'])
    N2O_GWP100 = float(gwp['N2O'])
    SF6_GWP100 = float(gwp['SF6'])

    # Convert input factors to kg if they're provided in grams
    mass_to_kg = _to_kg_factor(emission_input_unit)

    Transmission_Efficiency = 1.0
    years = [str(y) for y in range(2005, 2051)]
    grid = load_total_grid(xlsx_path)
    breakdown = build_breakdown()

    # Operating factors per gas (baseline values are in kg per kWh; if you provide them in g, set emission_input_unit='g')
    proc = {
        'coal_bit': {'CO2':1.08,'CH4':0.00134,'N2O':2.57e-6,'SF6':1.192e-9},
        'coal_lig': {'CO2':0.956,'CH4':0.00079,'N2O':2.57e-6,'SF6':4.02e-10},
        'coal_sub': {'CO2':1.007,'CH4':0.00078,'N2O':1.86e-6,'SF6':1.74e-10},
        'diesel':   {'CO2':0.993,'CH4':0.00096,'N2O':5.11e-5,'SF6':6.2e-9},
        'heavy':    {'CO2':1.135,'CH4':0.00074,'N2O':4.76e-5,'SF6':2.52e-9},
        'hydro_res':{'CO2':1.3e-4,'CH4':1.20e-7,'N2O':4.56e-9,'SF6':4e-12},
        'hydro_riv':{'CO2':1.3e-4,'CH4':1.20e-7,'N2O':4.56e-9,'SF6':4e-12},
        'natgas_cogen':  {'CO2':0.29436,'CH4':0.00076,'N2O':5.11e-6,'SF6':1.53e-10},
        'natgas_comb':   {'CO2':0.349,'CH4':0.0009,'N2O':6.06e-6,'SF6':1.8e-10},
        'natgas_convert':{'CO2':0.349,'CH4':0.00090,'N2O':6.06e-6,'SF6':1.8e-10},
        'natgas_simple': {'CO2':0.544,'CH4':0.00141,'N2O':9.47e-6,'SF6':2.16e-10},
        'nuclear':  {'CO2':0.00578,'CH4':1.06e-5,'N2O':4.17e-7,'SF6':2.23e-10},
        'solar_conc': {'CO2':0.00085,'CH4':1.126e-6,'N2O':5.28e-8,'SF6':3.61e-10},
        'solar_pv':  {'CO2':3.65e-6,'CH4':9.69e-9,'N2O':1.47e-10,'SF6':6.88e-13},
        'wind':      {'CO2':5.35e-5,'CH4':1.94e-7,'N2O':1.74e-9,'SF6':4.53e-12},
        'wood_cogen':{'CO2':0.03316,'CH4':5.93e-5,'N2O':4.03e-5,'SF6':4.82e-10},
        'wood_simple':{'CO2':0.06174,'CH4':0.00012,'N2O':8.62e-5,'SF6':8.77e-10},
    }

    # Scale per-gas masses to kg if user says inputs are grams
    proc_scaled = {
        k: {g: v[g] * mass_to_kg for g in v}
        for k, v in proc.items()
    }

    # Convert to CO2e (kg/kWh)
    procCO2eq = {
        k: (v['CO2']*CO2_GWP100 + v['CH4']*CH4_GWP100 + v['N2O']*N2O_GWP100 + v['SF6']*SF6_GWP100) / Transmission_Efficiency
        for k, v in proc_scaled.items()
    }

    Grid_ByYear: dict[str, list[pd.DataFrame]] = {}
    for i, s in enumerate(SECTORS):
        Grid_ByYear[s] = []
        solar_cf = solar_breakdown['cf'][s]
        wind_cf  = wind_breakdown['cf to 5%'][s]
        cf_holder_solar, cf_holder_wind = 0.15, 0.5  # carried over

        for j, y in enumerate(years):
            block = grid[i].iloc[0:8, j+1].copy().to_frame()
            block.index = NEW_INDEX
            block.iloc[:, 0] = block.iloc[:, 0] * 1e6  # GWh -> kWh

            # NG split overrides
            natgas_CC = breakdown[s]['natgas']['CC%']
            natgas_CO = breakdown[s]['natgas']['CO%']
            natgas_SC = breakdown[s]['natgas']['SC%']
            if s == 'AB':
                natgas_CC = DDprojections['ratio CC'][2022]
                natgas_CO = DDprojections['ratio Cogen'][2022]
                natgas_SC = DDprojections['ratio SC'][2022]
            if s == 'ON':
                natgas_CC = IESO_natgas_breakdown['CC']
                natgas_SC = IESO_natgas_breakdown['SC']
                natgas_CO = IESO_natgas_breakdown['CO']

            # Operating CO2e (kg/kWh)
            op = pd.Series({
                'Hydro / Wave / Tidal': procCO2eq['hydro_res']*breakdown[s]['hydro']['res%'] + procCO2eq['hydro_riv']*breakdown[s]['hydro']['riv%'],
                'Wind':                 procCO2eq['wind'],
                'Biomass / Geothermal': procCO2eq['wood_cogen']*0.5 + procCO2eq['wood_simple']*0.5,
                'Solar':                procCO2eq['solar_pv'],
                'Uranium':              procCO2eq['nuclear'],
                'Coal & Coke':          procCO2eq['coal_bit']*breakdown[s]['coal']['bit%'] + procCO2eq['coal_sub']*breakdown[s]['coal']['sub%'] + procCO2eq['coal_lig']*breakdown[s]['coal']['lig%'],
                'Natural Gas':          procCO2eq['natgas_comb']*natgas_CC + procCO2eq['natgas_cogen']*natgas_CO + procCO2eq['natgas_simple']*natgas_SC,
                'Oil':                  procCO2eq['diesel']*breakdown[s]['oil']['diesel%'] + procCO2eq['heavy']*breakdown[s]['oil']['heavy%'],
            }, name='Operating kgCO2/kWh')

            # Embodied (baseline expressions are kg CO2e/kWh; if you provide them in g, set emission_input_unit='g')
            emb = pd.Series({
                'Hydro / Wave / Tidal': (0.018*breakdown[s]['hydro']['res%'] + 0.008*breakdown[s]['hydro']['riv%']) * mass_to_kg,
                'Wind':                 (0.0001070049744 * (cf_holder_wind / wind_cf)) * mass_to_kg,
                'Biomass / Geothermal': (0.032 + 0.0613) * mass_to_kg,
                'Solar':                (0.00112363578 * (cf_holder_solar / solar_cf)) * mass_to_kg,
                'Uranium':              (0.2653938859/(650*30*365*24*0.89*1000)) * mass_to_kg,
                'Coal & Coke':          (35437946.91/(100*150000*1000)) * mass_to_kg,
                'Natural Gas':          (5496684.453/(100*180000*1000)) * mass_to_kg,
                'Oil':                  (500821.3393/(10*100000*1000)) * mass_to_kg,
            }, name='Embodied kgCO2/kWh')

            out = block.copy()
            out[y] = block.iloc[:, 0]
            out['Operating kgCO2/kWh'] = op
            out['Embodied kgCO2/kWh'] = emb
            out['Total kgCO2/kWh'] = out['Operating kgCO2/kWh'] + out['Embodied kgCO2/kWh']

            total_elec = out[y].sum()
            out['% of electricity'] = out[y] / total_elec if total_elec else 0.0
            Grid_ByYear[s].append(out)

    # Grid intensity (kg CO2e/kWh)
    Grid_Intensity: dict[str, pd.Series] = {}
    for s in SECTORS:
        gi = {}
        for y in years:
            j = int(y) - 2005
            df = Grid_ByYear[s][j]
            gi[y] = (df['% of electricity'] * df['Total kgCO2/kWh']).sum()
        Grid_Intensity[s] = pd.Series(gi, name='kgCO2/kWh')

    # Year totals & shares (CO2e)
    TotalCarbon: dict[str, dict[str, pd.DataFrame]] = {}
    for s in SECTORS:
        TotalCarbon[s] = {}
        for y in years:
            j = int(y) - 2005
            df = Grid_ByYear[s][j].copy()
            df['Total kgCO2'] = df['Total kgCO2/kWh'] * df[y]
            tot = df['Total kgCO2'].sum()
            df['% of CO2'] = df['Total kgCO2'] / tot if tot else 0.0
            df['Grid_Intensity_Contribution'] = df['% of CO2'] * Grid_Intensity[s][y]
            TotalCarbon[s][y] = df

    return {
        "sectors": SECTORS,
        "years": [str(y) for y in range(2005, 2051)],
        "grid_by_year": Grid_ByYear,
        "grid_intensity": Grid_Intensity,
        "total_carbon": TotalCarbon,
    }
