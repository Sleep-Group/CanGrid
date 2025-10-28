# app/streamlit_app.py
import streamlit as st
import plotly.express as px
import pandas as pd
from io import StringIO
from pathlib import Path
from typing import List
import warnings
import re
import traceback

from grid_core import compute_structures, NEW_INDEX, SECTORS

# --- UPDATED: New page title for browser tab ---
st.set_page_config(page_title="CanGrid Dashboard", page_icon='cangrid.png', layout="wide")

# --- Centralized Plotly config ---
PLOTLY_CONFIG = {
    "displaylogo": False,
    "responsive": True,
    "scrollZoom": True,
    "toImageButtonOptions": {"format": "png", "height": 600, "width": 1000, "scale": 2},
}

# --- Silence Streamlit's deprecation warning & guard direct plotly_chart kwargs ---
_depr_msg_re = re.compile(r"The keyword arguments have been deprecated.*Use config instead", re.I)
warnings.filterwarnings("ignore", message=_depr_msg_re.pattern)

_orig_plotly_chart = st.plotly_chart
QUIET_GUARD = True

def _guarded_plotly_chart(*args, **kwargs):
    banned = {
        "displaylogo", "displayModeBar", "modeBarButtonsToRemove", "scrollZoom",
        "toImageButtonOptions", "doubleClick", "staticPlot", "responsive", "editable"
    }
    offenders = banned.intersection(kwargs.keys())
    if offenders:
        raise RuntimeError(
            "Deprecated Plotly kwargs passed to st.plotly_chart: "
            f"{sorted(offenders)}. Use show(fig) and PLOTLY_CONFIG instead."
        )
    if not QUIET_GUARD and kwargs:
        tb = "".join(traceback.format_stack(limit=4))
        warnings.warn(f"Direct st.plotly_chart call detected; please route via show(fig).\n{tb}")
    return _orig_plotly_chart(*args, **kwargs)

st.plotly_chart = _guarded_plotly_chart

def show(fig):
    # modern width API (replacement for deprecated use_container_width)
    _orig_plotly_chart(fig, config=PLOTLY_CONFIG)

# ---------- Scenario file mapping ----------
SCENARIO_TO_FILE = {
    "2021 Current":              "Electricity_Generation_2021_Current.xlsx",
    "2021 Evolving":             "Electricity_Generation_2021_Evolving.xlsx",
    "2023 Canada Net Zero":      "Electricity_Generation_2023_Canada_Net_Zero.xlsx",
    "2023 Current":              "Electricity_Generation_2023_Current.xlsx",
    "2023 Global Net Zero":      "Electricity_Generation_2023_Global_Net_Zero.xlsx",
}
SCENARIOS = list(SCENARIO_TO_FILE.keys())
DATA_DIR = Path(__file__).resolve().parents[1] / "data"

# ---------- GWP presets (100-year) ----------
GWP_AR5 = {"CO2": 1.0, "CH4": 28.0,  "N2O": 265.0, "SF6": 23500.0}
GWP_AR6 = {"CO2": 1.0, "CH4": 27.2,  "N2O": 273.0, "SF6": 25200.0}

@st.cache_data(show_spinner=False)
def load_all(xlsx_path: Path, gwp: dict, ef_unit: str):
    # ef_unit: 'kg' or 'g' -> passed to the model as its INPUT unit
    return compute_structures(xlsx_path, gwp, emission_input_unit=ef_unit)

def download_button_for_table(df: pd.DataFrame, filename_hint: str):
    csv_buf = StringIO()
    df.to_csv(csv_buf, index=False)
    st.download_button(
        label="⬇️ Download table as CSV",
        data=csv_buf.getvalue(),
        file_name=f"{filename_hint}.csv",
        mime="text/csv",
        width="stretch",
        key=f"dl-{filename_hint}"
    )

# =========================
#   HEADER & TOP CONTROLS
# =========================

# --- UPDATED: Columns for title and image ---
col_title, col_image = st.columns([4, 1]) # Ratio of 4:1 for space
with col_title:
    st.title("CanGrid - The Canadian Electricity Grid Project")
    st.caption("Pick a scenario, GWP standard, and explore charts with downloadable tables. Compare across scenarios or regions.")

with col_image:
    st.image(
        "cangrid.png", 
        width=160  # Adjust this width as needed to make the logo look good
    )

# ---------- Controls row 1: compare + GWP + CO2e units (combined) ----------
c1, c2, c3 = st.columns([1.4, 1, 1.3])

with c1:
    compare_mode = st.selectbox("Compare mode", ["None", "Multi-scenario", "Multi-region"], index=0)

with c2:
    gwp_mode = st.radio("GWP (100-yr)", ["AR6", "AR5", "Custom"], index=0, horizontal=True)

with c3:
    co2e_unit_label = st.selectbox(
        "CO₂e unit (model input + display)",
        ["kg CO₂e/kWh", "g CO₂e/kWh"],
        index=0
    )

# --- Combined unit wiring ---
ef_unit = "kg" if co2e_unit_label.startswith("kg") else "g"  # model INPUT unit
if co2e_unit_label.startswith("g"):
    em_scale, EM_LABEL, em_tag = 1000.0, "g CO₂e/kWh", "gco2e_per_kwh"
else:
    em_scale, EM_LABEL, em_tag = 1.0, "kg CO₂e/kWh", "kgco2e_per_kwh"

# Electricity is now fixed to TWh (no unit picker)
ELEC_LABEL = "TWh"
elec_div   = 1e9  # kWh -> TWh

# ---------- Custom GWP inputs if needed ----------
if gwp_mode == "Custom":
    u1, u2, u3, u4 = st.columns([1, 1, 1, 1])
    with u1:
        gwp_CO2 = st.number_input("CO₂ GWP100", value=1.0, step=0.1, format="%.4f")
    with u2:
        gwp_CH4 = st.number_input("CH₄ GWP100", value=27.2, step=0.1, format="%.3f")
    with u3:
        gwp_N2O = st.number_input("N₂O GWP100", value=273.0, step=0.1, format="%.1f")
    with u4:
        gwp_SF6 = st.number_input("SF₆ GWP100", value=25200.0, step=100.0, format="%.0f")
else:
    preset = GWP_AR6 if gwp_mode == "AR6" else GWP_AR5
    gwp_CO2, gwp_CH4, gwp_N2O, gwp_SF6 = preset["CO2"], preset["CH4"], preset["N2O"], preset["SF6"]

gwp = {"CO2": gwp_CO2, "CH4": gwp_CH4, "N2O": gwp_N2O, "SF6": gwp_SF6}

# =========================
#     LOADERS (CACHED)
# =========================
@st.cache_data(show_spinner=False)
def get_data_for_scenario(scenario: str, gwp: dict, ef_unit: str):
    xlsx_path = DATA_DIR / SCENARIO_TO_FILE[scenario]
    return load_all(xlsx_path, gwp, ef_unit)

@st.cache_data(show_spinner=False)
def get_many_scenarios(scenarios: List[str], gwp: dict, ef_unit: str):
    return {sc: get_data_for_scenario(sc, gwp, ef_unit) for sc in scenarios}

# =========================
#     SECONDARY CONTROLS
# =========================
colA, colB = st.columns([1.4, 2])

with colA:
    chart = st.selectbox(
        "Chart",
        [
            "Total Intensity (line)",
            "Energy Mix (% stacked bar, every 5 years)",
            "Energy Mix (stacked bar, every 5 years)",  # fixed TWh
            "CO₂e Contribution (stacked bar, every 5 years)",
            "CO₂e Share by Source (% stacked bar, every 5 years)",
            "Emissions by Source (Operating vs Embodied, single year)",
        ],
        index=0
    )

with colB:
    if compare_mode == "Multi-scenario":
        scenario_list = st.multiselect("Scenarios", SCENARIOS, default=["2023 Current", "2023 Global Net Zero"])
        sector = st.selectbox("Region", SECTORS, index=SECTORS.index("Canada"))
    elif compare_mode == "Multi-region":
        scenario = st.selectbox("Scenario", SCENARIOS, index=SCENARIOS.index("2023 Current"))
        sectors_chosen = st.multiselect("Regions", SECTORS, default=["Canada", "AB", "ON", "QC"])
    else:
        scenario = st.selectbox("Scenario", SCENARIOS, index=SCENARIOS.index("2023 Current"))
        sector = st.selectbox("Region", SECTORS, index=SECTORS.index("Canada"))

# Year control appears only for the single-year chart
def pick_year_control():
    return st.selectbox("Year", list(range(2005, 2051)), index=(2025-2005))

# =========================
#      DATA HANDLES
# =========================
if compare_mode == "Multi-scenario":
    if not scenario_list:
        st.warning("Pick at least one scenario.")
        st.stop()
    data_by_scenario = get_many_scenarios(scenario_list, gwp, ef_unit)
    years = next(iter(data_by_scenario.values()))["years"]
else:
    data = get_data_for_scenario(scenario, gwp, ef_unit)
    years = data["years"]

# =========================
#  TABLE BUILDING HELPERS (unit-aware)
# =========================
def table_mix_percent_single(data_dict, sector: str, step=5):
    frames = []
    for y in years[::step]:
        k = int(y) - 2005
        df = data_dict["grid_by_year"][sector][k][["% of electricity"]].copy()
        df.columns = [y]
        frames.append(df)
    out = pd.concat(frames, axis=1) * 100
    out.index.name = "Source"
    return out

def table_mix_energy_single(data_dict, sector: str, step=5):
    # Base column y is kWh; convert to fixed TWh
    frames = []
    for y in years[::step]:
        k = int(y) - 2005
        df = data_dict["grid_by_year"][sector][k][[y]].copy() / elec_div
        df.columns = [y]
        frames.append(df)
    out = pd.concat(frames, axis=1)
    out.index.name = "Source"
    return out

def table_contrib_single(data_dict, sector: str, step=5):
    frames = []
    for y in years[::step]:
        df = data_dict["total_carbon"][sector][y][["Grid_Intensity_Contribution"]].copy()
        df.columns = [y]
        frames.append(df * em_scale)
    out = pd.concat(frames, axis=1)
    out.index.name = "Source"
    return out

def table_co2e_share_single(data_dict, sector: str, step=5):
    frames = []
    for y in years[::step]:
        df = data_dict["total_carbon"][sector][y][["% of CO2"]].copy() * 100
        df.columns = [y]
        frames.append(df)
    out = pd.concat(frames, axis=1)
    out.index.name = "Source"
    return out

def table_emissions_split_single_year(data_dict, sector: str, year: int):
    df = data_dict["grid_by_year"][sector][year - 2005][["Operating kgCO2/kWh","Embodied kgCO2/kWh"]].copy()
    df *= em_scale
    df.columns = [f"Operating {EM_LABEL}", f"Embodied {EM_LABEL}"]
    df.index.name = "Source"
    return df

# ---------- Robust Series→DataFrame helper for intensity line charts ----------
def _intensity_to_df(series: pd.Series, scale: float) -> pd.DataFrame:
    """
    Ensure a two-column DataFrame with ['Year', 'kgCO2e/kWh'] from a Series,
    regardless of whether reset_index() names the first column 'index' or 'Year'.
    Also applies the selected display-unit scale.
    """
    df = series.rename("kgCO2e/kWh").reset_index()
    first_col = df.columns[0]
    if first_col != "Year":
        df.rename(columns={first_col: "Year"}, inplace=True)
    df["kgCO2e/kWh"] = df["kgCO2e/kWh"] * scale
    return df

# =========================
#  AXIS STYLING HELPERS (dynamic titles, ticks, hover)
# =========================
def _axis_formats():
    # Emissions: kg → decimals; g → integers
    em_tick = ",.2f" if EM_LABEL.startswith("kg") else ",.0f"
    em_hover = ".2f" if EM_LABEL.startswith("kg") else ".0f"
    # Electricity (fixed TWh): sensible precision
    e_tick, e_hover = ",.2f", ".2f"
    return em_tick, em_hover, e_tick, e_hover

def style_emissions_axis(fig):
    em_tick, em_hover, _, _ = _axis_formats()
    fig.update_yaxes(title_text=EM_LABEL, tickformat=em_tick, separatethousands=True, rangemode="tozero")
    fig.update_traces(hovertemplate=f"%{{y:{em_hover}}} {EM_LABEL}<extra></extra>")

def style_energy_axis(fig):
    _, _, e_tick, e_hover = _axis_formats()
    fig.update_yaxes(title_text=ELEC_LABEL, tickformat=e_tick, separatethousands=True, rangemode="tozero")
    fig.update_traces(hovertemplate=f"%{{y:{e_hover}}} {ELEC_LABEL}<extra></extra>")

def style_percent_axis(fig, ytitle: str):
    fig.update_yaxes(title_text=ytitle, tickformat=".0f", ticksuffix="%", range=[0, 100])
    fig.update_traces(hovertemplate="%{y:.1f}%<extra></extra>")

# =========================
#      RENDER SECTIONS (with dynamic axes)
# =========================
if compare_mode == "None":
    # ---------- SINGLE SCENARIO / SINGLE REGION ----------
    if chart == "Total Intensity (line)":
        df = _intensity_to_df(data["grid_intensity"][sector], em_scale)
        s_out = df.rename(columns={"kgCO2e/kWh": EM_LABEL})
        title = f"{sector} – Grid CO₂e Intensity ({scenario}, {gwp_mode})"
        fig = px.line(s_out, x="Year", y=EM_LABEL, title=title)
        style_emissions_axis(fig)
        show(fig)
        st.dataframe(s_out)
        download_button_for_table(s_out, f"intensity_{sector}_{scenario.replace(' ','_')}_{gwp_mode}_{em_tag}")

    elif chart == "Energy Mix (% stacked bar, every 5 years)":
        tbl = table_mix_percent_single(data, sector)
        long = tbl.reset_index().melt(id_vars="Source", var_name="Year", value_name="% of electricity")
        fig = px.bar(long, x="Year", y="% of electricity", color="Source",
                     title=f"{sector} – Energy Mix (%) ({scenario}, {gwp_mode})")
        style_percent_axis(fig, ytitle="% of electricity")
        show(fig)
        st.dataframe(tbl.round(2))
        download_button_for_table(tbl.round(2), f"mix_percent_{sector}_{scenario.replace(' ','_')}_{gwp_mode}")

    elif chart == "Energy Mix (stacked bar, every 5 years)":
        tbl = table_mix_energy_single(data, sector)
        long = tbl.reset_index().melt(id_vars="Source", var_name="Year", value_name=ELEC_LABEL)
        fig = px.bar(long, x="Year", y=ELEC_LABEL, color="Source",
                     title=f"{sector} – Energy Mix ({ELEC_LABEL}) ({scenario}, {gwp_mode})")
        style_energy_axis(fig)
        show(fig)
        st.dataframe(tbl.round(3))
        download_button_for_table(tbl.round(3), f"mix_{ELEC_LABEL}_{sector}_{scenario.replace(' ','_')}_{gwp_mode}")

    elif chart == "CO₂e Contribution (stacked bar, every 5 years)":
        tbl = table_contrib_single(data, sector)
        long = tbl.reset_index().melt(id_vars="Source", var_name="Year", value_name=EM_LABEL)
        fig = px.bar(long, x="Year", y=EM_LABEL, color="Source",
                     title=f"{sector} – CO₂e Contribution ({scenario}, {gwp_mode})")
        style_emissions_axis(fig)
        show(fig)
        st.dataframe(tbl.round(5))
        download_button_for_table(tbl.round(5), f"contrib_{sector}_{scenario.replace(' ','_')}_{gwp_mode}_{em_tag}")

    elif chart == "CO₂e Share by Source (% stacked bar, every 5 years)":
        tbl = table_co2e_share_single(data, sector)
        long = tbl.reset_index().melt(id_vars="Source", var_name="Year", value_name="% of CO₂e")
        fig = px.bar(long, x="Year", y="% of CO₂e", color="Source",
                     title=f"{sector} – CO₂e Share by Source ({scenario}, {gwp_mode})")
        style_percent_axis(fig, ytitle="% of CO₂e")
        show(fig)
        st.dataframe(tbl.round(2))
        download_button_for_table(tbl.round(2), f"co2e_share_{sector}_{scenario.replace(' ','_')}_{gwp_mode}")

    elif chart == "Emissions by Source (Operating vs Embodied, single year)":
        year = pick_year_control()
        tbl = table_emissions_split_single_year(data, sector, year)
        long = tbl.reset_index().melt(id_vars="Source", var_name="Type", value_name=EM_LABEL)
        fig = px.bar(long, x="Source", y=EM_LABEL, color="Type", barmode="stack",
                     title=f"{sector} – Emissions by Source ({EM_LABEL}, {year}, {scenario}, {gwp_mode})")
        style_emissions_axis(fig)
        show(fig)
        st.dataframe(tbl.round(6))
        download_button_for_table(tbl.round(6), f"emissions_split_{sector}_{year}_{scenario.replace(' ','_')}_{gWp_mode}_{em_tag}")

elif compare_mode == "Multi-scenario":
    # (not shown here)
    pass
elif compare_mode == "Multi-region":
    # (not shown here)
    pass

st.markdown("---")
st.markdown(
    
    " CanGrid - The Canadian Electricity Grid Project, citation can be found in the GitHub repo [View Project on GitHub](https://github.com/Sleep-Group/CanGrid)"
    ,
    unsafe_allow_html=True

)
