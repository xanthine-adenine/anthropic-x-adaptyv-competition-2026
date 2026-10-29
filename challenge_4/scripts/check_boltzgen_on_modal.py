import os
from pathlib import Path

from modal import App, FunctionCall, Image

GPU = os.environ.get("GPU", "H100")


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

app = App("boltzgen-axa-challenge-4-check", image=image)


@app.function(timeout=5 * 60, gpu=GPU)
def check_boltzgen(
    yaml_name: str,
    yaml_str: str,
    additional_files: dict[str, bytes],
) -> tuple[str, bytes]:
    from subprocess import run as sp_run
    from tempfile import TemporaryDirectory

    with TemporaryDirectory() as work:
        work = Path(work)
        yaml_path = work / yaml_name
        yaml_path.write_text(yaml_str)
        for name, content in additional_files.items():
            (work / name).write_bytes(content)

        cmd = ["boltzgen", "check", str(yaml_path), "--output", str(work)]
        print(f"Running: {' '.join(cmd)}")
        result = sp_run(cmd, capture_output=True, text=True)
        output = result.stdout + result.stderr
        if result.returncode != 0:
            raise RuntimeError(f"Boltzgen check failed:\n{output}")

        cif_path = work / yaml_path.with_suffix(".cif").name
        return output, cif_path.read_bytes()


@app.local_entrypoint()
def main(
    yaml_name: str,
    data_dir: str = "./data/",
    out_dir: str = "./out/",
):
    import re
    from datetime import datetime

    yaml_path = Path(data_dir) / yaml_name
    yaml_str = yaml_path.read_text()

    additional_files = {}
    for match in re.finditer(r"path:\s*([^\s\n]+)", yaml_str):
        ref = match.group(1)
        ref_path = yaml_path.parent / ref
        if ref_path.exists():
            additional_files[ref] = ref_path.read_bytes()
            print(f"Including referenced file: {ref}")

    output, cif_bytes = check_boltzgen.remote(yaml_name, yaml_str, additional_files)
    print(output)

    cif_name = yaml_path.with_suffix(".cif").name
    tstamp = datetime.now().strftime("%Y%m%d%H%M")[2:]
    dest = Path(out_dir) / f"check_{tstamp}" / cif_name
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_bytes(cif_bytes)
    print(f"Check CIF saved to: {dest}")
    return
