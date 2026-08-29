import pandas as pd

f = "dataset/raw/historical_firms/2022/viirs-snpp/2022/viirs-snpp_2022_India.csv"

df = pd.read_csv(f)

print("COLUMNS:")
print(df.columns.tolist())

print("\nTOTAL RECORDS:")
print(len(df))

print("\nFIRST 5 ROWS:")
print(df.head().to_string())
