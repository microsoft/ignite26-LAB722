"""Render a credential-free, source-pinned VM LCA for the Skillable author."""
import argparse
import base64
import hashlib
import json
from pathlib import Path
import zipfile


def export(destination, editor_id=None):
    root = Path(__file__).resolve().parents[1]
    destination.mkdir(parents=True, exist_ok=True)
    scripts = [
        "initialize-reactor-skillable.ps1", "run-reactor-skillable-vm.ps1",
        "prepare-reactor-swarm.ps1", "prepare-reactor-agent-image.ps1",
        "deploy-reactor.ps1", "setup-reactor-foundry.py",
        "inspect-reactor-toolbox.py", "connect-reactor-frontend.ps1", "wait-reactor-hosted.py",
    ]
    files = [root / "scripts" / name for name in scripts]
    files += [
        root / "infra" / "reactor.bicep",
        root / "infra" / "modules" / "reactor-access.bicep",
        root / "data" / "reactor-research-images.json",
        root / "src" / "reactor" / "agent_runtime.py",
        root / "src" / "reactor" / "openapi.json",
        root / "src" / "orchestrator" / "requirements.txt",
    ]
    archive = destination / "reactor2-source.zip"
    with zipfile.ZipFile(archive, "w", zipfile.ZIP_DEFLATED) as output:
        for source in files:
            info = zipfile.ZipInfo(source.relative_to(root).as_posix(), (2026, 11, 8, 0, 0, 0))
            info.compress_type = zipfile.ZIP_DEFLATED
            output.writestr(info, source.read_bytes())
    payload = archive.read_bytes()
    template = (root / "scripts" / "skillable-reactor2-vm.ps1").read_text(encoding="utf-8-sig")
    rendered = template.replace("__REACTOR2_SOURCE_BASE64__", base64.b64encode(payload).decode())
    rendered = rendered.replace("__REACTOR2_SOURCE_SHA256__", hashlib.sha256(payload).hexdigest())
    (destination / "reactor2-vm-lca.ps1").write_text(rendered, encoding="utf-8")
    if editor_id is not None:
        arm = (root / "infra" / "skillable" / "reactor2.azuredeploy.json").read_text(encoding="utf-8-sig")
        browser = (
            "() => {"
            f"if(location.pathname!=='/CloudTemplate/Edit/{editor_id}')throw Error('Wrong template editor');"
            f"editor.setValue({json.dumps(arm)});"
            "return {parameters:Object.keys(JSON.parse(editor.getValue()).parameters),length:editor.getValue().length};}"
        )
        (destination / "set-arm-editor.js").write_text(browser, encoding="utf-8")
    print(f"Source files: {len(files)}; archive SHA256: {hashlib.sha256(payload).hexdigest()}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--editor-id", type=int)
    args = parser.parse_args()
    export(args.output.resolve(), args.editor_id)
