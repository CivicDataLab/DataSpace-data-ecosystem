"""
Command-line interface for the disaster risk-score model.

Exposes one console command, ``drsm`` (also runnable as
``python -m disaster_risk_score_model``), with a subcommand per pipeline stage
plus ``init-config`` (scaffold an editable config), ``generate-sample-data``
(write a synthetic dataset) and ``run`` (the whole pipeline end to end).

Configuration is supplied via ``--config-dir`` (or ``RISK_MODEL_CONFIG_DIR``,
or a ``./config`` directory); I/O locations via ``--data-dir`` /
``RISK_MODEL_DATA_DIR`` and ``--input-file`` / ``RISK_MODEL_INPUT_FILE``.
"""

import argparse

from disaster_risk_score_model import (
    config,
    exposure,
    govtresponse,
    hazard,
    sample_data,
    topsis,
    vulnerability,
)

# Factor steps in the order `run` executes them. TOPSIS runs last, separately,
# because it aggregates the factor outputs.
_FACTOR_STEPS = [
    ("hazard", hazard),
    ("exposure", exposure),
    ("vulnerability", vulnerability),
    ("govtresponse", govtresponse),
]


def _run_all(config_dir, data_dir, input_file):
    for _, module in _FACTOR_STEPS:
        module.main(config_dir=config_dir, data_dir=data_dir, input_file=input_file)
    topsis.main(config_dir=config_dir, data_dir=data_dir)


def main(argv=None):
    parser = argparse.ArgumentParser(
        prog="drsm",
        description="Intelligent Data Solution for Disaster Risk Reduction (IDS-DRR).",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    # Reusable option groups.
    cfg_opt = argparse.ArgumentParser(add_help=False)
    cfg_opt.add_argument(
        "--config-dir",
        help="config directory (default: $RISK_MODEL_CONFIG_DIR or ./config).",
    )
    data_opt = argparse.ArgumentParser(add_help=False)
    data_opt.add_argument(
        "--data-dir",
        help="data directory for inputs/outputs (default: $RISK_MODEL_DATA_DIR or ./data).",
    )
    input_opt = argparse.ArgumentParser(add_help=False)
    input_opt.add_argument(
        "--input-file",
        help="master input filename under the data dir (default: $RISK_MODEL_INPUT_FILE or MASTER_VARIABLES.csv).",
    )

    p_init = sub.add_parser("init-config", help="scaffold an editable config directory.")
    p_init.add_argument("dir", help="destination directory for the config templates.")

    sub.add_parser(
        "generate-sample-data",
        parents=[data_opt, input_opt],
        help="write a synthetic sample dataset to the data dir.",
    )

    for name, _ in _FACTOR_STEPS:
        sub.add_parser(
            name,
            parents=[cfg_opt, data_opt, input_opt],
            help=f"compute the {name} factor scores.",
        )
    sub.add_parser(
        "topsis",
        parents=[cfg_opt, data_opt],
        help="aggregate factor scores into the composite risk score.",
    )
    sub.add_parser(
        "run",
        parents=[cfg_opt, data_opt, input_opt],
        help="run the full pipeline (all factors, then TOPSIS).",
    )

    args = parser.parse_args(argv)
    factor_modules = dict(_FACTOR_STEPS)

    if args.command == "init-config":
        config.init_config(args.dir)
    elif args.command == "generate-sample-data":
        sample_data.generate(data_dir=args.data_dir, input_file=args.input_file)
    elif args.command in factor_modules:
        factor_modules[args.command].main(
            config_dir=args.config_dir,
            data_dir=args.data_dir,
            input_file=args.input_file,
        )
    elif args.command == "topsis":
        topsis.main(config_dir=args.config_dir, data_dir=args.data_dir)
    elif args.command == "run":
        _run_all(args.config_dir, args.data_dir, args.input_file)

    return 0
