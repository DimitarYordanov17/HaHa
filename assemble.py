import os
from pydub import AudioSegment

DATASET = "/01 Dummy-Pc"
NAMES_COUNT = 3

dataset_dir = "Datasets/" + DATASET
output_dir = f"Datasets/{DATASET}/output"
os.makedirs(output_dir, exist_ok=True)

prefix = AudioSegment.from_file(os.path.join(dataset_dir, "start.mp3"))
suffix = AudioSegment.from_file(os.path.join(dataset_dir, "end.mp3"))

names = ["name-00" + str(i+1) for i in range(NAMES_COUNT)]

for name in names:
    middle = AudioSegment.from_file(os.path.join(dataset_dir, f"{name}.mp3"))
    combined = prefix + middle + suffix
    out_path = os.path.join(output_dir, f"{name}_combined.mp3")
    combined.export(out_path, format="mp3")
    print(f"Saved: {out_path}")
