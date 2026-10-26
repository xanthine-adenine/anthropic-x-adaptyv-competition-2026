"""Download a PDB structure from RCSB PDB.

Usage:
    uv run python fetch_structure.py [pdb_id]
"""

import argparse
import pathlib

import requests


def main() -> None:
    parser = argparse.ArgumentParser(description="Download a structure from RCSB PDB.")
    parser.add_argument("--pdb-id", default="7r2h", help="PDB ID to download (default: 7r2h)")
    parser.add_argument("--data-dir", default="./data", help="Data directory (default: ./data)")
    args = parser.parse_args()

    data_dir = pathlib.Path(args.data_dir)
    pdb_id = args.pdb_id.lower()
    url = f"https://files.rcsb.org/download/{pdb_id}.cif"

    data_dir.mkdir(parents=True, exist_ok=True)
    out_path = data_dir / f"{pdb_id}.cif"
    print(f"Downloading {pdb_id}.cif... ", end="")
    resp = requests.get(url)
    resp.raise_for_status()
    out_path.write_bytes(resp.content)
    print("done.")
    print(f"Saved to {out_path}")


if __name__ == "__main__":
    main()
