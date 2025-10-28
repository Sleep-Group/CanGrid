import pandas as pd
# === CANGRID path resolver (cross‑platform) ===
from pathlib import Path
import os

def _guess_data_dir() -> Path:
    here = Path(__file__).resolve().parent
    candidates = [
        here / "data",
        here.parent / "data",
        Path.cwd() / "data",
        Path(os.getenv("CANGRID_DATA_DIR", "")).expanduser() if os.getenv("CANGRID_DATA_DIR") else None,
    ]
    tried = []
    for d in candidates:
        if d:
            tried.append(str(d))
            if d.exists():
                return d
    raise FileNotFoundError(
        "Could not find a 'data' directory.\n"
        f"Tried: {tried}\n"
        f"Current working directory: {Path.cwd()}\n"
        f"Script location: {here}"
    )

DATA_DIR = _guess_data_dir()


filepath = DATA_DIR / "IESO-Active-Contracted-Generation-List.csv"
#see the file to see source, but it is from their website: https://www.ieso.ca/en/Sector-Participants/Resource-Acquisition-and-Contracts/Contract-Data-and-Reports

Data_Raw = pd.read_csv(filepath)
Breakdown = pd.DataFrame()
Data_Raw_Excluded = Data_Raw

fueltypes = ['Biomass','Natural Gas','Solar','Uranium','Waterpower','Wind','By Product Gas']
for i in range(len(fueltypes)):
    for j in range(len(Data_Raw)):
        if Data_Raw['Fuel Type'][j] == fueltypes[i]:
            Breakdown = pd.concat([Breakdown, Data_Raw.loc[[j]]], ignore_index = True)
            Data_Raw_Excluded = Data_Raw_Excluded.drop(index = j)
Breakdown = Breakdown.drop(columns = ['Contract Type','Supplier Legal Name','Contract Status','Contract Term (Yrs)','Milestone Commercial Operation Date',
                                      'Term Start Date','Term End Date','Fuel Group','Connection Type','Closest City/Town','Upper Municipality','IESO Zone','Regional Planning Zone'])
total_capacity = sum(Data_Raw['Contract Capacity (MW)'])
Breakdown_capacity = sum(Breakdown['Contract Capacity (MW)'])
# print(str((total_capacity - Breakdown_capacity)/total_capacity*100)+'% of total MW Contract Capacity Included')

###IESO_natgas_breakdown
SC = []
CC = []
CO = []

filtered_rows = Breakdown[
    (Breakdown['Fuel Type'] == 'Natural Gas') & (Breakdown['Technology'].isin(['Rankine Cycle','Simple Cycle','Simple Cycle CHP']))
    ]
SC = filtered_rows['Contract Capacity (MW)'].tolist()

filtered_rows = Breakdown[
    (Breakdown['Fuel Type'] == 'Natural Gas') & (Breakdown['Technology'].isin(['Combined Cycle','Combined Cycle CHP']))
    ]
CC = filtered_rows['Contract Capacity (MW)'].tolist()

filtered_rows = Breakdown[
    (Breakdown['Fuel Type'] == 'Natural Gas') & (Breakdown['Technology'].isin(['Combined Heat and Power']))
    ]
CO = filtered_rows['Contract Capacity (MW)'].tolist()

#capacity factors (assuming all gas turbines if not CC, which should be correcct): https://www.eia.gov/electricity/monthly/epm_table_grapher.php?t=epmt_6_07_a
CC_cf = 0.141
CO_cf = 0.588
SC_cf = CC_cf

total_natgas = int(sum(SC)*SC_cf) + int(sum(CC)*CC_cf) + int(sum(CO)*CO_cf)

IESO_natgas_breakdown = pd.Series([
    round(sum(SC)*SC_cf/total_natgas,3),
    round(sum(CC)*CC_cf/total_natgas,3),
    round(sum(CO)*CO_cf/total_natgas,3)
    ], index = ['SC','CC','CO'])