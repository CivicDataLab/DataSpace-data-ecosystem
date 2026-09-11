"""Enable ``python -m disaster_risk_score_model`` as an alias for the CLI."""

from disaster_risk_score_model.cli import main

if __name__ == "__main__":
    raise SystemExit(main())
