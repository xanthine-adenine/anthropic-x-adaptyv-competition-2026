import argparse
import pathlib

import gemmi


def process_structure(data_dir: pathlib.Path, pdb_id: str):
    st = gemmi.read_structure(str(data_dir / f"{pdb_id}.cif"))
    
    st.remove_ligands_and_waters()
    st.remove_empty_chains()

    model = st[0]
    chains_to_remove = [ch.name for ch in model if ch.name != "A"]
    for name in chains_to_remove:
        model.remove_chain(name)

    st.setup_entities()
    st.assign_subchains()
    st.assign_label_seq_id()

    st.make_mmcif_document().write_file(str(data_dir / f"{pdb_id}_processed.cif"))


def main():
    parser = argparse.ArgumentParser(description="Post-process a PyMOL-processed structure.")
    parser.add_argument("--pdb-id", default="7r2h", help="PDB ID to process (default: 7r2h)")
    parser.add_argument("--data-dir", default="./data", help="Data directory (default: ./data)")
    args = parser.parse_args()

    data_dir = pathlib.Path(args.data_dir)
    pdb_id = args.pdb_id

    cif_path = data_dir / f"{pdb_id}.cif"
    if not cif_path.exists():
        print(f"{cif_path} does not exist")
        exit(1)

    print(f"Processing {pdb_id}... ", end="")
    process_structure(data_dir, pdb_id)
    print("done.")


if __name__ == "__main__":
    main()
