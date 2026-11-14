from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from plots import render
if __name__ == "__main__": render("fig7_finite_packet_configuration")
