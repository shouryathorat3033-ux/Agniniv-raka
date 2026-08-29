import pandas as pd
import glob
import os

files = glob.glob(
    "dataset/raw/historical_firms/**/*India.csv",
    recursive=True
)

for file in sorted(files):
    df = pd.read_csv(file)

    print("\n" + "=" * 60)
    print("FILE:", file)
    print("=" * 60)

    print("TOTAL RECORDS:", len(df))
    print("COLUMNS:", df.columns.tolist())

    print("\nMISSING VALUES:")
    print(df.isnull().sum())

    print("\nDATE RANGE:")
    print("FROM:", df["acq_date"].min())
    print("TO:  ", df["acq_date"].max())