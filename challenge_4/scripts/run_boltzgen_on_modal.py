import os
from pathlib import Path

from modal import App, FunctionCall, Image

GPU = os.environ.get("GPU", "H100")
TIMEOUT = int(os.environ.get("TIMEOUT", 24)) * 60


def download_models():
    import subprocess
    print("Downloading BoltzGen models...")
    subprocess.run(["boltzgen", "download", "all"], check=True)
    print("BoltzGen models downloaded")


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

app = App("boltzgen-axa-challenge-4", image=image)


@app.function(timeout=TIMEOUT, gpu=GPU)
def run_boltzgen(
    yaml_name: str,
    yaml_str: str,
    additional_files: dict[str, bytes],
    num_designs: int,
    *boltzgen_args,
) -> list[tuple[str, bytes]]:
    from subprocess import run as sp_run
    from tempfile import TemporaryDirectory

    with TemporaryDirectory() as work:
        work = Path(work)
        yaml_path = work / yaml_name
        yaml_path.write_text(yaml_str)
        for name, content in additional_files.items():
            (work / name).write_bytes(content)

        out = work / "output"
        cmd = [
            "boltzgen", "run", str(yaml_path),
            "--output", str(out),
            "--protocol", "protein-anything",
            "--num_designs", str(num_designs),
            *boltzgen_args,
        ]
        print(f"Running: {' '.join(cmd)}")
        sp_run(cmd, check=True)

        return [
            (str(f.relative_to(out)), f.read_bytes())
            for f in out.rglob("*") if f.is_file()
        ]


@app.local_entrypoint()
def main(
    yaml_name: str,
    num_designs: int = 2,
    data_dir: str = "./data/",
    out_dir: str = "./out/",
    check: bool = False,
    spawn: bool = False,
    call_id: str = "",
):
    import re
    from datetime import datetime

    def save_outputs(outputs: list[tuple[str, bytes]]) -> Path:
        tstamp = datetime.now().strftime("%Y%m%d%H%M")[2:]
        dest = Path(out_dir) / f"run_{tstamp}"
        for rel, content in outputs:
            p = dest / rel
            p.parent.mkdir(parents=True, exist_ok=True)
            p.write_bytes(content)
        return dest

    if call_id:
        outputs = FunctionCall.from_id(call_id).get()
        print(f"\nResults saved to: {save_outputs(outputs)}")
        return

    yaml_path = Path(data_dir) / yaml_name
    yaml_str = yaml_path.read_text()

    additional_files = {}
    for match in re.finditer(r"path:\s*([^\s\n]+)", yaml_str):
        ref = match.group(1)
        ref_path = yaml_path.parent / ref
        if ref_path.exists():
            additional_files[ref] = ref_path.read_bytes()
            print(f"Including referenced file: {ref}")

    if spawn:
        call = run_boltzgen.spawn(yaml_name, yaml_str, additional_files, num_designs)
        print(f"\nSpawned call ID: {call.object_id}")
        print(
            "Collect results with:\n"
            f"  modal run {__file__} --call-id {call.object_id}"
        )
    else:
        outputs = run_boltzgen.remote(yaml_name, yaml_str, additional_files, num_designs)
        print(f"\nResults saved to: {save_outputs(outputs)}")
