from __future__ import annotations

import unittest

from commander.agent_bot import (
    AGENT_DEFINITIONS,
    PERMISSIONS,
    BusinessResearcherAgent,
    CommanderDecisionEngine,
)


class AgentBotContractTests(unittest.TestCase):
    def setUp(self) -> None:
        self.researcher = BusinessResearcherAgent()

    def test_researcher_initiates_a_question_when_market_is_missing(self) -> None:
        result = self.researcher.run("Сервис для планирования семейного питания", {})
        self.assertEqual("request", result["kind"])
        self.assertEqual("ask_user", result["request"].request_type)
        self.assertEqual("ask_user", result["request"].capability)

    def test_researcher_requests_a_new_research_action_after_user_answer(self) -> None:
        result = self.researcher.run("Сервис для планирования семейного питания", {"target_market": "США"})
        self.assertEqual("research_market", result["request"].request_type)
        mode, _ = CommanderDecisionEngine().decide(result["request"])
        self.assertEqual("allowed", mode)

    def test_researcher_delivers_report_only_after_commander_result(self) -> None:
        context = {
            "target_market": "США",
            "market_research": {
                "signals": ["interview first"],
                "competitors": ["replaceable workflow"],
            },
        }
        result = self.researcher.run("Сервис для планирования питания", context)
        self.assertEqual("final", result["kind"])
        self.assertIn("summary", result["report"])
        self.assertIn("research_note", result["report"])

    def test_permission_catalog_keeps_specialist_from_expanding_system(self) -> None:
        self.assertEqual({"commander", "business_researcher"}, {item["id"] for item in AGENT_DEFINITIONS})
        permission = next(item for item in PERMISSIONS if item["agent_id"] == "business_researcher" and item["capability"] == "system_expansion")
        self.assertEqual("denied", permission["mode"])
        commander = next(item for item in PERMISSIONS if item["agent_id"] == "commander" and item["capability"] == "system_expansion")
        self.assertEqual("approval_required", commander["mode"])


if __name__ == "__main__":
    unittest.main()
