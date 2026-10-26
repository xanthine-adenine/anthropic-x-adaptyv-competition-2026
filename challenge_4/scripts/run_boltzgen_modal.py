"""Run BoltzGen cyclic peptide design on Modal.

Expects cyclic_peptide_to_ppif.yaml and 2bit.cif alongside this script.

Usage:
  modal run modal/run_boltzgen_modal.py --num-designs 2
  modal run modal/run_boltzgen_modal.py --check   # validate YAML only
"""

import os
from pathlib import Path

from modal import App, Image

GPU = os.environ.get("GPU", "L40S")
TIMEOUT = int(os.environ.get("TIMEOUT", 120))

YAML_NAME = "cyclic_peptide_to_ppif.yaml"


def download_models():
    import subprocess
    subprocess.run(["boltzgen", "download", "all"], check=True)
    print("downloaded BoltzGen models")


image = (
    Image.debian_slim()
    .apt_install("git", "build-essential")
    .pip_install("torch>=2.4.1")
    .run_commands(
        "git clone https://github.com/HannesStark/boltzgen /root/boltzgen",
        "cd /root/boltzgen && git checkout 247b9bbd8b68a60aba854c2968d6a0cddd21ad6d && pip install -e .",
    )
    .run_function(download_models)
)

app = App("boltzgen-cyclic", image=image)


@app.function(timeout=5 * 60, gpu=GPU)
def check_boltzgen(
    yaml_str: str, additional_files: dict[str, bytes],
) -> tuple[str, bytes]:
    from subprocess import run as sp_run
    from tempfile import TemporaryDirectory

    with TemporaryDirectory() as work:
        work = Path(work)
        yaml_path = work / YAML_NAME
        yaml_path.write_text(yaml_str)
        for name, content in additional_files.items():
            (work / name).write_bytes(content)

        cmd = ["boltzgen", "check", str(yaml_path), "--output", str(work)]
        print(f"Running: {' '.join(cmd)}")
        result = sp_run(cmd, capture_output=True, text=True)
        output = result.stdout + result.stderr
        if result.returncode != 0:
            raise RuntimeError(f"boltzgen check failed:\n{output}")

        cif_path = work / yaml_path.with_suffix(".cif").name
        return output, cif_path.read_bytes()


@app.function(timeout=TIMEOUT * 60, gpu=GPU)
def run_boltzgen(
    yaml_str: str, additional_files: dict[str, bytes], num_designs: int = 2,
) -> list[tuple[str, bytes]]:
    from subprocess import run as sp_run
    from tempfile import TemporaryDirectory

    with TemporaryDirectory() as work:
        work = Path(work)
        yaml_path = work / YAML_NAME
        yaml_path.write_text(yaml_str)
        for name, content in additional_files.items():
            (work / name).write_bytes(content)

        out = work / "output"
        cmd = [
            "boltzgen", "run", str(yaml_path),
            "--output", str(out),
            "--protocol", "peptide-anything",
            "--num_designs", str(num_designs),
        ]
        print(f"Running: {' '.join(cmd)}")
        sp_run(cmd, check=True)

        return [
            (str(f.relative_to(out)), f.read_bytes())
            for f in out.rglob("*") if f.is_file()
        ]


@app.local_entrypoint()
def main(
    num_designs: int = 2,
    data_dir: str = "./data/",
    out_dir: str = "./out/",
    check: bool = False,
):
    import re
    from datetime import datetime

    yaml_path = Path(data_dir) / YAML_NAME
    yaml_str = yaml_path.read_text()

    additional_files = {}
    for match in re.finditer(r"path:\s*([^\s\n]+)", yaml_str):
        ref = match.group(1)
        ref_path = yaml_path.parent / ref
        if ref_path.exists():
            additional_files[ref] = ref_path.read_bytes()
            print(f"Including referenced file: {ref}")

    if check:
        output, cif_bytes = check_boltzgen.remote(yaml_str, additional_files)
        print(output)

        cif_name = yaml_path.with_suffix(".cif").name
        tstamp = datetime.now().strftime("%Y%m%d%H%M")[2:]
        dest = Path(out_dir) / f"check_{tstamp}" / cif_name
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_bytes(cif_bytes)
        print(f"Check CIF saved to: {dest}")
        return
    else:
        outputs = run_boltzgen.remote(yaml_str, additional_files, num_designs)

        tstamp = datetime.now().strftime("%Y%m%d%H%M")[2:]
        dest = Path(out_dir) / f"run_{tstamp}"
        for rel, content in outputs:
            p = dest / rel
            p.parent.mkdir(parents=True, exist_ok=True)
            p.write_bytes(content)

        print(f"\nResults saved to: {dest}")