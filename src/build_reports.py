"""Rebuild the project's English reports and map assets from archived sources."""
import runpy
import sys


def main():
    commands = [
        ("src.analyze", []), ("src.plot_map", []),
        ("src.compare_funding", []), ("src.plot_funding", []),
        ("src.plot_haf", []), ("src.bff", ["--year", "2024"]),
        ("src.bff_evidence", []), ("src.residential", ["--year", "2025"]),
        ("src.compare_residential_bff", []), ("src.audit_payments", []),
    ]
    original = sys.argv[:]
    try:
        for module, arguments in commands:
            print(f"\nBuilding {module}", flush=True)
            sys.argv = [module, *arguments]
            runpy.run_module(module, run_name="__main__")
    finally:
        sys.argv = original


if __name__ == "__main__":
    main()
