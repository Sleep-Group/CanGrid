import pandas as pd
import numpy as np




from pathlib import Path
import os

def _guess_data_dir() -> Path:
    here = Path(__file__).resolve().parent
    # Probe a few common locations for a 'data' folder
    candidates = [
        here / 'data',
        here.parent / 'data',
        Path.cwd() / 'data',
        Path(os.getenv('CANGRID_DATA_DIR', '')).expanduser() if os.getenv('CANGRID_DATA_DIR') else None,
    ]
    for d in candidates:
        if d and d.exists():
            return d
    raise FileNotFoundError(
        f"Could not find a 'data' directory. Tried: { [str(c) for c in candidates if c] }\n"
        f"Current working directory: {Path.cwd()}\nScript location: {here}"
    )

DATA_DIR = _guess_data_dir()

##########natgas_breakdown
filepath = DATA_DIR / 'Natgas_breakdown.csv'
# from https://globalenergyobservatory.org/list.php?db=PowerPlants&type=Gas
natgas_plant_list = pd.read_csv(filepath)
natgas_plant_list = natgas_plant_list.drop(columns=['CO','Cogeneration','bruh'])

for i in range(len(natgas_plant_list)):
    if natgas_plant_list['Province'][i] == 'Alberta':
        natgas_plant_list.loc[i,'Province'] = 'AB'
    if natgas_plant_list['Province'][i] == 'British Columbia':
        natgas_plant_list.loc[i,'Province'] = 'BC'
    if natgas_plant_list['Province'][i] == 'Manitoba':
        natgas_plant_list.loc[i,'Province'] = 'MB'
    if natgas_plant_list['Province'][i] == 'New Brunswick':
        natgas_plant_list.loc[i,'Province'] = 'NB'
    if natgas_plant_list['Province'][i] == 'Nova Scotia':
        natgas_plant_list.loc[i,'Province'] = 'NS'
    if natgas_plant_list['Province'][i] == 'Ontario':
        natgas_plant_list.loc[i,'Province'] = 'ON'
    if natgas_plant_list['Province'][i] == 'Saskatchewan':
        natgas_plant_list.loc[i,'Province'] = 'SK'
    if natgas_plant_list['Province'][i] == 'Quebec':
        natgas_plant_list.loc[i,'Province'] = 'QC'

sectors = ['Canada','AB','BC','MB','NB','NL','NT','NS','NU','ON','PE','QC','SK','YT']
natgas_breakdown_dict = {}
for i in range(len(sectors)):
    natgas_breakdown_dict[sectors[i]] = []
for i in range(len(natgas_plant_list)):
    for j in range(len(sectors)):
        if natgas_plant_list['Province'][i] == sectors[j]:
            natgas_breakdown_dict[sectors[j]].append([natgas_plant_list['Type of plant'][i],natgas_plant_list['MWh Capacity'][i]])
for i in range(len(natgas_plant_list)):
    natgas_breakdown_dict['Canada'].append([natgas_plant_list['Type of plant'][i],natgas_plant_list['MWh Capacity'][i]])
    
natgas_breakdown = pd.DataFrame(
    {'CO':[0,0,0,0,0,0,0,0,0,0,0,0,0,0],
     'CC':[0,0,0,0,0,0,0,0,0,0,0,0,0,0],
     'SC':[0,0,0,0,0,0,0,0,0,0,0,0,0,0]},
    index = sectors)

#capacity factors (assuming all gas turbines if not CC, which should be correcct): https://www.eia.gov/electricity/monthly/epm_table_grapher.php?t=epmt_6_07_a
CC_cf = 0.141
CO_cf = 0.588
SC_cf = CC_cf

for j in range(len(sectors)):
    for k in range(len(natgas_breakdown_dict[sectors[j]])):
        if natgas_breakdown_dict[sectors[j]][k][0] == 'CC':
            natgas_breakdown.loc[sectors[j],'CC'] = natgas_breakdown.loc[sectors[j],'CC'] + int(natgas_breakdown_dict[sectors[j]][k][1] * CC_cf)
        if natgas_breakdown_dict[sectors[j]][k][0] == 'CO':
            natgas_breakdown.loc[sectors[j],'CO'] = natgas_breakdown.loc[sectors[j],'CO'] + int(natgas_breakdown_dict[sectors[j]][k][1] * CO_cf)
        if natgas_breakdown_dict[sectors[j]][k][0] == 'SC' or 'X': #to be conservative, all that isn't classified is put under the least efficient single cycle, BUT CHANGES VALUES A LOT
            natgas_breakdown.loc[sectors[j],'SC'] = natgas_breakdown.loc[sectors[j],'SC'] + int(natgas_breakdown_dict[sectors[j]][k][1] * SC_cf)
            
natgas_breakdown['Total'] = natgas_breakdown['CC'] + natgas_breakdown['CO'] + natgas_breakdown['SC']
natgas_breakdown['CC%'] = natgas_breakdown['CC'] / natgas_breakdown['Total']
natgas_breakdown['CO%'] = natgas_breakdown['CO'] / natgas_breakdown['Total']
natgas_breakdown['SC%'] = natgas_breakdown['SC'] / natgas_breakdown['Total']

natgas_breakdown = natgas_breakdown.replace(np.nan,123456)

for i in range(len(natgas_breakdown.columns)):
    for j in range(len(natgas_breakdown.index)):
        if natgas_breakdown[natgas_breakdown.columns[i]][natgas_breakdown.index[j]] == 123456:
            natgas_breakdown.loc[natgas_breakdown.index[j], natgas_breakdown.columns[i]] = natgas_breakdown[natgas_breakdown.columns[i]]['Canada']
        natgas_breakdown.loc[natgas_breakdown.index[j], natgas_breakdown.columns[i]] = round(natgas_breakdown.loc[natgas_breakdown.index[j], natgas_breakdown.columns[i]],3)
            
################hydro_breakdown
sectors = ['Canada','AB','BC','MB','NB','NL','NT','NS','NU','ON','PE','QC','SK','YT']
# from: https://www.canada.ca/en/environment-climate-change/services/managing-pollution/fuel-life-cycle-assessment-model/methodology.html#toc21
hydro_breakdown = pd.DataFrame({'res%':[0.78,0.66,0.95,0.998,0.91,0.97,0.56,0,0,0.856,0,0.629,0.97,0]}, index = sectors) #from https://www.canada.ca/en/environment-climate-change/services/managing-pollution/fuel-life-cycle-assessment-model/methodology.html#toc21
hydro_breakdown['riv%'] = 1 - hydro_breakdown['res%']
for i in range(len(hydro_breakdown)):
    if hydro_breakdown.loc[sectors[i],'res%'] == 0:
        hydro_breakdown.loc[sectors[i],'res%'] = 0.50
        hydro_breakdown.loc[sectors[i],'riv%'] = 0.50
    hydro_breakdown.loc[sectors[i],'riv%'] = round(hydro_breakdown.loc[sectors[i],'riv%'],3)

################coal_breakdown
filepath = DATA_DIR / 'coal_breakdown(edited).csv'
# from https://www150.statcan.gc.ca/t1/tbl1/en/cv.action?pid=2510001901, 2021
sectors = ['Canada','AB','BC','MB','NB','NL','NT','NS','NU','ON','PE','QC','SK','YT']

coal_breakdown = pd.read_csv(filepath) #all in MWh
coal_breakdown.set_index('Geography', inplace = True, drop = True)
coal_breakdown = coal_breakdown.transpose()
coal_breakdown.index = 'Canada','NL','PE','NS','NB','QC','ON','MB','SK','AB','BC','YT','NT','NU'
coal_breakdown = coal_breakdown.reindex(sectors)
coal_breakdown['bit%'] = coal_breakdown['bit'] / coal_breakdown['total']
coal_breakdown['sub%'] = coal_breakdown['sub'] / coal_breakdown['total']
coal_breakdown['lig%'] = coal_breakdown['lig'] / coal_breakdown['total']

coal_breakdown = coal_breakdown.replace(np.nan,123456123456)

for i in range(len(coal_breakdown.columns)):
    for j in range(len(coal_breakdown.index)):
        if coal_breakdown[coal_breakdown.columns[i]][coal_breakdown.index[j]] == 123456123456:
            coal_breakdown.loc[coal_breakdown.index[j], coal_breakdown.columns[i]] = coal_breakdown[coal_breakdown.columns[i]]['Canada']
        coal_breakdown.loc[coal_breakdown.index[j], coal_breakdown.columns[i]] = round(coal_breakdown.loc[coal_breakdown.index[j], coal_breakdown.columns[i]],3)
################oil_breakdown
filepath = DATA_DIR / 'Oil_breakdown(edited).csv'
#same source as coal_breakdown
sectors = ['Canada','AB','BC','MB','NB','NL','NT','NS','NU','ON','PE','QC','SK','YT']
oil_breakdown = pd.read_csv(filepath)
oil_breakdown = oil_breakdown.transpose()
oil_breakdown = oil_breakdown.drop(index = 'Geography')
oil_breakdown.columns = ['Heavy_Oil','Diesel']

oil_breakdown['Total'] = oil_breakdown['Heavy_Oil'] + oil_breakdown['Diesel']
oil_breakdown[oil_breakdown == 0] = 0.000001
oil_breakdown['Heavy_Oil%'] = oil_breakdown['Heavy_Oil'] / oil_breakdown['Total']
oil_breakdown['Diesel%'] = oil_breakdown['Diesel'] / oil_breakdown['Total']

oil_breakdown.index = ['Canada','NL','PE','NS','NB','QC','ON','MB','SK','AB','BC','YT','NT','NU']

for i in range(len(oil_breakdown)):
    for j in ['Heavy_Oil%','Diesel%']:
        oil_breakdown.loc[sectors[i],j] = round(oil_breakdown.loc[sectors[i],j],3)
oil_breakdown.loc['PE','Heavy_Oil%'] = 0.500
oil_breakdown.loc['PE','Diesel%'] = 0.500
oil_breakdown['Total%'] = oil_breakdown['Heavy_Oil%'] + oil_breakdown['Diesel%']

#solar_breakdown
filepath = DATA_DIR / 'solar_breakdown.csv'

solar_breakdown = pd.read_csv(filepath)
solar_breakdown.set_index('Sector', inplace = True)

#wind_breakdown
filepath = DATA_DIR / 'wind_breakdown.csv'

wind_breakdown = pd.read_csv(filepath)
wind_breakdown.set_index('Sector', inplace = True)

        