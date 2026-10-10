import base64
import json
import re
import shlex
from uuid import UUID

from data.pipeline.contracts import Manifest
from src.workers.frozen_contract import PUBLIC_PURPOSE, SYNTHETIC_PURPOSE, acceptance_selection, canonical_hash
from .contracts import CheckEvidence, Role, WorkerResult
from .sandbox import SandboxExecutor

FEATURE_FILES: dict[Role, str] = {
    "clinical-trials": "src/research-portal/backend/trial_feature.py",
    "drug-safety": "src/research-portal/backend/safety_feature.py",
}


def public_verification_script(manifest: Manifest) -> str:
    if manifest.dataset_kind != "reviewed-public":
        return ""
    acceptance_selection(manifest.model_dump(mode="json"), PUBLIC_PURPOSE)
    return (
        "import json,pathlib\n"
        "from data.pipeline.validate_dataset import validate_artifact,file_sha256\n"
        "from src.workers.frozen_contract import canonical_hash,public_identity,load_public_sources\n"
        "p=pathlib.Path('data/artifacts/development/data-manifest.json')\n"
        "m=validate_artifact(p)\n"
        f"assert canonical_hash(m.model_dump(mode='json'))=={canonical_hash(manifest.model_dump(mode='json'))!r}\n"
        "baseline_record=json.loads(pathlib.Path('prepared-baseline.json').read_bytes())\n"
        "assert baseline_record['acceptance_purpose']=='public-lab-development'\n"
        "assert file_sha256(p)==baseline_record['data_manifest_sha256']\n"
        "assert baseline_record['public_identity']==public_identity(json.loads(p.read_bytes()))\n"
        "for name,expected in baseline_record['protected_files'].items():\n"
        "    assert file_sha256(pathlib.Path(name))==expected, 'Protected source or frozen artifact changed'\n"
        "load_public_sources(p.parent,json.loads(p.read_bytes()),pathlib.Path('.'))\n"
    )


def feature_validation_script(role: Role) -> str:
    """Build a remote oracle from complete source rows, not the candidate's filtered joins."""
    if role == "clinical-trials":
        table, key, model = "trials", "trial_id", "Trial"
        collections = {
            "candidate_ids": ("trial_candidates", "candidate_id"),
            "conditions": ("trial_conditions", "condition"),
        }
        conditions = "[None] + [row[0] for row in connection.execute('SELECT DISTINCT condition FROM trial_conditions ORDER BY condition').fetchall()]"
        call = "feature.query_trials(connection, candidate, condition)"
    elif role == "drug-safety":
        table, key, model = "safety_reports", "report_id", "SafetyReport"
        collections = {
            "candidate_ids": ("safety_report_candidates", "candidate_id"),
            "reaction_terms": ("safety_reactions", "reaction_term"),
        }
        conditions = "[None]"
        call = "feature.query_safety_reports(connection, candidate)"
    else:
        raise ValueError("Only implementation roles have feature validation.")
    return (
        f"    source_cursor = connection.execute('SELECT * FROM {table} ORDER BY {key}')\n"
        "    source_columns = [column[0] for column in source_cursor.description]\n"
        "    source_records = [dict(zip(source_columns, row)) for row in source_cursor.fetchall()]\n"
        f"    collections = {collections!r}\n"
        "    for record in source_records:\n"
        "        for field, (table, column) in collections.items():\n"
        f"            record[field] = [row[0] for row in connection.execute(f'SELECT {{column}} FROM {{table}} WHERE {key} = ? ORDER BY {{column}}', [record[{key!r}]]).fetchall()]\n"
        "    candidates = [row[0] for row in connection.execute('SELECT candidate_id FROM candidates ORDER BY candidate_id').fetchall()]\n"
        f"    conditions = {conditions}\n"
        "    for candidate in candidates:\n"
        "        for condition in conditions:\n"
        f"            expected = {{record[{key!r}]: record for record in source_records if candidate in record['candidate_ids'] and (condition is None or condition in record['conditions'])}}\n"
        f"            rows = {call}\n"
        "            assert isinstance(rows, list), 'Feature must return a list of source records'\n"
        f"            typed = [{model}.model_validate(row).model_dump(mode='json') for row in rows]\n"
        f"            actual = {{record[{key!r}]: record for record in typed}}\n"
        "            assert len(actual) == len(typed), 'Feature returned duplicate source records'\n"
        "            assert set(actual) == set(expected), f'Source record selection mismatch: candidate={candidate}, condition={condition}, expected={sorted(expected)}, actual={sorted(actual)}'\n"
        f"            assert [record[{key!r}] for record in typed] == sorted(expected), 'Source record ordering mismatch; return ascending record identifiers'\n"
        "            for identifier, record in actual.items():\n"
        "                assert record == expected[identifier], f'Source record fidelity mismatch: candidate={candidate}, condition={condition}, record={identifier}, expected={expected[identifier]}, actual={record}'\n"
    )


def feature_conformance_script(role: Role) -> str:
    """Exercise shared records independently of a frozen slice's incidental coverage."""
    return (
        "from data.pipeline.build_dataset import SCHEMA_SQL\n"
        "with duckdb.connect(':memory:',config={'enable_external_access':False}) as connection:\n"
        "    connection.execute(SCHEMA_SQL)\n"
        "    connection.execute(\"INSERT INTO candidates VALUES ('candidate-a','A','fictional conformance'),('candidate-b','B','fictional conformance'),('candidate-c','C','empty')\")\n"
        "    connection.execute(\"INSERT INTO trials VALUES ('trial-shared','Fictional shared trial','PHASE2','RECRUITING','fixture','trial-shared',NULL)\")\n"
        "    connection.execute(\"INSERT INTO trial_candidates VALUES ('trial-shared','candidate-a'),('trial-shared','candidate-b')\")\n"
        "    connection.execute(\"INSERT INTO trial_conditions VALUES ('trial-shared','obesity'),('trial-shared','type-2-diabetes')\")\n"
        "    connection.execute(\"INSERT INTO safety_reports VALUES ('report-shared',2,'fixture','report-shared',NULL)\")\n"
        "    connection.execute(\"INSERT INTO safety_report_candidates VALUES ('report-shared','candidate-a'),('report-shared','candidate-b')\")\n"
        "    connection.execute(\"INSERT INTO safety_reactions VALUES ('report-shared','FICTIONAL, ONE'),('report-shared','FICTIONAL TWO')\")\n"
        + feature_validation_script(role)
    )


async def validate_egress(executor: SandboxExecutor, run_id: UUID) -> list[CheckEvidence]:
    policy = await executor.verify_egress_policy()
    checks = []
    for name, url in (
        ("egress-allowed", "https://open.fda.gov/apis/"),
        ("egress-denied", "https://example.com/"),
    ):
        marker = f"LAB722_{name}:{run_id}:{executor.binding.sandbox_id}"
        if name == "egress-allowed":
            probe = (
                f"with urlopen({url!r}, timeout=20) as response:\n"
                "    assert response.status == 200\n"
                "    assert urlsplit(response.geturl()).hostname == 'open.fda.gov'\n"
            )
        else:
            probe = (
                "try:\n"
                f"    with urlopen({url!r}, timeout=20) as response:\n"
                "        raise RuntimeError('Denied request unexpectedly succeeded')\n"
                "except HTTPError as error:\n"
                "    assert error.code == 403, f'Expected policy HTTP 403, received {error.code}'\n"
            )
        script = (
            "from urllib.request import urlopen\n"
            "from urllib.error import HTTPError\n"
            "from urllib.parse import urlsplit\n"
            f"print({json.dumps(policy, sort_keys=True)!r})\n"
            + probe + f"print({marker!r})\n"
        )
        execution = await executor.execute(
            "python3 -c " + shlex.quote(script), timeout=60, verify_remote_status=True,
        )
        passed = execution.exit_code == 0 and marker in execution.stdout.splitlines()
        receipt = execution.evidence(run_id, name, executor.binding.sandbox_id, passed)
        if not passed:
            raise RuntimeError(f"{name} failed: {execution.stderr or execution.stdout}")
        checks.append(receipt)
    return checks


async def validate_worker_results(
    primary: SandboxExecutor,
    workers: list[WorkerResult],
    implementors: dict[Role, SandboxExecutor],
    manifest: Manifest,
    run_id: UUID,
) -> CheckEvidence:
    payload = base64.b64encode(json.dumps([
        worker.model_dump(mode="json") for worker in workers
    ]).encode()).decode()
    identities = {role: str(executor.binding.sandbox_id) for role, executor in implementors.items()}
    marker = f"LAB722_WORKERS_VALIDATED:{run_id}:{primary.binding.sandbox_id}"
    script = (
        "import base64,json,duckdb\n"
        f"workers=json.loads(base64.b64decode({payload!r}))\n"
        f"identities={identities!r}\n"
        "assert len(workers)==3 and {worker['role'] for worker in workers}==set(identities)\n"
        "with duckdb.connect("
        f"{('data/artifacts/development/' + manifest.database.path)!r},read_only=True"
        ") as connection:\n"
        "    known={row[0] for row in connection.execute("
        "'SELECT source_record_id FROM trials UNION SELECT source_record_id FROM safety_reports'"
        ").fetchall()}\n"
        "for worker in workers:\n"
        f"    assert worker['run_id']=={str(run_id)!r}\n"
        f"    assert worker['dataset_version']=={manifest.dataset_version!r}\n"
        f"    assert worker['logical_sha256']=={manifest.logical_sha256!r}\n"
        "    assert worker['sandbox_id']==identities[worker['role']]\n"
        "    assert not worker['blockers']\n"
        "    assert set(worker['source_record_ids']).issubset(known)\n"
        f"print({marker!r})\n"
    )
    execution = await primary.execute(
        "python3 -c " + shlex.quote(script), timeout=30, verify_remote_status=True,
    )
    passed = execution.exit_code == 0 and marker in execution.stdout.splitlines()
    if not passed:
        raise RuntimeError(f"Independent worker-result validation failed: {execution.stderr or execution.stdout}")
    return execution.evidence(run_id, "worker-schema", primary.binding.sandbox_id, True)


async def integrate_and_validate(
    primary: SandboxExecutor,
    governance: SandboxExecutor,
    implementors: dict[Role, SandboxExecutor],
    manifest: Manifest,
    run_id: UUID,
) -> list[CheckEvidence]:
    """Transfer only scoped source text; execute the candidate exclusively in Sandboxes."""
    proposals = {}
    for role, path in FEATURE_FILES.items():
        proposals[path] = await implementors[role].file(path)
    for target in (primary, governance):
        for path, proposal in proposals.items():
            content = base64.b64encode(proposal["content"].encode()).decode()
            script = (
                "import base64,hashlib,pathlib;"
                f"root=pathlib.Path({target.binding.workspace!r});"
                f"p=root/{path!r};"
                "assert p.is_file() and not p.is_symlink();"
                "assert not any(parent.is_symlink() for parent in p.parents);"
                "assert p.resolve().is_relative_to(root.resolve());"
                f"data=base64.b64decode({content!r});"
                f"assert hashlib.sha256(data).hexdigest()=={proposal['sha256']!r};"
                "p.write_bytes(data);"
                f"assert hashlib.sha256(p.read_bytes()).hexdigest()=={proposal['sha256']!r}"
            )
            result = await target.execute(
                "python3 -c " + shlex.quote(script), verify_remote_status=True,
            )
            if result.exit_code != 0:
                raise RuntimeError(f"Trusted integration failed in {target.binding.sandbox_id}: {result.stderr}")
    script = (
        "import pathlib;"
        "from data.pipeline.validate_dataset import validate_artifact;"
        "m=validate_artifact(pathlib.Path('data/artifacts/development/data-manifest.json'));"
        f"assert m.database.sha256=={manifest.database.sha256!r};"
        f"assert m.logical_sha256=={manifest.logical_sha256!r}"
    )
    if manifest.dataset_kind == "reviewed-public":
        script = public_verification_script(manifest)
    integrity = await primary.execute("python3 -c " + shlex.quote(script), verify_remote_status=True)
    if integrity.exit_code != 0:
        raise RuntimeError(f"The integrated candidate changed its frozen data: {integrity.stderr}")
    marker = f"LAB722_SOURCE_FIDELITY:{run_id}:{primary.binding.sandbox_id}"
    validation = (
        public_verification_script(manifest) +
        "import importlib,sys,duckdb\n"
        "from data.pipeline.contracts import Trial,SafetyReport\n"
        "sys.path.insert(0,'src/research-portal/backend')\n"
        "with duckdb.connect("
        f"{('data/artifacts/development/' + manifest.database.path)!r},read_only=True,"
        "config={'enable_external_access':False}) as connection:\n"
    )
    for role, path in FEATURE_FILES.items():
        module = path.rsplit("/", 1)[1].removesuffix(".py")
        validation += f"    feature = importlib.import_module({module!r})\n" + feature_validation_script(role)
    for role, path in FEATURE_FILES.items():
        module = path.rsplit("/", 1)[1].removesuffix(".py")
        validation += f"feature = importlib.import_module({module!r})\n" + feature_conformance_script(role)
    validation += f"print({marker!r})\n"
    purpose = PUBLIC_PURPOSE if manifest.dataset_kind == "reviewed-public" else SYNTHETIC_PURPOSE
    pattern, count = acceptance_selection(manifest.model_dump(mode="json"), purpose)
    environment = "CALDOVA_EXPECTED_PREVIEW_STATE=starter "
    if purpose == PUBLIC_PURPOSE:
        # The remote trust record supplies the original byte anchor, not a reserialized host model.
        validation += (
            "print('LAB722_PUBLIC_ANCHOR:'+baseline_record['data_manifest_sha256'])\n"
        )
        environment += (
            "CALDOVA_ACCEPTANCE_PURPOSE=public-lab-development "
            "CALDOVA_DATA_MANIFEST_SHA256=$(python3 -c "
            + shlex.quote("import json;print(json.load(open('prepared-baseline.json'))['data_manifest_sha256'])")
            + ") "
        )
    acceptance = await primary.execute(
        "python3 -c " + shlex.quote(validation) + " && "
        + environment + f"python3 -m unittest discover -s tests -p {pattern} -v",
        timeout=120, verify_remote_status=True,
    )
    output = acceptance.stdout + "\n" + acceptance.stderr
    passed = acceptance.exit_code == 0 and marker in acceptance.stdout.splitlines() \
        and re.search(rf"(?m)^Ran {count} tests in ", output) is not None \
        and re.search(r"(?m)^OK\s*$", output) is not None
    if purpose == PUBLIC_PURPOSE and re.search(r"(?m)^(?:OK \(skipped|FAILED|ERROR:)", output):
        passed = False
    checks = [
        acceptance.evidence(run_id, name, primary.binding.sandbox_id, passed)
        for name in ("trial-fixtures", "safety-normalization", "citations",
                     "responsible-use", "application-acceptance")
    ]
    if not passed:
        raise RuntimeError(f"Integrated acceptance failed: {output}")
    return checks
