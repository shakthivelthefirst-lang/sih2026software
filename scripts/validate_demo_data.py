
from pathlib import Path
import pandas as pd
ROOT=Path(__file__).resolve().parents[1]
for p in sorted((ROOT/"data/coimbatore").glob("*.csv")):
    df=pd.read_csv(p,nrows=5)
    print(f"{p.name}: columns={len(df.columns)}")
geo=ROOT/"data/coimbatore/19_gis_parcels.geojson"
print(f"{geo.name}: {'present' if geo.exists() else 'missing'}")
print("Dataset notice:", (ROOT/"data/coimbatore/DATASET_NOTICE.txt").read_text().splitlines()[0])
