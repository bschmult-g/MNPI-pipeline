"""Interactive CLI and compliance test runner for MNPI Agent System.

Usage:
    # Run built-in test scenarios:
    python main.py --scenario leak
    python main.py --scenario public
    python main.py --scenario roadmap
    python main.py --scenario benign

    # Test custom text:
    python main.py --text "Project Titan is acquiring TechCo next week. Don't share."

    # Interactive session:
    python main.py --interactive
"""

from __future__ import annotations

import argparse
import json
import sys
from schemas import ArbiterVerdict, FactCheckingDossier
from workflow import run_pipeline

SAMPLE_SCENARIOS = {
    "leak": (
        "Don't share this yet, but we are finalizing Project Titan to acquire "
        "TechCo for $2.4B next Tuesday ahead of the upcoming Q3 earnings call."
    ),
    "public": (
        "Target publicly reported Q2 financial results on August 21, "
        "confirming 2.7% comparable sales growth and reaffirming full-year guidance."
    ),
    "roadmap": (
        "The executive committee decided that the roadmap feature release is slipping "
        "by two quarters to allow for architectural redesign."
    ),
    "benign": (
        "Reminder to all team members: the quarterly facilities maintenance "
        "will take place this Saturday from 9 AM to 1 PM."
    ),
}


def print_banner():
    print("=" * 80)
    print("      GOOGLE ADK: MATERIAL NON-PUBLIC INFORMATION (MNPI) COMPLIANCE AGENT")
    print("=" * 80)


def print_results(text: str, dossier: FactCheckingDossier, verdict: ArbiterVerdict):
    print("\n" + "=" * 80)
    print("INPUT TEXT UNDER EVALUATION:")
    print("=" * 80)
    print(f'"{text.strip()}"')

    print("\n" + "-" * 80)
    print("🕵️  AGENT 1: MPNI FACT CHECKER DOSSIER (Synthesized from SA1, SA2, SA3)")
    print("-" * 80)
    print(f"• Entities Identified (SA1):")
    for e in dossier.entities.entities:
        tag = "[RESTRICTED/INTERNAL]" if e.is_internal_or_restricted else "[PUBLIC/GENERAL]"
        print(f"  - {e.name} ({e.category}) {tag} -> {e.notes or 'No notes'}")
    if not dossier.entities.entities:
        print("  - None detected.")

    print(f"\n• Sensitive Triggers Detected (SA2):")
    for t in dossier.triggers.triggers:
        print(f"  - [{t.sensitivity_level}] {t.term} ({t.category})")
    if not dossier.triggers.triggers:
        print("  - None detected.")

    print(f"\n• Public Verification & Secrecy Check (SA3):")
    pub_flag = "✅ VERIFIED PUBLIC" if dossier.public_check.is_publicly_verified else "❌ NON-PUBLIC / UNVERIFIED"
    print(f"  - Status: {pub_flag} (Confidence: {dossier.public_check.verification_confidence:.1%})")
    if dossier.public_check.has_secrecy_markers:
        print(f"  - ⚠️  Linguistic Secrecy Markers Detected: {dossier.public_check.linguistic_markers}")
    else:
        print(f"  - Linguistic Secrecy Markers: None detected.")
    print(f"  - Mosaic Check Notes: {dossier.public_check.mosaic_check_notes}")

    print("\n" + "=" * 80)
    print("⚖️  AGENT 2: MPNI AGENT ARBITER (Decision Authority - 4 Assessment Tests)")
    print("=" * 80)

    tests = [
        verdict.materiality_test,
        verdict.public_availability_test,
        verdict.source_and_duty_test,
        verdict.actionability_harm_test,
    ]

    for t in tests:
        score_bar = "█" * int(t.score * 10) + "░" * (10 - int(t.score * 10))
        print(f"\n[{t.test_name}]")
        print(f"  Score: [{score_bar}] {t.score:.2f} | Result: {t.passed_or_failed}")
        print(f"  Rationale: {t.rationale}")

    print("\n" + "=" * 80)
    print("FINAL COMPLIANCE DETERMINATION:")
    print("=" * 80)
    print(f"• Verdict:            {verdict.verdict}")
    print(f"• Risk Level:         {verdict.risk_level}")
    print(f"• Recommended Action: {verdict.recommended_action}")
    if verdict.redacted_text and verdict.verdict == "MNPI_CONFIRMED":
        print(f"• Redacted Output:    {verdict.redacted_text}")
    print(f"• Justification:      {verdict.summary_justification}")
    print("=" * 80 + "\n")


def main():
    parser = argparse.ArgumentParser(description="MNPI Google ADK Compliance System")
    parser.add_argument(
        "--scenario",
        choices=["leak", "public", "roadmap", "benign"],
        help="Run a built-in compliance test scenario",
    )
    parser.add_argument("--text", type=str, help="Analyze custom input text")
    parser.add_argument("--interactive", action="store_true", help="Launch interactive CLI")
    parser.add_argument("--json", action="store_true", help="Output raw JSON results")

    args = parser.parse_args()
    print_banner()

    if args.scenario:
        sample_text = SAMPLE_SCENARIOS[args.scenario]
        dossier, verdict = run_pipeline(sample_text)
        if args.json:
            print(json.dumps({"dossier": dossier.model_dump(), "verdict": verdict.model_dump()}, indent=2))
        else:
            print_results(sample_text, dossier, verdict)

    elif args.text:
        dossier, verdict = run_pipeline(args.text)
        if args.json:
            print(json.dumps({"dossier": dossier.model_dump(), "verdict": verdict.model_dump()}, indent=2))
        else:
            print_results(args.text, dossier, verdict)

    elif args.interactive:
        print("Type text chunk to analyze (or 'exit' to quit):\n")
        while True:
            try:
                user_input = input("Enter text > ").strip()
                if not user_input:
                    continue
                if user_input.lower() in ("exit", "quit"):
                    break
                dossier, verdict = run_pipeline(user_input)
                print_results(user_input, dossier, verdict)
            except (KeyboardInterrupt, EOFError):
                break
        print("\nExiting MNPI Compliance CLI.")

    else:
        # Default: demonstrate all 4 scenarios
        print("Running all 4 test scenarios:\n")
        for sc_name, sc_text in SAMPLE_SCENARIOS.items():
            print(f">>> SCENARIO: {sc_name.upper()} <<<")
            dossier, verdict = run_pipeline(sc_text)
            print_results(sc_text, dossier, verdict)


if __name__ == "__main__":
    main()
