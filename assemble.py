import os
from pydub import AudioSegment

dataset_dir = "Datasets/00 Dummy"
output_dir = "Datasets/00 Dummy/output"
os.makedirs(output_dir, exist_ok=True)

prefix = AudioSegment.from_file(os.path.join(dataset_dir, "ne sam siguren no mislq che.m4a"))
suffix = AudioSegment.from_file(os.path.join(dataset_dir, "govorq.m4a"))

names = ["dancho", "kondio", "mitko", "petar", "rumqna"]

for name in names:
    middle = AudioSegment.from_file(os.path.join(dataset_dir, f"{name}.m4a"))
    combined = prefix + middle + suffix
    out_path = os.path.join(output_dir, f"{name}_combined.m4a")
    combined.export(out_path, format="ipod")
    print(f"Saved: {out_path}")
