import pandas as pd
import glob
import os

files = sorted(
    glob.glob(
        "dataset/raw/historical_firms/**/*India.csv",
        recursive=True
    )
)

print("Files found:", len(files))

dfs = []

for file in files:
    print("Reading:", file)

    df = pd.read_csv(file)

    # Add year from the acquisition date
    df["year"] = pd.to_datetime(df["acq_date"]).dt.year

    dfs.append(df)

# Combine all years
combined = pd.concat(dfs, ignore_index=True)

# Sort chronologically
combined["acq_date"] = pd.to_datetime(combined["acq_date"])
combined = combined.sort_values("acq_date").reset_index(drop=True)

# Create processed directory
os.makedirs("dataset/processed", exist_ok=True)

# Save combined dataset
output = "dataset/processed/firms_india_2022_2024.csv"
combined.to_csv(output, index=False)

print("\n==========================================")
print("COMBINATION COMPLETE")
print("==========================================")
print("Total records:", len(combined))
print("Columns:", len(combined.columns))
print("Date:", combined["acq_date"].min(), "to", combined["acq_date"].max())
print("Output:", output)