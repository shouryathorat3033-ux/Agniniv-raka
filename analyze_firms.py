import pandas as pd

file = "dataset/processed/firms_india_2022_2024.csv"

df = pd.read_csv(file)

print("=" * 60)
print("FIRMS DATASET ANALYSIS")
print("=" * 60)

print("\nTOTAL RECORDS:", len(df))

print("\nDATA TYPES:")
print(df.dtypes)

print("\nCONFIDENCE VALUES:")
print(df["confidence"].value_counts(dropna=False))

print("\nTYPE VALUES:")
print(df["type"].value_counts(dropna=False))

print("\nDAY/NIGHT:")
print(df["daynight"].value_counts(dropna=False))

print("\nSATELLITE:")
print(df["satellite"].value_counts(dropna=False))

print("\nFRP STATISTICS:")
print(df["frp"].describe())

print("\nBRIGHT_Ti4 STATISTICS:")
print(df["bright_ti4"].describe())

print("\nBRIGHT_Ti5 STATISTICS:")
print(df["bright_ti5"].describe())

print("\nSCAN STATISTICS:")
print(df["scan"].describe())

print("\nTRACK STATISTICS:")
print(df["track"].describe())