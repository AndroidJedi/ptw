from __future__ import annotations

import unittest
from unittest.mock import AsyncMock, patch

from root_broker.server import RootBroker


class RootBrokerOperationTests(unittest.IsolatedAsyncioTestCase):
    async def test_reset_uses_exact_confirmation_without_backup(self) -> None:
        broker = RootBroker.__new__(RootBroker)
        writer = AsyncMock()
        process = AsyncMock()
        process.wait.return_value = 0
        with (
            patch.object(broker, "_write", new=AsyncMock()) as write,
            patch("asyncio.create_subprocess_exec", new=AsyncMock(return_value=process)) as spawn,
        ):
            await broker._operation({"name": "reset"}, writer)
        spawn.assert_awaited_once_with(
            "/root/ptw/scripts/reset_ptw.sh",
            "--confirm",
            "RESET PTW PRODUCTION",
        )
        self.assertEqual("operation.completed", write.await_args_list[-1].args[1]["type"])

    async def test_unknown_operation_is_rejected(self) -> None:
        broker = RootBroker.__new__(RootBroker)
        with patch.object(broker, "_write", new=AsyncMock()) as write:
            await broker._operation({"name": "other"}, AsyncMock())
        self.assertEqual("unsupported_operation", write.await_args.args[1]["code"])
