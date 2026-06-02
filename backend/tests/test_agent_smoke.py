import asyncio
import io
import unittest
from unittest.mock import AsyncMock, patch

from fastapi.testclient import TestClient
from sqlalchemy import delete, select

from app.core.database import async_session
from app.main import app
from app.models.agent import AgentFile, AgentMessage, AgentSession, AgentTask
from app.models.match import Match
from app.models.message import Message
from app.models.need import Need
from app.models.need_application import NeedApplication
from app.models.system_config import SystemConfig


class AgentSmokeTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.client_cm = TestClient(app)
        cls.client = cls.client_cm.__enter__()

    @classmethod
    def tearDownClass(cls):
        cls.client_cm.__exit__(None, None, None)

    def setUp(self):
        self.session_ids: list[int] = []
        self.need_ids: list[int] = []

    def tearDown(self):
        asyncio.run(self._cleanup())

    async def _cleanup(self):
        async with async_session() as db:
            if self.need_ids:
                await db.execute(delete(Message).where(Message.need_id.in_(self.need_ids)))
                await db.execute(delete(Match).where(Match.need_id.in_(self.need_ids)))
                await db.execute(delete(NeedApplication).where(NeedApplication.need_id.in_(self.need_ids)))
                await db.execute(delete(Need).where(Need.id.in_(self.need_ids)))
            if self.session_ids:
                await db.execute(delete(AgentTask).where(AgentTask.session_id.in_(self.session_ids)))
                await db.execute(delete(AgentMessage).where(AgentMessage.session_id.in_(self.session_ids)))
                await db.execute(delete(AgentFile).where(AgentFile.session_id.in_(self.session_ids)))
                await db.execute(delete(AgentSession).where(AgentSession.id.in_(self.session_ids)))
            await db.commit()

    def _login(self, username: str = "alice", password: str = "123456") -> tuple[dict, dict]:
        response = self.client.post("/api/auth/login", json={"username": username, "password": password})
        self.assertEqual(response.status_code, 200, response.text)
        payload = response.json()
        headers = {"Authorization": f"Bearer {payload['access_token']}"}
        return payload, headers

    def _create_session(self, headers: dict, title: str) -> int:
        response = self.client.post("/api/agent/sessions", json={"title": title}, headers=headers)
        self.assertEqual(response.status_code, 200, response.text)
        session_id = response.json()["id"]
        self.session_ids.append(session_id)
        return session_id

    def test_invalid_login_returns_401(self):
        response = self.client.post("/api/auth/login", json={"username": "alice", "password": "wrong"})
        self.assertEqual(response.status_code, 401)

    def test_settings_api_key_check_does_not_persist_key(self):
        _, headers = self._login()

        before = self.client.get("/api/settings", headers=headers)
        self.assertEqual(before.status_code, 200, before.text)

        with patch("app.routers.settings.AIClient.chat", new=AsyncMock(return_value="ok")) as chat_mock:
            response = self.client.post(
                "/api/settings/test-api-key",
                json={"deepseek_api_key": "sk-temp-check-contract"},
                headers=headers,
            )

        self.assertEqual(response.status_code, 200, response.text)
        body = response.json()
        self.assertTrue(body["ok"])
        self.assertIn("API Key 可用", body["message"])
        self.assertIn(body["connection_path"], ("default", "local_proxy"))
        chat_mock.assert_awaited_once()

        after = self.client.get("/api/settings", headers=headers)
        self.assertEqual(after.status_code, 200, after.text)
        self.assertEqual(after.json(), before.json())

        async def load_temp_key() -> str | None:
            async with async_session() as db:
                result = await db.execute(
                    select(SystemConfig.value).where(SystemConfig.key == "deepseek_api_key")
                )
                return result.scalar_one_or_none()

        self.assertNotEqual(asyncio.run(load_temp_key()), "sk-temp-check-contract")

    def test_agent_follow_up_publish_flow_works_without_remote_ai(self):
        _, headers = self._login()
        session_id = self._create_session(headers, "TEST-AUTO follow-up")

        response = self.client.post(
            f"/api/agent/sessions/{session_id}/chat",
            json={"message": "我想发布一个需求"},
            headers=headers,
        )
        self.assertEqual(response.status_code, 200, response.text)
        body = response.json()
        self.assertEqual(body["intent"], "publish_need")
        self.assertIsNone(body["drafts"])

        for message in ("组队", "黑客松前端协作", "需要会 Vue、接口联调和项目演示的队友", "多人"):
            response = self.client.post(
                f"/api/agent/sessions/{session_id}/chat",
                json={"message": message},
                headers=headers,
            )
            self.assertEqual(response.status_code, 200, response.text)

        final_body = response.json()
        self.assertEqual(final_body["intent"], "publish_need")
        self.assertEqual(len(final_body["drafts"]), 1)
        draft = final_body["drafts"][0]
        self.assertEqual(draft["type"], "组队")
        self.assertEqual(draft["selection_mode"], "multi")
        self.assertIn("黑客松", draft["title"])
        self.assertIn("Vue", draft["description"])

        with patch("app.services.agent_executor._run_matching_in_background", new=AsyncMock(return_value=None)), patch(
            "app.agents.match_watcher_agent.MatchWatcherAgent.execute",
            new=AsyncMock(return_value={"ok": True}),
        ):
            publish_response = self.client.post(
                f"/api/agent/sessions/{session_id}/confirm-publish",
                json={"draft": draft},
                headers=headers,
            )
        self.assertEqual(publish_response.status_code, 200, publish_response.text)
        created = publish_response.json()["needs"]
        self.assertEqual(len(created), 1)
        self.need_ids.extend([item["id"] for item in created])

    def test_agent_publish_confirmation_message_persists_need_after_follow_up(self):
        _, headers = self._login()
        session_id = self._create_session(headers, "TEST-AUTO confirm by chat")

        start_response = self.client.post(
            f"/api/agent/sessions/{session_id}/chat",
            json={"message": "我要发布一个需求"},
            headers=headers,
        )
        self.assertEqual(start_response.status_code, 200, start_response.text)

        for message in ("组队", "蓝桥杯软件类队友", "需要会算法、C++ 和题解复盘的队友", "多人"):
            response = self.client.post(
                f"/api/agent/sessions/{session_id}/chat",
                json={"message": message},
                headers=headers,
            )
            self.assertEqual(response.status_code, 200, response.text)

        draft_ready = response.json()
        self.assertEqual(draft_ready["intent"], "publish_need")
        self.assertTrue(draft_ready["drafts"])

        with patch("app.services.agent_executor._run_matching_in_background", new=AsyncMock(return_value=None)), patch(
            "app.agents.match_watcher_agent.MatchWatcherAgent.execute",
            new=AsyncMock(return_value={"ok": True}),
        ):
            publish_response = self.client.post(
                f"/api/agent/sessions/{session_id}/chat",
                json={"message": "发布"},
                headers=headers,
            )

        self.assertEqual(publish_response.status_code, 200, publish_response.text)
        publish_body = publish_response.json()
        self.assertTrue(publish_body["needs"])
        self.need_ids.extend([item["id"] for item in publish_body["needs"]])
        self.assertEqual(publish_body["intent"], "publish_need")

        mine_response = self.client.get("/api/needs/mine", headers=headers)
        self.assertEqual(mine_response.status_code, 200, mine_response.text)
        titles = [item["title"] for item in mine_response.json()]
        self.assertTrue(any("蓝桥杯" in title for title in titles), titles)

    def test_agent_asks_for_skills_before_drafting_team_need(self):
        _, headers = self._login()
        session_id = self._create_session(headers, "TEST-AUTO team requirement follow-up")

        response = self.client.post(
            f"/api/agent/sessions/{session_id}/chat",
            json={"message": "帮我发布一个组队需求"},
            headers=headers,
        )
        self.assertEqual(response.status_code, 200, response.text)

        response = self.client.post(
            f"/api/agent/sessions/{session_id}/chat",
            json={"message": "报名参加acm"},
            headers=headers,
        )
        self.assertEqual(response.status_code, 200, response.text)

        response = self.client.post(
            f"/api/agent/sessions/{session_id}/chat",
            json={"message": "多人"},
            headers=headers,
        )
        self.assertEqual(response.status_code, 200, response.text)
        body = response.json()
        self.assertEqual(body["intent"], "publish_need")
        self.assertIsNone(body["drafts"])
        self.assertIn("技能", body["reply"])

        response = self.client.post(
            f"/api/agent/sessions/{session_id}/chat",
            json={"message": "需要会 C++、算法训练和比赛报名流程的队友"},
            headers=headers,
        )
        self.assertEqual(response.status_code, 200, response.text)
        final_body = response.json()
        self.assertEqual(len(final_body["drafts"]), 1)
        draft = final_body["drafts"][0]
        self.assertEqual(draft["selection_mode"], "multi")
        self.assertIn("C++", draft["description"])

    def test_upload_flow_uses_fallbacks_and_returns_publishable_draft(self):
        _, headers = self._login()
        session_id = self._create_session(headers, "TEST-AUTO upload")

        with patch(
            "app.adapters.deepseek_adapter.DeepSeekChatAdapter.chat_with_json",
            new=AsyncMock(side_effect=RuntimeError("offline")),
        ):
            response = self.client.post(
                f"/api/agent/sessions/{session_id}/upload",
                headers=headers,
                files={
                    "file": (
                        "hackathon.txt",
                        io.BytesIO("黑客松项目，需要找一名前端和一名设计一起完善演示".encode("utf-8")),
                        "text/plain",
                    )
                },
            )

        self.assertEqual(response.status_code, 200, response.text)
        body = response.json()
        self.assertTrue(body["file_id"] > 0)
        self.assertIn("summary", body["extracted"])
        self.assertEqual(len(body["drafts"]), 1)

        with patch("app.services.agent_executor._run_matching_in_background", new=AsyncMock(return_value=None)), patch(
            "app.agents.match_watcher_agent.MatchWatcherAgent.execute",
            new=AsyncMock(return_value={"ok": True}),
        ):
            publish_response = self.client.post(
                f"/api/agent/sessions/{session_id}/confirm-publish",
                json={"draft": body["drafts"][0]},
                headers=headers,
            )
        self.assertEqual(publish_response.status_code, 200, publish_response.text)
        self.need_ids.extend([item["id"] for item in publish_response.json()["needs"]])

        tasks_response = self.client.get(f"/api/agent/sessions/{session_id}/tasks", headers=headers)
        self.assertEqual(tasks_response.status_code, 200, tasks_response.text)
        task_types = {task["task_type"] for task in tasks_response.json()}
        self.assertIn("analyze_file", task_types)
        self.assertIn("draft_need", task_types)

    def test_confirm_publish_is_idempotent_for_same_pending_draft(self):
        _, headers = self._login()
        session_id = self._create_session(headers, "TEST-AUTO idempotent publish")

        self.client.post(
            f"/api/agent/sessions/{session_id}/chat",
            json={"message": "我要发布一个需求"},
            headers=headers,
        )
        for message in ("组队", "蓝桥杯搭子", "需要会算法训练、C++ 和报名沟通的队友", "多人"):
            response = self.client.post(
                f"/api/agent/sessions/{session_id}/chat",
                json={"message": message},
                headers=headers,
            )
            self.assertEqual(response.status_code, 200, response.text)

        draft = response.json()["drafts"][0]

        with patch("app.services.agent_executor._run_matching_in_background", new=AsyncMock(return_value=None)), patch(
            "app.agents.match_watcher_agent.MatchWatcherAgent.execute",
            new=AsyncMock(return_value={"ok": True}),
        ):
            first = self.client.post(
                f"/api/agent/sessions/{session_id}/confirm-publish",
                json={"draft": draft},
                headers=headers,
            )
            second = self.client.post(
                f"/api/agent/sessions/{session_id}/confirm-publish",
                json={"draft": draft},
                headers=headers,
            )

        self.assertEqual(first.status_code, 200, first.text)
        first_ids = [item["id"] for item in first.json()["needs"]]
        self.need_ids.extend(first_ids)
        self.assertEqual(len(first_ids), 1)
        self.assertEqual(second.status_code, 409, second.text)

        mine_response = self.client.get("/api/needs/mine", headers=headers)
        self.assertEqual(mine_response.status_code, 200, mine_response.text)
        created = [item for item in mine_response.json() if item["id"] in first_ids]
        self.assertEqual(len(created), 1)

    def test_confirm_publish_can_publish_only_selected_pending_draft(self):
        _, headers = self._login()
        session_id = self._create_session(headers, "TEST-AUTO selected draft publish")
        drafts = [
            {
                "type": "组队",
                "title": "TEST-AUTO selected hackathon teammate",
                "description": "寻找可以一起做黑客松作品的同学。",
                "selection_mode": "multi",
            },
            {
                "type": "求助",
                "title": "TEST-AUTO unselected mentor help",
                "description": "希望获得技术指导。",
                "selection_mode": "single",
            },
        ]

        async def seed_pending_drafts():
            from app.services import agent_service

            async with async_session() as db:
                await agent_service.update_session_planning_state(db, session_id, {"pending_drafts": drafts})

        asyncio.run(seed_pending_drafts())

        with patch("app.services.agent_executor._run_matching_in_background", new=AsyncMock(return_value=None)), patch(
            "app.agents.match_watcher_agent.MatchWatcherAgent.execute",
            new=AsyncMock(return_value={"ok": True}),
        ):
            publish_response = self.client.post(
                f"/api/agent/sessions/{session_id}/confirm-publish",
                json={"draft": [drafts[0]]},
                headers=headers,
            )

        self.assertEqual(publish_response.status_code, 200, publish_response.text)
        created = publish_response.json()["needs"]
        self.need_ids.extend([item["id"] for item in created])
        self.assertEqual([item["title"] for item in created], ["TEST-AUTO selected hackathon teammate"])

        session_response = self.client.get(f"/api/agent/sessions/{session_id}", headers=headers)
        self.assertEqual(session_response.status_code, 200, session_response.text)
        pending = session_response.json()["session"]["planning_state"]["pending_drafts"]
        self.assertEqual(len(pending), 1)
        self.assertEqual(pending[0]["title"], "TEST-AUTO unselected mentor help")

    def test_permission_and_exception_paths_are_guarded(self):
        _, alice_headers = self._login("alice")
        _, bob_headers = self._login("bob")
        session_id = self._create_session(alice_headers, "TEST-AUTO guards")

        unauthorized = self.client.get(f"/api/agent/sessions/{session_id}", headers=bob_headers)
        self.assertEqual(unauthorized.status_code, 404)

        invalid_upload = self.client.post(
            f"/api/agent/sessions/{session_id}/upload",
            headers=alice_headers,
            files={"file": ("bad.exe", io.BytesIO(b"oops"), "application/octet-stream")},
        )
        self.assertEqual(invalid_upload.status_code, 400)

        missing_draft = self.client.post(
            f"/api/agent/sessions/{session_id}/confirm-publish",
            headers=alice_headers,
            json={},
        )
        self.assertEqual(missing_draft.status_code, 400)

        chat = self.client.post(
            f"/api/agent/sessions/{session_id}/chat",
            json={"message": "我想发布一个求助需求"},
            headers=alice_headers,
        )
        self.assertEqual(chat.status_code, 200, chat.text)

        tasks_response = self.client.get(f"/api/agent/sessions/{session_id}/tasks", headers=alice_headers)
        self.assertEqual(tasks_response.status_code, 200, tasks_response.text)
        waiting_task = next(task for task in tasks_response.json() if task["status"] == "waiting_user")

        retry = self.client.post(
            f"/api/agent/sessions/{session_id}/tasks/{waiting_task['id']}/retry",
            headers=alice_headers,
        )
        self.assertEqual(retry.status_code, 400)

    def test_agent_chat_and_draft_message_have_offline_fallbacks(self):
        _, headers = self._login()
        session_id = self._create_session(headers, "TEST-AUTO fallback")

        with patch(
            "app.adapters.deepseek_adapter.DeepSeekChatAdapter.chat",
            new=AsyncMock(side_effect=RuntimeError("offline")),
        ):
            chat_response = self.client.post(
                f"/api/agent/sessions/{session_id}/chat",
                json={"message": "你好，你现在能帮我做什么？"},
                headers=headers,
            )
            self.assertEqual(chat_response.status_code, 200, chat_response.text)
            self.assertIn("可以帮你", chat_response.json()["reply"])

            draft_response = self.client.post(
                "/api/agent/draft-message",
                headers=headers,
                json={
                    "need_title": "黑客松路演页面",
                    "match_name": "Bob",
                    "match_skills": ["Vue", "ECharts"],
                    "match_reason": "他做过可视化项目",
                },
            )
        self.assertEqual(draft_response.status_code, 200, draft_response.text)
        drafted_message = draft_response.json()["message"]
        self.assertIn("黑客松路演页面", drafted_message)
        self.assertIn("Vue", drafted_message)

    def test_agent_dialogue_routes_demo_questions_without_stiff_tool_list(self):
        _, headers = self._login()
        stiff_reply = "我现在可以帮你分析文件、整理需求草稿"

        platform_cases = (
            "帮我用一句话总结这个平台能做什么",
            "一句话告诉我，你的最大特色",
            "你和普通需求发布平台有什么区别",
        )
        with patch(
            "app.adapters.deepseek_adapter.DeepSeekChatAdapter.chat",
            new=AsyncMock(side_effect=RuntimeError("offline")),
        ):
            for message in platform_cases:
                session_id = self._create_session(headers, f"TEST-AUTO platform intro {message[:8]}")
                response = self.client.post(
                    f"/api/agent/sessions/{session_id}/chat",
                    json={"message": message},
                    headers=headers,
                )
                self.assertEqual(response.status_code, 200, response.text)
                body = response.json()
                reply = body["reply"]
                self.assertEqual(body["intent"], "chat")
                self.assertIn("AI", reply)
                self.assertTrue(any(token in reply for token in ("撮合", "匹配", "连接")))
                self.assertNotIn(stiff_reply, reply)

        with patch(
            "app.services.need_discovery_service.recommend_needs_for_user",
            new=AsyncMock(
                return_value=[
                    {
                        "id": 1,
                        "title": "ACM 校赛训练队",
                        "type": "组队",
                        "description": "寻找算法方向队友",
                        "score": 0.91,
                        "reason": "与算法和竞赛兴趣匹配",
                    }
                ]
            ),
        ):
            discover_session = self._create_session(headers, "TEST-AUTO discover existing team")
            discover_response = self.client.post(
                f"/api/agent/sessions/{discover_session}/chat",
                json={"message": "我想报名ACM，有没有现有队伍可以加入？"},
                headers=headers,
            )
            self.assertEqual(discover_response.status_code, 200, discover_response.text)
            discover_body = discover_response.json()
            self.assertEqual(discover_body["intent"], "discover_needs")
            self.assertTrue(discover_body["need_recommendations"])
            self.assertIn("开放需求", discover_body["reply"])

        publish_session = self._create_session(headers, "TEST-AUTO publish routing")
        publish_response = self.client.post(
            f"/api/agent/sessions/{publish_session}/chat",
            json={"message": "帮我发布一个黑客松组队需求"},
            headers=headers,
        )
        self.assertEqual(publish_response.status_code, 200, publish_response.text)
        publish_body = publish_response.json()
        self.assertEqual(publish_body["intent"], "publish_need")
        self.assertIsNone(publish_body["drafts"])
        self.assertTrue(any(token in publish_body["reply"] for token in ("标题", "技能", "人数", "类型")))

        upload_session = self._create_session(headers, "TEST-AUTO upload routing")
        with patch(
            "app.adapters.deepseek_adapter.DeepSeekChatAdapter.chat",
            new=AsyncMock(side_effect=RuntimeError("offline")),
        ):
            upload_response = self.client.post(
                f"/api/agent/sessions/{upload_session}/chat",
                json={"message": "我待会上传一份比赛通知文档，你能先分析再帮我整理吗？"},
                headers=headers,
            )
        self.assertEqual(upload_response.status_code, 200, upload_response.text)
        upload_body = upload_response.json()
        self.assertEqual(upload_body["intent"], "upload_file")
        self.assertIn("上传", upload_body["reply"])


    def test_user_can_apply_to_need_and_owner_can_accept(self):
        _, alice_headers = self._login("alice")
        _, bob_headers = self._login("bob")

        create_response = self.client.post(
            "/api/needs",
            headers=alice_headers,
            json={
                "type": "缁勯槦",
                "title": "TEST-AUTO 双边组队需求",
                "description": "需要会 Vue 和数据可视化的同学一起完成黑客松展示。",
                "selection_mode": "single",
            },
        )
        self.assertEqual(create_response.status_code, 200, create_response.text)
        need_id = create_response.json()["id"]
        self.need_ids.append(need_id)

        detail_response = self.client.get(f"/api/needs/{need_id}", headers=bob_headers)
        self.assertEqual(detail_response.status_code, 200, detail_response.text)
        self.assertTrue(detail_response.json()["can_apply"])

        apply_response = self.client.post(
            f"/api/needs/{need_id}/apply",
            headers=bob_headers,
            json={"message": "我会 Vue、ECharts 和路演页，可以负责前端与可视化。"},
        )
        self.assertEqual(apply_response.status_code, 200, apply_response.text)
        self.assertEqual(apply_response.json()["status"], "pending")

        duplicate_response = self.client.post(
            f"/api/needs/{need_id}/apply",
            headers=bob_headers,
            json={"message": "再次申请"},
        )
        self.assertEqual(duplicate_response.status_code, 400, duplicate_response.text)

        applications_response = self.client.get(
            f"/api/needs/{need_id}/applications",
            headers=alice_headers,
        )
        self.assertEqual(applications_response.status_code, 200, applications_response.text)
        self.assertEqual(len(applications_response.json()["items"]), 1)
        application_id = applications_response.json()["items"][0]["id"]

        accept_response = self.client.post(
            f"/api/needs/applications/{application_id}/accept",
            headers=alice_headers,
            json={"owner_reply": "很匹配，我们继续聊下分工。"},
        )
        self.assertEqual(accept_response.status_code, 200, accept_response.text)
        self.assertEqual(accept_response.json()["status"], "accepted")

        mine_response = self.client.get("/api/needs/applications/mine", headers=bob_headers)
        self.assertEqual(mine_response.status_code, 200, mine_response.text)
        self.assertEqual(mine_response.json()["items"][0]["status"], "accepted")
        self.assertIn("TEST-AUTO", mine_response.json()["items"][0]["need_title"])
        self.assertEqual(mine_response.json()["items"][0]["owner_username"], "alice")
        self.assertEqual(mine_response.json()["items"][0]["owner_user_id"], 1)

        conversation_response = self.client.get(f"/api/messages/1?needId={need_id}", headers=bob_headers)
        self.assertEqual(conversation_response.status_code, 200, conversation_response.text)
        joined_content = "\n".join(item["content"] for item in conversation_response.json())
        self.assertIn("负责前端与可视化", joined_content)
        self.assertIn("继续聊下分工", joined_content)

    def test_selecting_matched_user_accepts_their_pending_application(self):
        _, alice_headers = self._login("alice")
        bob_payload, bob_headers = self._login("bob")

        create_response = self.client.post(
            "/api/needs",
            headers=alice_headers,
            json={
                "type": "组队",
                "title": "TEST-AUTO select accepts application",
                "description": "验证匹配页选定申请人后，申请面板状态同步。",
                "selection_mode": "single",
            },
        )
        self.assertEqual(create_response.status_code, 200, create_response.text)
        need_id = create_response.json()["id"]
        self.need_ids.append(need_id)

        apply_response = self.client.post(
            f"/api/needs/{need_id}/apply",
            headers=bob_headers,
            json={"message": "我想加入这个 ICPC 需求。"},
        )
        self.assertEqual(apply_response.status_code, 200, apply_response.text)
        self.assertEqual(apply_response.json()["status"], "pending")

        select_response = self.client.post(
            f"/api/needs/{need_id}/select",
            headers=alice_headers,
            json={"user_ids": [bob_payload["user"]["id"]]},
        )
        self.assertEqual(select_response.status_code, 200, select_response.text)

        mine_response = self.client.get("/api/needs/applications/mine", headers=bob_headers)
        self.assertEqual(mine_response.status_code, 200, mine_response.text)
        application = next(item for item in mine_response.json()["items"] if item["need_id"] == need_id)
        self.assertEqual(application["status"], "accepted")

    def test_single_need_selection_finalizes_unselected_pending_applications(self):
        _, alice_headers = self._login("alice")
        bob_payload, bob_headers = self._login("bob")
        iris_payload, iris_headers = self._login("iris")

        create_response = self.client.post(
            "/api/needs",
            headers=alice_headers,
            json={
                "type": "组队",
                "title": "TEST-AUTO single selection finalizes applications",
                "description": "单人需求选定一人后，其他待处理申请不应继续待处理。",
                "selection_mode": "single",
            },
        )
        self.assertEqual(create_response.status_code, 200, create_response.text)
        need_id = create_response.json()["id"]
        self.need_ids.append(need_id)

        for headers, message in (
            (bob_headers, "我想加入这个单人需求。"),
            (iris_headers, "我也可以参与这个单人需求。"),
        ):
            apply_response = self.client.post(
                f"/api/needs/{need_id}/apply",
                headers=headers,
                json={"message": message},
            )
            self.assertEqual(apply_response.status_code, 200, apply_response.text)
            self.assertEqual(apply_response.json()["status"], "pending")

        select_response = self.client.post(
            f"/api/needs/{need_id}/select",
            headers=alice_headers,
            json={"user_ids": [bob_payload["user"]["id"]]},
        )
        self.assertEqual(select_response.status_code, 200, select_response.text)
        self.assertEqual(select_response.json()["status"], "已匹配")

        bob_mine = self.client.get("/api/needs/applications/mine", headers=bob_headers)
        self.assertEqual(bob_mine.status_code, 200, bob_mine.text)
        bob_application = next(item for item in bob_mine.json()["items"] if item["need_id"] == need_id)
        self.assertEqual(bob_application["status"], "accepted")

        iris_mine = self.client.get("/api/needs/applications/mine", headers=iris_headers)
        self.assertEqual(iris_mine.status_code, 200, iris_mine.text)
        iris_application = next(item for item in iris_mine.json()["items"] if item["need_id"] == need_id)
        self.assertEqual(iris_application["status"], "rejected")
        self.assertIn("已完成匹配", iris_application["owner_reply"])

    def test_selecting_recommended_candidate_notifies_them_to_continue_conversation(self):
        alice_payload, alice_headers = self._login("alice")
        iris_payload, iris_headers = self._login("iris")

        create_response = self.client.post(
            "/api/needs",
            headers=alice_headers,
            json={
                "type": "组队",
                "title": "TEST-AUTO 蓝桥杯组队",
                "description": "验证被系统推荐后选中的候选人也能看到沟通入口。",
                "selection_mode": "multi",
            },
        )
        self.assertEqual(create_response.status_code, 200, create_response.text)
        need_id = create_response.json()["id"]
        self.need_ids.append(need_id)

        select_response = self.client.post(
            f"/api/needs/{need_id}/select",
            headers=alice_headers,
            json={"user_ids": [iris_payload["user"]["id"]]},
        )
        self.assertEqual(select_response.status_code, 200, select_response.text)

        conversations_response = self.client.get("/api/messages/conversations", headers=iris_headers)
        self.assertEqual(conversations_response.status_code, 200, conversations_response.text)
        self.assertTrue(
            any(item["other_user_id"] == alice_payload["user"]["id"] for item in conversations_response.json()),
            conversations_response.text,
        )

        conversation_response = self.client.get(
            f"/api/messages/{alice_payload['user']['id']}?needId={need_id}",
            headers=iris_headers,
        )
        self.assertEqual(conversation_response.status_code, 200, conversation_response.text)
        joined_content = "\n".join(item["content"] for item in conversation_response.json())
        self.assertIn("TEST-AUTO 蓝桥杯组队", joined_content)
        self.assertIn("继续沟通", joined_content)

    def test_user_can_list_needs_where_they_were_selected(self):
        _, alice_headers = self._login("alice")
        iris_payload, iris_headers = self._login("iris")

        create_response = self.client.post(
            "/api/needs",
            headers=alice_headers,
            json={
                "type": "组队",
                "title": "TEST-AUTO selected need card",
                "description": "验证我的需求页能展示自己被选中的需求。",
                "selection_mode": "multi",
            },
        )
        self.assertEqual(create_response.status_code, 200, create_response.text)
        need_id = create_response.json()["id"]
        self.need_ids.append(need_id)

        select_response = self.client.post(
            f"/api/needs/{need_id}/select",
            headers=alice_headers,
            json={"user_ids": [iris_payload["user"]["id"]]},
        )
        self.assertEqual(select_response.status_code, 200, select_response.text)

        selected_response = self.client.get("/api/needs/selected/mine", headers=iris_headers)
        self.assertEqual(selected_response.status_code, 200, selected_response.text)
        selected_items = selected_response.json()
        self.assertTrue(any(item["id"] == need_id for item in selected_items), selected_items)
        selected_need = next(item for item in selected_items if item["id"] == need_id)
        self.assertEqual(selected_need["username"], "alice")
        self.assertIn(iris_payload["user"]["id"], selected_need["selected_user_ids"])

    def test_delete_need_cancels_background_matching(self):
        _, headers = self._login("alice")
        create_response = self.client.post(
            "/api/needs",
            headers=headers,
            json={
                "type": "组队",
                "title": "TEST-AUTO cancel matching",
                "description": "删除时应该取消后台匹配任务",
                "selection_mode": "single",
            },
        )
        self.assertEqual(create_response.status_code, 200, create_response.text)
        need_id = create_response.json()["id"]
        self.need_ids.append(need_id)

        with patch("app.services.match_engine.cancel_matching", new=AsyncMock(return_value=True)) as cancel_mock:
            delete_response = self.client.delete(f"/api/needs/{need_id}", headers=headers)

        self.assertEqual(delete_response.status_code, 200, delete_response.text)
        cancel_mock.assert_awaited_once_with(need_id)

    def test_delete_need_with_application_and_messages_cleans_related_records(self):
        _, alice_headers = self._login("alice")
        _, bob_headers = self._login("bob")
        create_response = self.client.post(
            "/api/needs",
            headers=alice_headers,
            json={
                "type": "组队",
                "title": "TEST-AUTO delete with application",
                "description": "删除时需要清理申请和站内消息",
                "selection_mode": "single",
            },
        )
        self.assertEqual(create_response.status_code, 200, create_response.text)
        need_id = create_response.json()["id"]
        self.need_ids.append(need_id)

        apply_response = self.client.post(
            f"/api/needs/{need_id}/apply",
            headers=bob_headers,
            json={"message": "我想加入这个测试需求"},
        )
        self.assertEqual(apply_response.status_code, 200, apply_response.text)

        delete_response = self.client.delete(f"/api/needs/{need_id}", headers=alice_headers)

        self.assertEqual(delete_response.status_code, 200, delete_response.text)
        detail_response = self.client.get(f"/api/needs/{need_id}", headers=alice_headers)
        self.assertEqual(detail_response.status_code, 404)

    def test_agent_treats_algorithm_competition_existing_team_need_as_discovery(self):
        _, alice_headers = self._login("alice")
        _, bob_headers = self._login("bob")
        create_response = self.client.post(
            "/api/needs",
            headers=alice_headers,
            json={
                "type": "组队",
                "title": "TEST-AUTO 算法比赛组队",
                "description": "寻找准备算法竞赛、刷题训练和比赛复盘的同学一起组队。",
                "selection_mode": "multi",
            },
        )
        self.assertEqual(create_response.status_code, 200, create_response.text)
        need_id = create_response.json()["id"]
        self.need_ids.append(need_id)

        session_id = self._create_session(bob_headers, "TEST-AUTO algorithm discover")
        response = self.client.post(
            f"/api/agent/sessions/{session_id}/chat",
            headers=bob_headers,
            json={"message": "我想打算法比赛，帮我看看有没有这方面的组队需求"},
        )

        self.assertEqual(response.status_code, 200, response.text)
        body = response.json()
        self.assertEqual(body["intent"], "discover_needs")
        self.assertIsNone(body["drafts"])
        self.assertTrue(body["need_recommendations"])
        self.assertIn(need_id, [item["need_id"] for item in body["need_recommendations"]])

    def test_agent_can_escape_publish_follow_up_when_user_asks_for_existing_needs(self):
        _, alice_headers = self._login("alice")
        _, bob_headers = self._login("bob")
        create_response = self.client.post(
            "/api/needs",
            headers=alice_headers,
            json={
                "type": "组队",
                "title": "TEST-AUTO 现有需求逃逸",
                "description": "已有算法比赛组队需求，用户应该能从发布追问切换到查找现有需求。",
                "selection_mode": "multi",
            },
        )
        self.assertEqual(create_response.status_code, 200, create_response.text)
        need_id = create_response.json()["id"]
        self.need_ids.append(need_id)

        session_id = self._create_session(bob_headers, "TEST-AUTO escape publish follow-up")
        first_response = self.client.post(
            f"/api/agent/sessions/{session_id}/chat",
            headers=bob_headers,
            json={"message": "我想找队友打算法比赛"},
        )
        self.assertEqual(first_response.status_code, 200, first_response.text)
        self.assertEqual(first_response.json()["intent"], "publish_need")

        response = self.client.post(
            f"/api/agent/sessions/{session_id}/chat",
            headers=bob_headers,
            json={"message": "帮我找现有的需求"},
        )

        self.assertEqual(response.status_code, 200, response.text)
        body = response.json()
        self.assertEqual(body["intent"], "discover_needs")
        self.assertIsNone(body["drafts"])
        self.assertTrue(body["need_recommendations"])
        self.assertIn(need_id, [item["need_id"] for item in body["need_recommendations"]])

    def test_agent_can_recommend_existing_needs_for_user(self):
        _, alice_headers = self._login("alice")
        _, bob_headers = self._login("bob")

        create_response = self.client.post(
            "/api/needs",
            headers=alice_headers,
            json={
                "type": "缁勯槦",
                "title": "TEST-AUTO 数据可视化黑客松队友",
                "description": "需要擅长 Vue、ECharts、Python 数据分析的同学一起完成黑客松路演和看板。",
                "selection_mode": "multi",
            },
        )
        self.assertEqual(create_response.status_code, 200, create_response.text)
        need_id = create_response.json()["id"]
        self.need_ids.append(need_id)

        session_id = self._create_session(bob_headers, "TEST-AUTO reverse needs")
        response = self.client.post(
            f"/api/agent/sessions/{session_id}/chat",
            headers=bob_headers,
            json={"message": "我会 Vue、ECharts 和 Python 数据分析，想找一个黑客松可视化需求加入。"},
        )
        self.assertEqual(response.status_code, 200, response.text)
        body = response.json()
        self.assertEqual(body["intent"], "discover_needs")
        self.assertTrue(body["need_recommendations"])
        self.assertEqual(body["need_recommendations"][0]["need_id"], need_id)

        draft_response = self.client.post(
            "/api/agent/draft-application-message",
            headers=bob_headers,
            json={
                "need_id": need_id,
                "need_title": "TEST-AUTO 数据可视化黑客松队友",
                "need_type": "缁勯槦",
                "owner_name": "alice",
                "user_skills": ["Vue", "ECharts", "Python"],
                "match_reason": "你的技能和需求标签高度匹配，适合补足前端和可视化能力。",
            },
        )
        self.assertEqual(draft_response.status_code, 200, draft_response.text)
        self.assertIn("Vue", draft_response.json()["message"])
        self.assertIn("Python", draft_response.json()["message"])


if __name__ == "__main__":
    unittest.main()
