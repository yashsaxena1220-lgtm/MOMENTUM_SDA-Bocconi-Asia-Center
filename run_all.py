"""Rebuild everything from the raw files: python run_all.py"""
import subprocess, sys
for step in ["env_data", "ehr_synthea", "simulate", "train", "score_all", "mimic_demo"]:
    print(f"\n=== {step} ===", flush=True)
    subprocess.run([sys.executable, f"{step}.py"], cwd="src", check=True)
