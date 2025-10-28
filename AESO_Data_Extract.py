import pandas as pd
import matplotlib.pyplot as plt
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


file = DATA_DIR / "AESO.csv"

projections = pd.read_csv(file)
years = []
for i in range(2022,2042):
    years.append(i)

Natural_Gas_Combined_Cycle = []
Cogeneration = []
Natural_Gas_Simple_Cycle= []

for i in range(len(projections)):
    if projections['Scenario'][i] == 'Dispatchable Dominant' and projections['Output'][i] == 'Generation_MWh':
        if projections['Fuel Type'][i] == 'Natural Gas Combined-Cycle':
            Natural_Gas_Combined_Cycle.append(int(projections[' Value '][i].replace(",","")))
        if projections['Fuel Type'][i] == 'Cogeneration':
            Cogeneration.append(int(projections[' Value '][i].replace(",","")))
        if projections['Fuel Type'][i] == 'Natural Gas Simple-Cycle':
             Natural_Gas_Simple_Cycle.append(int(projections[' Value '][i].replace(",","")))
            
DDprojections = pd.DataFrame({
    'Natural Gas Combined-Cycle':Natural_Gas_Combined_Cycle,
    'Cogeneration':Cogeneration,
    'Natural Gas Simple-Cycle':Natural_Gas_Simple_Cycle
                      }, index = years)
DDprojections['Total'] = DDprojections['Natural Gas Combined-Cycle'] + DDprojections['Cogeneration'] + DDprojections['Natural Gas Simple-Cycle']
DDprojections['ratio CC'] = DDprojections['Natural Gas Combined-Cycle'] / DDprojections['Total']
DDprojections['ratio Cogen'] = DDprojections['Cogeneration'] / DDprojections['Total']
DDprojections['ratio SC'] = DDprojections['Natural Gas Simple-Cycle'] / DDprojections['Total']

fig, ax = plt.subplots()

plt.plot(DDprojections['Total'], label = 'Total')
plt.plot(DDprojections['Cogeneration'], label = 'Cogeneration')
plt.plot(DDprojections['Natural Gas Combined-Cycle'], label = 'Combined-Cycle')
plt.plot(DDprojections['Natural Gas Simple-Cycle'], label = 'Simple-Cycle')

ticks = plt.gca().get_xticks()
labels = plt.gca().get_xticklabels()
plt.gca().set_xticks(ticks[::2])
plt.gca().set_xticklabels(labels[::2])

plt.legend(loc = 'upper left', bbox_to_anchor = (1,1), frameon = False)

plt.xlim(2022,2041)
plt.ylim(0,6*10**7)
plt.ylabel('MWh generated')
plt.xlabel('Year')