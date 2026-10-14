"""Execute the notebook, or inspect retained evidence with the read-only --check option."""
from pathlib import Path
from datetime import datetime, timezone
from urllib.parse import unquote, urlsplit
import argparse
import hashlib
import importlib.metadata as package_metadata
import json
import os
import re
import sys
import tempfile

sys.dont_write_bytecode = True
import nbformat
import numpy as np
import pandas as pd
from packaging.requirements import Requirement

ROOT = Path(__file__).resolve().parent
NOTEBOOK = ROOT / "victoria_liquor_retail_forecasting.ipynb"
SUMMARY = ROOT / "outputs/execution_summary.json"


def sha256(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def check_retained(require_record=True):
    """Read public artifacts without fitting models, writing files or requiring .generated."""
    assert (ROOT / ".python-version").read_text(encoding="utf-8").strip() == "3.12"
    assert sys.version_info[:2] == (3, 12), "Use Python 3.12 for this project's pinned environment."
    active_versions = {}
    for line in (ROOT / "requirements.txt").read_text(encoding="utf-8").splitlines():
        if not line.strip() or line.lstrip().startswith("#"):
            continue
        requirement = Requirement(line)
        if requirement.marker is not None and not requirement.marker.evaluate({"extra": ""}):
            continue
        installed = package_metadata.version(requirement.name)
        assert installed in requirement.specifier, f"Pinned dependency mismatch: {requirement.name}"
        active_versions[requirement.name] = installed
    notebook = nbformat.read(NOTEBOOK, as_version=4)
    nbformat.validate(notebook)
    code = [cell for cell in notebook.cells if cell.cell_type == "code"]
    errors = [output for cell in code for output in cell.outputs if output.output_type == "error"]
    figures = sum("image/png" in output.get("data", {}) for cell in code for output in cell.outputs)
    assert len(code) == 19 and all(cell.execution_count is not None for cell in code)
    assert not errors and figures == 8
    provenance = json.loads((ROOT / "data/provenance.json").read_text(encoding="utf-8"))
    snapshots, hashes = {}, {}
    for filename, metadata in provenance["snapshots"].items():
        path = ROOT / "data" / filename
        hashes[filename] = sha256(path)
        assert hashes[filename] == metadata["selected_sha256"]
        frame = pd.read_csv(path, parse_dates=["month"])
        assert frame.columns.tolist() == ["month", "turnover_aud_million"]
        assert len(frame) == metadata["rows"] and frame.notna().all().all()
        assert frame.month.is_unique and frame.month.is_monotonic_increasing
        assert frame.month.tolist() == pd.date_range(frame.month.min(), frame.month.max(), freq="MS").tolist()
        assert (frame.turnover_aud_million > 0).all()
        snapshots[filename] = frame.set_index("month")["turnover_aud_million"]
    assignment, extension = snapshots["assignment_vintage.csv"], snapshots["extension_vintage.csv"]
    assert len(assignment) == 488 and len(extension) == 516
    assert np.array_equal(assignment.to_numpy(), extension.loc[assignment.index].to_numpy())
    summary = json.loads(SUMMARY.read_text(encoding="utf-8"))
    assert summary["data_hashes"] == hashes
    if require_record:
        assert summary["status"] == "executed_and_validated"
        assert summary["notebook_sha256"] == sha256(NOTEBOOK), "Execution record is stale."
    else:
        assert summary["status"] == "executed_complete"
    selection = summary["frozen_selection"]
    assert selection["selected_without_final_evaluation"] is True
    metrics = pd.read_csv(ROOT / "outputs/evaluation_metrics.csv").set_index("model")
    predictions = pd.read_csv(ROOT / "outputs/evaluation_predictions.csv", parse_dates=["month"])
    dates = pd.date_range("2022-12-01", "2025-03-01", freq="MS")
    scale = np.mean(np.abs(assignment.to_numpy()[12:] - assignment.to_numpy()[:-12]))
    checked = []
    for model, group in predictions.groupby("model", sort=False):
        assert group.month.tolist() == dates.tolist() and len(group) == 28
        assert np.array_equal(group.actual_AUD_m.to_numpy(), extension.loc[dates].to_numpy())
        residual = group.actual_AUD_m.to_numpy() - group.point_AUD_m.to_numpy()
        values = {"MAE_AUD_m": np.mean(np.abs(residual)), "RMSE_AUD_m": np.sqrt(np.mean(residual ** 2)),
                  "MASE": np.mean(np.abs(residual)) / scale, "mean_error_AUD_m": np.mean(residual)}
        for level in [80, 95]:
            values[f"coverage_{level}"] = np.mean((group.actual_AUD_m >= group[f"lower_{level}"])
                                                 & (group.actual_AUD_m <= group[f"upper_{level}"]))
            values[f"mean_width_{level}_AUD_m"] = np.mean(group[f"upper_{level}"] - group[f"lower_{level}"])
        for name, value in values.items():
            assert np.isclose(value, metrics.loc[model, name], atol=1e-8, rtol=0), (model, name)
        checked.append(model)
    assert set(checked) == set(selection["family_representatives"])
    assert metrics.loc[selection["chosen_model"], "chosen_on_validation"]
    recorded_metrics = {row["model"]: row for row in summary["final_evaluation_metrics"]}
    for model in metrics.index:
        for column in ["MAE_AUD_m", "RMSE_AUD_m", "MASE", "coverage_80", "coverage_95"]:
            assert np.isclose(metrics.loc[model, column], recorded_metrics[model][column], atol=1e-8, rtol=0)
    documents = [(ROOT, cell.source) for cell in notebook.cells if cell.cell_type == "markdown"]
    documents += [(path.parent, path.read_text(encoding="utf-8")) for path in [ROOT / "README.md", ROOT / "data/README.md"]]
    links = []
    for base, text in documents:
        for link in re.findall(r"!?\[[^\]]*\]\(([^)]+)\)", text):
            parsed = urlsplit(link.strip().strip("<>"))
            if parsed.scheme or not parsed.path:
                continue
            target = (base / unquote(parsed.path)).resolve()
            assert target.is_relative_to(ROOT) and target.exists(), f"Broken local link: {link}"
            links.append(target.relative_to(ROOT).as_posix())
    assert (ROOT / "outputs/05_final_evaluation_forecasts.png").read_bytes().startswith(b"\x89PNG\r\n\x1a\n")
    return {"status": "retained_evidence_verified", "mode": "check_saved", "read_only": True,
            "fresh_execution_claim": False, "notebook": NOTEBOOK.name, "notebook_sha256": sha256(NOTEBOOK),
            "code_cells": len(code), "all_code_cells_executed": True, "cell_errors": len(errors),
            "embedded_figures": figures, "nbformat_valid": True, "data_hashes": hashes,
            "python": ".".join(str(value) for value in sys.version_info[:3]), "active_dependency_versions": active_versions,
            "evaluation_models_independently_checked": checked, "evaluation_months": 28,
            "local_links_checked": sorted(set(links)),
            "scope": "Retained final predictions/metrics, source hashes, notebook execution and links only. No independent check of omitted CV rows or new model fitting."}


def check_generated():
    """Check secondary evidence only after a fresh full execution regenerates it."""
    detail = ROOT / ".generated"
    summary = json.loads(SUMMARY.read_text(encoding="utf-8"))
    frozen = json.loads((detail / "frozen_model_selection.json").read_text(encoding="utf-8"))
    assert frozen == summary["frozen_selection"]
    allowed_origins = set(pd.to_datetime(frozen["origins"]))
    assignment = pd.read_csv(ROOT / "data/assignment_vintage.csv", parse_dates=["month"]).set_index("month")["turnover_aud_million"]
    metrics = pd.read_csv(detail / "validation_metrics.csv")
    predictions = pd.read_csv(detail / "validation_predictions.csv", parse_dates=["month"])
    assert len(metrics) == 18
    for (fold, model), group in predictions.groupby(["fold", "model"], sort=False):
        origin = pd.Timestamp(group.origin.iloc[0])
        assert origin in allowed_origins
        dates = pd.date_range(origin + pd.offsets.MonthBegin(1), periods=24, freq="MS")
        assert group.month.tolist() == dates.tolist()
        assert np.array_equal(group.actual_AUD_m.to_numpy(), assignment.loc[dates].to_numpy())
        row = metrics.loc[(metrics.fold == fold) & (metrics.model == model)].iloc[0]
        residual = group.actual_AUD_m.to_numpy() - group.point_AUD_m.to_numpy()
        assert np.isclose(np.mean(np.abs(residual)), row.MAE_AUD_m, atol=1e-8, rtol=0)
        assert np.isclose(np.sqrt(np.mean(residual ** 2)), row.RMSE_AUD_m, atol=1e-8, rtol=0)
    future = pd.read_csv(detail / "dated_forecast_apr2025_mar2027.csv", parse_dates=["month"])
    assert future.month.tolist() == pd.date_range("2025-04-01", "2027-03-01", freq="MS").tolist()
    for level in [80, 95]:
        assert (future[f"lower_{level}"] <= future["point_AUD_m"]).all()
        assert (future[f"upper_{level}"] >= future["point_AUD_m"]).all()
    secondary_figures = sorted(detail.glob("*.png"))
    assert len(secondary_figures) >= 7
    for figure in secondary_figures:
        assert figure.read_bytes().startswith(b"\x89PNG\r\n\x1a\n")
    return {"scope": "Regenerated secondary evidence checked during this full run; not required or rechecked by --check.",
            "validation_assessments_checked": 18, "dated_forecast_months": 24, "directory": ".generated"}


def execute():
    from nbclient import NotebookClient
    from jupyter_client import KernelManager
    SUMMARY.unlink(missing_ok=True)
    try:
        notebook = nbformat.read(NOTEBOOK, as_version=4)
        with tempfile.TemporaryDirectory(prefix="retail_forecast_kernel_") as temporary:
            manager = KernelManager(kernel_name="python3")
            manager.kernel_spec.argv = [sys.executable, "-m", "ipykernel_launcher", "-f", "{connection_file}"]
            client = NotebookClient(notebook, timeout=600, startup_timeout=60, km=manager,
                                    resources={"metadata": {"path": str(ROOT)}})
            environment = dict(os.environ, IPYTHONDIR=str(Path(temporary) / "ipython"),
                               MPLCONFIGDIR=str(Path(temporary) / "matplotlib"))
            try:
                client.execute(env=environment)
            finally:
                if manager.has_kernel:
                    manager.shutdown_kernel(now=True)
        nbformat.validate(notebook)
        with NOTEBOOK.open("w", encoding="utf-8", newline="\n") as stream:
            nbformat.write(notebook, stream)
        retained, generated = check_retained(False), check_generated()
        summary = json.loads(SUMMARY.read_text(encoding="utf-8"))
        summary.update(status="executed_and_validated", notebook_sha256=sha256(NOTEBOOK),
                       checked_at_utc=datetime.now(timezone.utc).isoformat(),
                       validation={"retained_checks": retained, "full_run_generated_checks": generated,
                                   "current_interpreter_used_for_kernel": True, "fresh_execution_claim": True})
        SUMMARY.write_text(json.dumps(summary, indent=2), encoding="utf-8")
    except BaseException:
        SUMMARY.unlink(missing_ok=True)
        raise
    print("Executed and validated the forecast notebook: 19 code cells, zero errors.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true", help="Read retained evidence without writing or fitting models.")
    if parser.parse_args().check:
        print(json.dumps(check_retained(), indent=2))
    else:
        execute()
