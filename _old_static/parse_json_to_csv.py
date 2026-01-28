from datetime import datetime, timedelta
import json

input = "350457791342064_2026-01-22 02:03-2026-01-23 14:03.json"
output = "350457791342064_20260122.csv"
serial = output.strip(".csv")

with open(input, "r") as f:
    rows = json.load(f)

with open(output, "w") as f:
    f.write(f"Serial: {serial}\n")
    f.write("Time; Humidity; Temperature\n")

    for row in rows:
        ts = row.get("Time")
        dt = datetime.fromisoformat(ts)
        rh = row.get("Humidity")
        t = row.get("Temperature")
        f.write(f"{ts}; {rh}; {t}\n")
