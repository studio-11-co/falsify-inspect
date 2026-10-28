"""CLI for falsify-inspect."""

from __future__ import annotations

import argparse
import json
import sys

from falsify_inspect.core import (
    preregister,
    verify_eval_log,
    PRMLVerificationError,
    MalformedLogError,
)


def _cmd_lock(args: argparse.Namespace) -> int:
    h, manifest = preregister(
        metric=args.metric,
        threshold=args.threshold,
        threshold_direction=args.threshold_direction,
        dataset=args.dataset,
        dataset_hash=args.dataset_hash,
        model_version=args.model_version,
        sample_size=args.sample_size,
        seed=args.seed,
        claim_id=args.claim_id,
        inspect_task=args.task,
        inspect_scorer=args.scorer,
        output_path=args.output,
    )
    sys.stdout.write(f"{h}\n")
    if args.output:
        sys.stderr.write(f"manifest written to {args.output}\n")
    return 0


def _cmd_verify(args: argparse.Namespace) -> int:
    try:
        result = verify_eval_log(
            args.log,
            expected_hash=args.hash,
            threshold=args.threshold,
            threshold_direction=args.threshold_direction,
            pre_registered=args.pre_registered,
            claim_id=args.claim_id,
            sample_size=args.sample_size,
            seed=args.seed,
        )
    except MalformedLogError as exc:
        sys.stderr.write(f"structurally invalid log: {exc}\n")
        return 2
    except PRMLVerificationError as exc:
        sys.stderr.write(f"verification error: {exc}\n")
        return 3
    except json.JSONDecodeError as exc:
        sys.stderr.write(
            f"structurally invalid log: malformed JSON: {exc.msg}\n"
        )
        return 2
    except FileNotFoundError as exc:
        sys.stderr.write(f"log not found: {exc}\n")
        return 2

    sys.stdout.write(json.dumps(result, indent=2, default=str) + "\n")
    if not result["hash_match"]:
        return 3   # tamper
    if not result["threshold_satisfied"]:
        return 10  # fail
    return 0       # pass


def _cmd_gate(args: argparse.Namespace) -> int:
    """CI gate: re-verify an Inspect eval log against a committed manifest.

    Inspect catches exceptions raised by hooks and logs them as warnings, so
    FALSIFY_PRML_STRICT=1 cannot fail `inspect eval` by itself (checked
    against inspect_ai 0.3.285 on 28 Oct 2026). Run this after `inspect eval`
    instead: it applies the same check as the hook and exits
    0 PASS, 10 FAIL, 3 TAMPERED, 2 if it cannot verify.
    """
    try:
        from inspect_ai.log import list_eval_logs, read_eval_log
        from falsify_inspect.hooks import _live_fields
    except ImportError:
        sys.stderr.write("gate needs inspect_ai: pip install 'falsify-inspect[inspect]'\n")
        return 2
    from falsify_inspect.core import load_committed_manifest, verify_live

    try:
        committed, _ = load_committed_manifest(args.manifest)
    except FileNotFoundError:
        sys.stderr.write(f"manifest not found: {args.manifest}\n")
        return 2
    metric = committed.get("metric")
    if not metric:
        sys.stderr.write(f"manifest {args.manifest} has no metric\n")
        return 2

    if args.log:
        target = args.log
    else:
        logs = list_eval_logs(args.log_dir, descending=True)
        if not logs:
            sys.stderr.write(f"no Inspect eval logs in {args.log_dir}\n")
            return 2
        target = logs[0]
    try:
        log = read_eval_log(target)
    except Exception as exc:  # unreadable or missing log
        sys.stderr.write(f"cannot read eval log: {exc}\n")
        return 2
    if getattr(log, "status", None) != "success":
        sys.stderr.write(f"eval log status is {getattr(log, 'status', None)!r}, not 'success'\n")
        return 2

    live = _live_fields(log, metric)
    if live["observed_value"] is None:
        sys.stderr.write(f"metric {metric!r} not found in the eval log scores\n")
        return 2
    verdict = verify_live(manifest_path=args.manifest, **live)
    sys.stdout.write(json.dumps(verdict, indent=2, default=str) + "\n")
    return {"PASS": 0, "FAIL": 10, "TAMPERED": 3}.get(verdict["status"], 2)


def main() -> int:
    p = argparse.ArgumentParser(
        prog="falsify-inspect",
        description="PRML pre-registration for Inspect AI eval logs",
    )
    sub = p.add_subparsers(dest="cmd", required=True)

    pl = sub.add_parser("lock", help="pre-register an eval claim, emit hash")
    pl.add_argument("--metric", required=True)
    pl.add_argument("--threshold", type=float, required=True)
    pl.add_argument(
        "--threshold-direction",
        required=True,
        choices=[">=", "<=", ">", "<", "=="],
    )
    pl.add_argument("--dataset", required=True, help="dataset id (PRML dataset.id)")
    pl.add_argument("--dataset-hash", required=True, help="64 lowercase hex SHA-256 (PRML dataset.hash)")
    pl.add_argument("--model-version", required=True, help="model id (PRML producer.id)")
    pl.add_argument("--sample-size", type=int, default=None)
    pl.add_argument("--seed", type=int, required=True)
    pl.add_argument("--claim-id", default=None, help="PRML claim_id, a UUIDv7 (default: generated)")
    pl.add_argument("--task", default=None, help="Inspect task name (optional)")
    pl.add_argument("--scorer", default=None, help="Inspect scorer name (optional)")
    pl.add_argument("--output", default=None, help="write manifest YAML to path")
    pl.set_defaults(func=_cmd_lock)

    pv = sub.add_parser("verify", help="verify an Inspect eval log against a pre-registered hash")
    pv.add_argument("log", help="path to inspect eval log (.json)")
    pv.add_argument("--hash", required=True, help="expected sha256: hash from lock")
    pv.add_argument("--threshold", type=float, required=True)
    pv.add_argument(
        "--threshold-direction",
        required=True,
        choices=[">=", "<=", ">", "<", "=="],
    )
    pv.add_argument("--pre-registered", required=True, help="RFC 3339 timestamp from lock")
    pv.add_argument("--claim-id", required=True, help="claim_id from the locked manifest (UUIDv7; not derivable from the log)")
    pv.add_argument("--sample-size", type=int, default=None)
    pv.add_argument("--seed", type=int, default=None)
    pv.set_defaults(func=_cmd_verify)

    pg = sub.add_parser(
        "gate",
        help="CI gate: verify the latest (or a given) Inspect eval log against a manifest; "
             "exit 0 PASS, 10 FAIL, 3 TAMPERED, 2 cannot verify",
    )
    pg.add_argument("--manifest", required=True, help="committed .prml.yaml (same file as FALSIFY_PRML)")
    pg.add_argument("--log", default=None, help="path to one eval log (default: newest in --log-dir)")
    pg.add_argument("--log-dir", default="./logs", help="Inspect log directory (default ./logs)")
    pg.set_defaults(func=_cmd_gate)

    args = p.parse_args()
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
