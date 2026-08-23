"""Durable private Natal preview population and block-edit orchestration."""

from __future__ import annotations

import asyncio
from typing import Any, Callable, Mapping

from natal.builder import preview_document
from natal.page import LandingPageContent

from .landing_draft_repository import LandingDraftRepository
from .landing_repository import LandingBuildRepository
from .landing_revision import LandingRevisionProvider


class LandingDraftCoordinator:
    def __init__(
        self,
        *,
        repository: LandingDraftRepository,
        build_repository: LandingBuildRepository,
        reviser: LandingRevisionProvider,
        stopped: Callable[[], bool],
    ) -> None:
        self.repository = repository
        self.build_repository = build_repository
        self.reviser = reviser
        self.stopped = stopped

    def verify_ready(self) -> None:
        self.reviser.verify_ready()

    def recover_interrupted(self) -> int:
        return self.repository.recover_interrupted()

    def active(self) -> dict[str, Any] | None:
        return self.repository.active()

    def get(self, draft_set_id: str) -> dict[str, Any]:
        return self.repository.get(draft_set_id)

    def by_request(self, request_id: str) -> dict[str, Any] | None:
        return self.repository.by_request(request_id)

    def latest(self, idea_run_id: str) -> dict[str, Any] | None:
        return self.repository.latest(idea_run_id)

    def create(
        self, prepared: Mapping[str, Any], *, request_id: str, requested_by: str
    ) -> tuple[dict[str, Any], bool]:
        memory = self.build_repository.skill_memory(str(prepared["idea_run_id"]))
        return self.repository.create(
            prepared, request_id=request_id, requested_by=requested_by,
            feedback_ids=[item["id"] for item in memory],
        )

    def retry_population(self, draft_set_id: str) -> dict[str, Any]:
        return self.repository.retry_population(draft_set_id)

    async def populate(self, draft_set_id: str) -> None:
        await asyncio.to_thread(self.populate_sync, draft_set_id)

    def populate_sync(self, draft_set_id: str) -> None:
        try:
            if self.stopped():
                raise RuntimeError("PTW emergency stop is active")
            draft_set = self.repository.mark_populating(draft_set_id)
            captured = set(draft_set["skill_memory_feedback_ids"])
            memory = [
                item for item in self.build_repository.skill_memory(draft_set["idea_run_id"])
                if item["id"] in captured
            ]
            pages, summary, invocation = self.reviser.populate_set(
                brief=dict(draft_set["brief"]), skill_memory=memory
            )
            previews = {
                template_id: preview_document(
                    template_id, dict(draft_set["brief"]), page_content
                )
                for template_id, page_content in pages.items()
            }
            self.repository.complete_population(
                draft_set_id, pages=pages, previews=previews,
                summary=summary, invocation=invocation,
            )
        except Exception as error:
            try:
                self.repository.fail_population(
                    draft_set_id, code=type(error).__name__, message=str(error) or type(error).__name__
                )
            except (KeyError, ValueError):
                pass

    def preview(self, snapshot_id: str) -> dict[str, Any]:
        snapshot = self.repository.snapshot(snapshot_id, include_html=True)
        return {
            "snapshot_id": snapshot["id"], "template_id": snapshot["template_id"],
            "snapshot_number": snapshot["snapshot_number"],
            "artifact_sha256": snapshot["artifact_sha256"], "html": snapshot["preview_html"],
        }

    def create_edit(
        self,
        snapshot_id: str,
        *,
        request_id: str,
        block_id: str,
        instruction: str,
        requested_by: str,
    ) -> tuple[dict[str, Any], bool]:
        return self.repository.create_edit(
            snapshot_id, request_id=request_id, block_id=block_id,
            instruction=instruction, requested_by=requested_by,
        )

    def get_edit(self, request_id: str) -> dict[str, Any]:
        return self.repository.edit(request_id)

    def snapshot(self, snapshot_id: str) -> dict[str, Any]:
        return self.repository.snapshot(snapshot_id)

    async def edit(self, request_id: str) -> None:
        await asyncio.to_thread(self.edit_sync, request_id)

    def edit_sync(self, request_id: str) -> None:
        try:
            if self.stopped():
                raise RuntimeError("PTW emergency stop is active")
            edit = self.repository.mark_editing(request_id)
            draft_set = self.repository.get(edit["draft_set_id"])
            base = self.repository.snapshot(edit["base_snapshot_id"])
            memory = self.build_repository.skill_memory(draft_set["idea_run_id"])
            block, summary, lesson, invocation = self.reviser.edit_block(
                template_id=edit["template_id"], brief=dict(draft_set["brief"]),
                page_content=dict(base["page_content"]), block_id=edit["block_id"],
                instruction=edit["instruction"], skill_memory=memory,
            )
            page = LandingPageContent.from_dict(
                base["page_content"], expected_template_id=edit["template_id"]
            ).replace_block(edit["block_id"], block)
            html = preview_document(
                edit["template_id"], dict(draft_set["brief"]), page
            )
            self.repository.complete_edit(
                request_id, page_content=page.to_dict(), preview_html=html,
                summary=summary, lesson=lesson, invocation=invocation,
            )
        except Exception as error:
            try:
                self.repository.fail_edit(
                    request_id, code=type(error).__name__, message=str(error) or type(error).__name__
                )
            except (KeyError, ValueError):
                pass

    def retry_edit(self, request_id: str) -> dict[str, Any]:
        return self.repository.retry_edit(request_id)

    def proposals(self, draft_set_id: str) -> list[dict[str, Any]]:
        return self.repository.proposals(draft_set_id)

    def proposal(self, proposal_id: str) -> dict[str, Any]:
        return self.repository.proposal(proposal_id)

    def dismiss_proposal(self, proposal_id: str) -> dict[str, Any]:
        return self.repository.dismiss_proposal(proposal_id)

    def mark_proposal_planning(
        self, proposal_id: str, *, lesson: str, command_session_id: str
    ) -> dict[str, Any]:
        return self.repository.mark_proposal_planning(
            proposal_id, lesson=lesson, command_session_id=command_session_id
        )
