import pathlib
import importlib
import os
import sys
import tempfile
import unittest
from datetime import datetime, timedelta


ROOT = pathlib.Path(__file__).resolve().parents[2]
BACKEND = ROOT / "backend"
FRONTEND = ROOT / "frontend"


class ProjectContractTests(unittest.TestCase):
    def test_runtime_requirements_include_agent_file_and_embedding_dependencies(self):
        requirements = (BACKEND / "requirements.txt").read_text(encoding="utf-8")

        for package in ("sentence-transformers", "python-docx", "PyPDF2"):
            with self.subTest(package=package):
                self.assertIn(package, requirements)

    def test_typescript_six_deprecation_is_explicitly_handled(self):
        tsconfig = (FRONTEND / "tsconfig.app.json").read_text(encoding="utf-8")

        self.assertIn('"ignoreDeprecations": "6.0"', tsconfig)

    def test_backend_config_anchors_env_and_sqlite_to_backend_directory(self):
        source = (BACKEND / "app" / "core" / "config.py").read_text(encoding="utf-8")

        self.assertIn("BACKEND_DIR", source)
        self.assertIn('DB_PATH = BACKEND_DIR / "app.db"', source)
        self.assertIn('SettingsConfigDict(env_file=BACKEND_DIR / ".env")', source)
        self.assertIn("DB_PATH.as_posix()", source)

    def test_backend_config_accepts_release_debug_environment_value(self):
        previous_debug = os.environ.get("DEBUG")
        os.environ["DEBUG"] = "release"
        sys.modules.pop("app.core.config", None)
        try:
            config = importlib.import_module("app.core.config")
            self.assertFalse(config.settings.DEBUG)
        finally:
            sys.modules.pop("app.core.config", None)
            if previous_debug is None:
                os.environ.pop("DEBUG", None)
            else:
                os.environ["DEBUG"] = previous_debug

    def test_settings_update_can_refresh_ai_client_runtime_key(self):
        from app.integrations import client as client_module

        previous_key = client_module.settings.DEEPSEEK_API_KEY
        previous_client = client_module._ai_client
        try:
            client_module.settings.DEEPSEEK_API_KEY = "sk-old-runtime-contract"
            client_module._ai_client = None
            old_client = client_module.get_ai_client()

            client_module.apply_runtime_config(deepseek_api_key="sk-new-runtime-contract")
            new_client = client_module.get_ai_client()

            self.assertEqual(old_client.api_key, "sk-old-runtime-contract")
            self.assertIsNot(old_client, new_client)
            self.assertEqual(new_client.api_key, "sk-new-runtime-contract")
        finally:
            client_module.settings.DEEPSEEK_API_KEY = previous_key
            client_module._ai_client = previous_client

    def test_settings_update_persists_api_key_to_env_file(self):
        from app.routers import settings as settings_router

        with tempfile.TemporaryDirectory() as temp_dir:
            env_path = pathlib.Path(temp_dir) / ".env"
            env_path.write_text(
                "APP_NAME=Campus AI Match\n"
                "DEEPSEEK_API_KEY=sk-old-env-contract\n"
                "DEBUG=true\n",
                encoding="utf-8",
            )

            settings_router.persist_env_value(
                "DEEPSEEK_API_KEY",
                "sk-new-env-contract",
                env_path=env_path,
            )

            content = env_path.read_text(encoding="utf-8")
            self.assertIn("DEEPSEEK_API_KEY=sk-new-env-contract", content)
            self.assertNotIn("DEEPSEEK_API_KEY=sk-old-env-contract", content)
            self.assertIn("DEBUG=true", content)

    def test_settings_page_explains_api_key_changes_take_effect_immediately(self):
        source = (FRONTEND / "src" / "views" / "SettingsView.vue").read_text(encoding="utf-8")

        self.assertIn("无需重启", source)
        self.assertNotIn("重启服务后生效", source)

    def test_settings_api_key_check_is_available_before_save(self):
        router_source = (BACKEND / "app" / "routers" / "settings.py").read_text(encoding="utf-8")
        client_source = (BACKEND / "app" / "integrations" / "client.py").read_text(encoding="utf-8")
        api_source = (FRONTEND / "src" / "api" / "settings.ts").read_text(encoding="utf-8")
        view_source = (FRONTEND / "src" / "views" / "SettingsView.vue").read_text(encoding="utf-8")

        self.assertIn('@router.post("/test-api-key")', router_source)
        self.assertIn("AIClient(api_key=key", router_source)
        self.assertIn("max_retries=0", router_source)
        self.assertIn("def explain_api_check_error", router_source)
        self.assertIn("api_key: str | None = None", client_source)
        self.assertIn("testApiKey", api_source)
        self.assertIn("/settings/test-api-key", api_source)
        self.assertIn("testApiKeyBeforeSave", view_source)
        self.assertIn("ElMessageBox.alert", view_source)
        self.assertIn("connection_path", api_source)
        self.assertIn("formatConnectionPath", view_source)

    def test_ai_client_can_fallback_to_local_proxy(self):
        client_source = (BACKEND / "app" / "integrations" / "client.py").read_text(encoding="utf-8")

        self.assertIn("LOCAL_PROXY_URL", client_source)
        self.assertIn('"local_proxy", LOCAL_PROXY_URL', client_source)
        self.assertIn("last_connection_path", client_source)
        self.assertIn("_is_network_error", client_source)
        self.assertIn('kwargs["proxy"] = proxy_url', client_source)

    def test_message_conversation_query_partitions_by_actual_other_user(self):
        source = (BACKEND / "app" / "services" / "message_service.py").read_text(encoding="utf-8")

        self.assertIn("conversation_partner_expr", source)
        self.assertNotIn("partition_by=func.max", source)

    def test_message_conversation_list_preserves_need_context(self):
        service_source = (BACKEND / "app" / "services" / "message_service.py").read_text(encoding="utf-8")
        schema_source = (BACKEND / "app" / "schemas" / "message.py").read_text(encoding="utf-8")
        type_source = (FRONTEND / "src" / "types" / "index.ts").read_text(encoding="utf-8")
        list_source = (FRONTEND / "src" / "components" / "message" / "ConversationList.vue").read_text(encoding="utf-8")
        view_source = (FRONTEND / "src" / "views" / "MessagesView.vue").read_text(encoding="utf-8")

        self.assertIn("need_id: int", schema_source)
        self.assertIn("Message.need_id", service_source)
        self.assertIn("partition_by=(conversation_partner_expr(user_id), Message.need_id)", service_source)
        self.assertIn("need_id: number", type_source)
        self.assertIn("`${c.other_user_id}-${c.need_id}`", list_source)
        self.assertIn("emit('select', c.other_user_id, c.need_id)", list_source)
        self.assertIn(":active-need-id=\"activeNeedId\"", view_source)
        self.assertNotIn("conversations.value.unshift", view_source)

    def test_frontend_exposes_promised_demo_features(self):
        need_create = (FRONTEND / "src" / "views" / "NeedCreateView.vue").read_text(encoding="utf-8")
        match_result = (FRONTEND / "src" / "views" / "MatchResultView.vue").read_text(encoding="utf-8")
        agent_store = (FRONTEND / "src" / "stores" / "agent.ts").read_text(encoding="utf-8")
        agent_view = (FRONTEND / "src" / "views" / "AgentView.vue").read_text(encoding="utf-8")

        self.assertIn("needTemplates", need_create)
        self.assertIn("comparison-table", match_result)
        self.assertIn("suggestions", agent_store)
        self.assertIn("主动建议", agent_view)

    def test_ai_description_generation_respects_selection_mode(self):
        need_api = (FRONTEND / "src" / "api" / "needs.ts").read_text(encoding="utf-8")
        need_create = (FRONTEND / "src" / "views" / "NeedCreateView.vue").read_text(encoding="utf-8")
        prompt_source = (BACKEND / "app" / "prompts" / "need_writing.py").read_text(encoding="utf-8")
        router_source = (BACKEND / "app" / "routers" / "needs.py").read_text(encoding="utf-8")

        self.assertIn("selection_mode", need_api)
        self.assertIn("selection_mode: form.selection_mode", need_create)
        self.assertIn("人数模式", prompt_source)
        self.assertIn("_align_description_with_selection_mode", router_source)

    def test_ai_assisted_drafts_survive_page_navigation(self):
        need_create = (FRONTEND / "src" / "views" / "NeedCreateView.vue").read_text(encoding="utf-8")
        need_detail = (FRONTEND / "src" / "views" / "NeedDetailView.vue").read_text(encoding="utf-8")
        match_result = (FRONTEND / "src" / "views" / "MatchResultView.vue").read_text(encoding="utf-8")
        helper_source = (FRONTEND / "src" / "utils" / "persistentDrafts.ts").read_text(encoding="utf-8")

        self.assertIn("localStorage", helper_source)
        self.assertIn("need-create-draft", need_create)
        self.assertIn("writeDraft(draftKey", need_create)
        self.assertIn("removeDraft(draftKey", need_create)
        self.assertIn("need-application-draft", need_detail)
        self.assertIn("writeDraft(applicationDraftKey.value", need_detail)
        self.assertIn("match-message-drafts", match_result)
        self.assertIn("readDraft<Record<number, string>>", match_result)

    def test_ai_writing_uses_current_user_context(self):
        needs_router = (BACKEND / "app" / "routers" / "needs.py").read_text(encoding="utf-8")
        agent_router = (BACKEND / "app" / "routers" / "agents.py").read_text(encoding="utf-8")
        user_context = (BACKEND / "app" / "services" / "user_context.py").read_text(encoding="utf-8")
        need_detail = (FRONTEND / "src" / "views" / "NeedDetailView.vue").read_text(encoding="utf-8")

        self.assertIn("build_user_context(db, user)", needs_router)
        self.assertIn("build_user_context(db, user)", agent_router)
        self.assertIn("user_context=user_context", agent_router)
        self.assertIn("技能标签", user_context)
        self.assertIn("历史需求风格", user_context)
        self.assertIn("Applicant context", (BACKEND / "app" / "services" / "agent_planner.py").read_text(encoding="utf-8"))
        self.assertIn("authStore.user.skill_tags", need_detail)

    def test_agent_view_never_drops_first_message_when_no_session_is_active(self):
        agent_view = (FRONTEND / "src" / "views" / "AgentView.vue").read_text(encoding="utf-8")

        self.assertIn("async function ensureActiveSession", agent_view)
        self.assertIn("const sessionId = await ensureActiveSession()", agent_view)
        self.assertNotIn("if (!text || !activeSessionId.value || store.isStreaming) return", agent_view)

    def test_agent_view_recovers_from_stale_session_route_after_account_switch(self):
        agent_view = (FRONTEND / "src" / "views" / "AgentView.vue").read_text(encoding="utf-8")
        agent_store = (FRONTEND / "src" / "stores" / "agent.ts").read_text(encoding="utf-8")

        self.assertIn("async function initializeAgentRoute", agent_view)
        self.assertIn("store.sessions.some((session) => session.id === requestedSessionId)", agent_view)
        self.assertIn("await openDefaultSession()", agent_view)
        self.assertIn("return true", agent_store)
        self.assertIn("return false", agent_store)


    def test_frontend_surfaces_demo_ready_entry_points(self):
        login_view = (FRONTEND / "src" / "views" / "LoginView.vue").read_text(encoding="utf-8")
        need_plaza = (FRONTEND / "src" / "views" / "NeedPlazaView.vue").read_text(encoding="utf-8")

        self.assertIn("Hackathon Demo", login_view)
        self.assertIn("demo-account-panel", login_view)
        self.assertIn("loginAsDemo", login_view)
        self.assertIn("featuredNeed", need_plaza)
        self.assertIn("demo-flow-card", need_plaza)

    def test_frontend_layout_keeps_pages_scrollable_and_hides_debug_overlay(self):
        global_css = (FRONTEND / "src" / "styles" / "global.css").read_text(encoding="utf-8")
        layout_source = (FRONTEND / "src" / "components" / "layout" / "AppLayout.vue").read_text(encoding="utf-8")

        self.assertNotIn("body {\n  overflow: hidden;", global_css)
        self.assertIn("overflow-y: auto", layout_source)
        self.assertNotIn("debug-panel", layout_source)
        self.assertNotIn("debug-toggle", layout_source)

    def test_needs_router_supports_application_flow(self):
        source = (BACKEND / "app" / "routers" / "needs.py").read_text(encoding="utf-8")

        self.assertIn('"/{need_id}/apply"', source)
        self.assertIn('"/{need_id}/applications"', source)
        self.assertIn('"/applications/{application_id}/accept"', source)
        self.assertIn('"/applications/{application_id}/reject"', source)
        self.assertIn('"/applications/mine"', source)

    def test_frontend_exposes_need_detail_and_apply_experience(self):
        router_source = (FRONTEND / "src" / "router" / "index.ts").read_text(encoding="utf-8")
        plaza_source = (FRONTEND / "src" / "views" / "NeedPlazaView.vue").read_text(encoding="utf-8")
        detail_source = (FRONTEND / "src" / "views" / "NeedDetailView.vue").read_text(encoding="utf-8")

        self.assertIn("NeedDetail", router_source)
        self.assertIn("查看需求详情", plaza_source)
        self.assertIn("申请加入", detail_source)
        self.assertIn("收到的申请", detail_source)

    def test_agent_supports_reverse_need_discovery(self):
        intent_source = (BACKEND / "app" / "agents" / "intent_analyzer_agent.py").read_text(encoding="utf-8")
        planner_source = (BACKEND / "app" / "services" / "agent_planner.py").read_text(encoding="utf-8")
        service_source = (BACKEND / "app" / "services" / "need_discovery_service.py").read_text(encoding="utf-8")

        self.assertIn("discover_needs", intent_source)
        self.assertIn("discover_needs", planner_source)
        self.assertIn("recommend_needs_for_user", service_source)

    def test_semantic_router_skill_is_registered_for_agent_reasoning(self):
        main_source = (BACKEND / "app" / "main.py").read_text(encoding="utf-8")
        intent_source = (BACKEND / "app" / "agents" / "intent_analyzer_agent.py").read_text(encoding="utf-8")
        prompt_source = (BACKEND / "app" / "prompts" / "semantic_router.py").read_text(encoding="utf-8")

        self.assertIn("SemanticRouterSkill", main_source)
        self.assertIn('SkillRegistry.get("semantic_router")', intent_source)
        self.assertIn('name="semantic_router"', prompt_source)
        self.assertIn("next_action", prompt_source)

    def test_agent_chat_prompt_handles_platform_identity_questions(self):
        prompt_source = (BACKEND / "app" / "prompts" / "agent_intent.py").read_text(encoding="utf-8")

        self.assertIn("平台定位类问题", prompt_source)
        self.assertIn("双边协作撮合", prompt_source)
        self.assertIn("不要只罗列工具能力", prompt_source)

    def test_frontend_exposes_my_applications_entry(self):
        router_source = (FRONTEND / "src" / "router" / "index.ts").read_text(encoding="utf-8")
        layout_source = (FRONTEND / "src" / "components" / "layout" / "AppLayout.vue").read_text(encoding="utf-8")
        view_source = (FRONTEND / "src" / "views" / "MyApplicationsView.vue").read_text(encoding="utf-8")

        self.assertIn("MyApplications", router_source)
        self.assertIn("/needs/applications", router_source)
        self.assertIn("/needs/applications", layout_source)
        self.assertIn("my-applications-page", view_source)
        self.assertIn("application-status-filter", view_source)

    def test_need_manage_page_shows_published_and_selected_need_cards(self):
        api_source = (FRONTEND / "src" / "api" / "needs.ts").read_text(encoding="utf-8")
        view_source = (FRONTEND / "src" / "views" / "NeedManageView.vue").read_text(encoding="utf-8")
        router_source = (BACKEND / "app" / "routers" / "needs.py").read_text(encoding="utf-8")

        self.assertIn("getMySelectedNeeds", api_source)
        self.assertIn("/needs/selected/mine", api_source)
        self.assertIn("selectedNeeds", view_source)
        self.assertIn("published-needs-section", view_source)
        self.assertIn("selected-needs-section", view_source)
        self.assertIn("goSelectedConversation", view_source)
        self.assertIn('"/selected/mine"', router_source)

    def test_frontend_surfaces_bidirectional_comparison_and_agent_apply_jump(self):
        match_result_source = (FRONTEND / "src" / "views" / "MatchResultView.vue").read_text(encoding="utf-8")
        agent_view_source = (FRONTEND / "src" / "views" / "AgentView.vue").read_text(encoding="utf-8")

        self.assertIn("application-comparison-board", match_result_source)
        self.assertIn("applicant-column", match_result_source)
        self.assertIn("handleQuickApplyFromAgent", agent_view_source)
        self.assertIn("quick-apply-button", agent_view_source)

    def test_frontend_match_result_keeps_draft_state_keyed_by_user_id(self):
        match_result = (FRONTEND / "src" / "views" / "MatchResultView.vue").read_text(encoding="utf-8")

        self.assertIn("draftMessages.value[match.user_id]", match_result)
        self.assertNotIn("match.username as unknown as number", match_result)

    def test_match_result_can_send_ai_drafted_private_message(self):
        match_result = (FRONTEND / "src" / "views" / "MatchResultView.vue").read_text(encoding="utf-8")

        self.assertIn("* as messagesApi", match_result)
        self.assertIn("async function handleSendDraft", match_result)
        self.assertIn("messagesApi.sendMessage", match_result)
        self.assertIn("content: draft", match_result)
        self.assertIn("发送草稿", match_result)

    def test_messages_view_cleans_up_resize_listener(self):
        messages_view = (FRONTEND / "src" / "views" / "MessagesView.vue").read_text(encoding="utf-8")

        self.assertIn("window.removeEventListener('resize', onResize)", messages_view)
        self.assertIn("route.query.needId", messages_view)

    def test_agent_executor_supports_core_task_types(self):
        source = (BACKEND / "app" / "services" / "agent_executor.py").read_text(encoding="utf-8")

        for task_type in ("analyze_file", "draft_need", "publish_need", "draft_message"):
            with self.subTest(task_type=task_type):
                self.assertIn(task_type, source)

    def test_agent_router_exposes_workspace_and_memory_endpoints(self):
        source = (BACKEND / "app" / "routers" / "agents.py").read_text(encoding="utf-8")

        self.assertIn("/sessions/{session_id}/workspace", source)
        self.assertIn("/sessions/{session_id}/memory/reset", source)

    def test_frontend_agent_workspace_capabilities_are_wired(self):
        api_source = (FRONTEND / "src" / "api" / "agent.ts").read_text(encoding="utf-8")
        store_source = (FRONTEND / "src" / "stores" / "agent.ts").read_text(encoding="utf-8")
        view_source = (FRONTEND / "src" / "views" / "AgentView.vue").read_text(encoding="utf-8")
        types_source = (FRONTEND / "src" / "types" / "index.ts").read_text(encoding="utf-8")

        self.assertIn("getWorkspace", api_source)
        self.assertIn("resetMemory", api_source)
        self.assertIn("workspace", store_source)
        self.assertIn("searchKnowledge", store_source)
        self.assertIn("knowledgeResults", store_source)
        self.assertIn("知识搜索", view_source)
        self.assertIn("文件库", view_source)
        self.assertIn("记忆摘要", view_source)
        self.assertIn("export interface AgentWorkspace", types_source)
        self.assertIn("export interface AgentSuggestion", types_source)


    def test_agent_follow_up_ui_supports_quick_options_and_fixed_chat_shell(self):
        view_source = (FRONTEND / "src" / "views" / "AgentView.vue").read_text(encoding="utf-8")
        store_source = (FRONTEND / "src" / "stores" / "agent.ts").read_text(encoding="utf-8")
        api_source = (FRONTEND / "src" / "api" / "agent.ts").read_text(encoding="utf-8")
        planner_source = (BACKEND / "app" / "services" / "agent_planner.py").read_text(encoding="utf-8")

        self.assertIn("follow-up-options", view_source)
        self.assertIn("handleFollowUpOptionClick", view_source)
        self.assertIn("message_metadata", store_source)
        self.assertIn("message_metadata", api_source)
        self.assertIn("pending_drafts", planner_source)
        self.assertIn("height: calc(100vh - var(--topbar-height) - 44px)", view_source)
        self.assertIn("isPublishing", store_source)

    def test_agent_draft_cards_are_selectable_before_publish(self):
        view_source = (FRONTEND / "src" / "views" / "AgentView.vue").read_text(encoding="utf-8")
        planner_source = (BACKEND / "app" / "services" / "agent_planner.py").read_text(encoding="utf-8")

        self.assertIn("selectedDraftKeys", view_source)
        self.assertIn("toggleDraftSelection", view_source)
        self.assertIn("isDraftSelected", view_source)
        self.assertIn("确认发布选中的", view_source)
        self.assertIn("_split_selected_and_remaining_drafts", planner_source)

    def test_matching_runtime_guards_against_duplicate_jobs(self):
        needs_router = (BACKEND / "app" / "routers" / "needs.py").read_text(encoding="utf-8")
        match_engine = (BACKEND / "app" / "services" / "match_engine.py").read_text(encoding="utf-8")

        self.assertIn("schedule_matching", needs_router)
        self.assertIn("cancel_matching", needs_router)
        self.assertIn("matching_active", needs_router)
        self.assertIn("def schedule_matching", match_engine)
        self.assertIn("async def cancel_matching", match_engine)
        self.assertIn("def is_matching_active", match_engine)


class AgentBehaviorTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
        from app.core.database import Base
        import app.models.agent  # noqa: F401
        import app.models.knowledge  # noqa: F401
        import app.models.message  # noqa: F401
        import app.models.user  # noqa: F401

        self.engine = create_async_engine("sqlite+aiosqlite:///:memory:")
        async with self.engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
        self.Session = async_sessionmaker(self.engine, expire_on_commit=False)

    async def asyncTearDown(self):
        await self.engine.dispose()

    async def test_ai_client_falls_back_to_local_proxy_on_network_error(self):
        from unittest.mock import AsyncMock, patch

        import httpx
        from app.integrations.client import AIClient

        request = httpx.Request("POST", "https://api.deepseek.com/chat/completions")
        response = {
            "choices": [
                {
                    "message": {
                        "content": "ok",
                    }
                }
            ]
        }

        async def fake_post(*args, **kwargs):
            if kwargs.get("proxy_url") is None:
                raise httpx.ConnectError("direct failed", request=request)
            return response

        client = AIClient(api_key="sk-test")
        with patch.object(client, "_post_chat", new=AsyncMock(side_effect=fake_post)) as post_mock:
            result = await client.chat([{"role": "user", "content": "ping"}], max_retries=0)

        self.assertEqual(result, "ok")
        self.assertEqual(client.last_connection_path, "local_proxy")
        self.assertEqual(post_mock.await_count, 2)

    async def test_ai_client_does_not_fallback_to_proxy_on_auth_error(self):
        from unittest.mock import AsyncMock, patch

        import httpx
        from app.integrations.client import AIClient

        request = httpx.Request("POST", "https://api.deepseek.com/chat/completions")
        response = httpx.Response(401, request=request, text="bad key")

        async def fake_post(*args, **kwargs):
            raise httpx.HTTPStatusError("auth failed", request=request, response=response)

        client = AIClient(api_key="sk-test")
        with patch.object(client, "_post_chat", new=AsyncMock(side_effect=fake_post)) as post_mock:
            with self.assertRaisesRegex(RuntimeError, "API error 401"):
                await client.chat([{"role": "user", "content": "ping"}], max_retries=0)

        self.assertEqual(post_mock.await_count, 1)

    async def test_agent_fallback_answers_platform_identity_without_tool_list(self):
        from app.services.agent_planner import _fallback_chat_reply

        questions = (
            "帮我用一句话总结这个平台能做什么",
            "一句话告诉我，你的最大特色",
            "你和普通需求发布平台有什么区别",
        )
        for question in questions:
            with self.subTest(question=question):
                reply = _fallback_chat_reply(question, "")
                self.assertIn("AI", reply)
                self.assertTrue(any(token in reply for token in ("撮合", "匹配", "连接")))
                self.assertNotIn("我现在可以帮你分析文件、整理需求草稿", reply)

    async def test_conversation_previews_keep_same_user_separate_by_need(self):
        from app.models.message import Message
        from app.models.user import User
        from app.services import message_service

        async with self.Session() as db:
            alice = User(username="alice-msg", password_hash="x")
            bob = User(username="bob-msg", password_hash="x")
            db.add_all([alice, bob])
            await db.flush()
            db.add_all([
                Message(need_id=101, sender_id=alice.id, receiver_id=bob.id, content="need 101 first"),
                Message(need_id=202, sender_id=bob.id, receiver_id=alice.id, content="need 202 latest"),
            ])
            await db.commit()

            previews = await message_service.get_conversations(db, alice.id)

        self.assertEqual({item.need_id for item in previews}, {101, 202})
        self.assertTrue(all(item.other_user_id == bob.id for item in previews))

    async def test_agent_messages_return_latest_limit_in_chronological_order(self):
        from app.models.agent import AgentMessage, AgentSession
        from app.models.user import User
        from app.services import agent_service

        async with self.Session() as db:
            user = User(username="agent-user", password_hash="x")
            db.add(user)
            await db.flush()
            session = AgentSession(user_id=user.id, title="latest messages")
            db.add(session)
            await db.flush()

            base_time = datetime(2026, 5, 30, 8, 0, 0)
            for i in range(60):
                db.add(AgentMessage(
                    session_id=session.id,
                    role="user",
                    content=f"message-{i}",
                    created_at=base_time + timedelta(minutes=i),
                ))
            await db.commit()

            messages = await agent_service.get_messages(db, session.id, limit=50)

        self.assertEqual(len(messages), 50)
        self.assertEqual(messages[0].content, "message-10")
        self.assertEqual(messages[-1].content, "message-59")

    async def test_agent_memory_does_not_resummarize_already_summarized_messages(self):
        from app.models.agent import AgentMessage, AgentSession
        from app.models.user import User
        from app.services.agent_memory import ContextManager
        from app.skills.registry import SkillRegistry

        class FakeSummarizer:
            def __init__(self):
                self.calls = []

            async def execute(self, payload):
                self.calls.append([m["content"] for m in payload["messages"]])
                return {"summary": f"summary-{len(self.calls)}"}

        original_get = SkillRegistry.get
        fake = FakeSummarizer()
        SkillRegistry.get = classmethod(lambda cls, name: fake if name == "context_summarizer" else original_get(name))
        try:
            async with self.Session() as db:
                user = User(username="memory-user", password_hash="x")
                db.add(user)
                await db.flush()
                session = AgentSession(user_id=user.id, title="memory")
                db.add(session)
                await db.flush()

                base_time = datetime(2026, 5, 30, 9, 0, 0)
                for i in range(25):
                    db.add(AgentMessage(
                        session_id=session.id,
                        role="user",
                        content=f"memory-{i}",
                        created_at=base_time + timedelta(minutes=i),
                    ))
                await db.commit()
                await db.refresh(session)

                manager = ContextManager(db)
                await manager.get_chat_context(session.id)
                await manager.get_chat_context(session.id)

                await db.refresh(session)

            self.assertEqual(fake.calls, [[f"memory-{i}" for i in range(15)]])
            self.assertIn("summarized_until_message_id", session.planning_state["_memory"])
        finally:
            SkillRegistry.get = original_get

    def test_agent_router_protects_session_scoped_side_endpoints(self):
        source = (BACKEND / "app" / "routers" / "agents.py").read_text(encoding="utf-8")

        self.assertIn("ensure_session_owner", source)
        self.assertIn("await ensure_session_owner(db, session_id, user.id)", source)

    def test_agent_view_renders_messages_as_text_not_html(self):
        source = (FRONTEND / "src" / "views" / "AgentView.vue").read_text(encoding="utf-8")

        self.assertNotIn("v-html", source)
        self.assertIn("white-space: pre-wrap", source)

    def test_agent_store_keeps_task_panel_and_streaming_state_in_sync(self):
        source = (FRONTEND / "src" / "stores" / "agent.ts").read_text(encoding="utf-8")

        self.assertIn("async function refreshTasks", source)
        self.assertIn("await refreshTasks(sessionId)", source)
        self.assertIn("finally", source)
        self.assertIn("isStreaming.value = false", source)

    def test_agent_upload_can_return_publishable_drafts(self):
        backend_source = (BACKEND / "app" / "services" / "agent_planner.py").read_text(encoding="utf-8")
        frontend_source = (FRONTEND / "src" / "api" / "agent.ts").read_text(encoding="utf-8")

        self.assertIn('return {"reply": ai_msg, "file_id": agent_file.id, "extracted": extracted, "drafts": drafts}', backend_source)
        self.assertIn('draft_task = await agent_service.create_task', backend_source)
        self.assertIn("drafts?: NeedDraft[]", frontend_source)

    def test_agent_task_model_has_stage_a_columns(self):
        source = (BACKEND / "app" / "models" / "agent.py").read_text(encoding="utf-8")

        self.assertIn("task_type: Mapped", source)
        self.assertIn("input_data: Mapped", source)
        self.assertIn("error_code: Mapped", source)
        self.assertIn("retry_count: Mapped", source)
        self.assertIn("need_id: Mapped", source)
        self.assertIn("file_id: Mapped", source)

    def test_agent_service_defines_task_lifecycle_state_machine(self):
        source = (BACKEND / "app" / "services" / "agent_service.py").read_text(encoding="utf-8")

        self.assertIn("VALID_TASK_TRANSITIONS", source)
        self.assertIn("validate_transition", source)
        self.assertIn("pending", source)
        self.assertIn("waiting_user", source)

    def test_agent_service_has_task_tree_builder(self):
        source = (BACKEND / "app" / "services" / "agent_service.py").read_text(encoding="utf-8")

        self.assertIn("def build_task_tree", source)

    def test_agent_router_exposes_task_retry_endpoint(self):
        source = (BACKEND / "app" / "routers" / "agents.py").read_text(encoding="utf-8")

        self.assertIn("tasks/{task_id}/retry", source)

    def test_frontend_task_panel_shows_error_and_retry(self):
        source = (FRONTEND / "src" / "views" / "AgentView.vue").read_text(encoding="utf-8")

        self.assertIn("task-error-block", source)
        self.assertIn("task-error-code", source)
        self.assertIn("retryTask", source)
        self.assertIn("task-type-tag", source)

    def test_frontend_type_defines_task_stage_a_fields(self):
        source = (FRONTEND / "src" / "types" / "index.ts").read_text(encoding="utf-8")

        self.assertIn("task_type?: string", source)
        self.assertIn("error_code?: string", source)
        self.assertIn("retry_count: number", source)
        self.assertIn("input_data?: Record<string, unknown>", source)

    async def test_task_lifecycle_rejects_invalid_transitions(self):
        from app.services.agent_service import validate_transition

        validate_transition("pending", "running")
        validate_transition("running", "done")
        validate_transition("failed", "running")

        with self.assertRaises(ValueError):
            validate_transition("done", "running")
        with self.assertRaises(ValueError):
            validate_transition("cancelled", "running")
        with self.assertRaises(ValueError):
            validate_transition("pending", "done")

    async def test_build_task_tree_nests_children_under_parents(self):
        from app.models.agent import AgentTask
        from app.services.agent_service import build_task_tree
        from datetime import datetime

        now = datetime(2026, 5, 30, 12, 0, 0)
        parent = AgentTask(id=1, session_id=1, goal="parent", status="pending", task_type="plan", created_at=now, updated_at=now)
        child = AgentTask(id=2, session_id=1, parent_task_id=1, goal="child", status="pending", task_type="analyze_file", created_at=now, updated_at=now)
        orphan = AgentTask(id=3, session_id=1, parent_task_id=99, goal="orphan", status="pending", task_type="draft_need", created_at=now, updated_at=now)

        tree = build_task_tree([parent, child, orphan])

        self.assertEqual(len(tree), 2)
        root_node = next(n for n in tree if n["id"] == 1)
        self.assertEqual(len(root_node["children"]), 1)
        self.assertEqual(root_node["children"][0]["id"], 2)
        self.assertEqual(root_node["children"][0]["task_type"], "analyze_file")

        orphan_node = next(n for n in tree if n["id"] == 3)
        self.assertEqual(len(orphan_node["children"]), 0)

    async def test_file_upload_creates_task_with_lifecycle(self):
        source = (BACKEND / "app" / "services" / "agent_planner.py").read_text(encoding="utf-8")

        self.assertIn('task_type="analyze_file"', source)
        self.assertIn("agent_executor.execute_task", source)
        self.assertIn('draft_task = await agent_service.create_task', source)

    async def test_follow_up_state_machine_collects_missing_need_fields(self):
        from app.services.agent_planner import collect_need_follow_up, get_follow_up_question

        state = collect_need_follow_up("帮我找人一起做比赛项目", None)
        self.assertEqual(state["collected"]["description"], "帮我找人一起做比赛项目")
        self.assertEqual(state["missing_fields"][0], "type")
        self.assertIn("类型", get_follow_up_question(state))

        state = collect_need_follow_up("组队", state)
        self.assertEqual(state["collected"]["type"], "组队")
        self.assertEqual(state["missing_fields"][0], "title")

        state = collect_need_follow_up("报名参加acm", state)
        self.assertEqual(state["missing_fields"][0], "requirements")

        state = collect_need_follow_up("多人", state)
        self.assertEqual(state["collected"]["selection_mode"], "multi")
        self.assertEqual(state["missing_fields"][0], "requirements")

        state = collect_need_follow_up("需要会 C++ 和算法训练", state)
        self.assertEqual(state["collected"]["requirements"], "需要会 C++ 和算法训练")
        self.assertEqual(state["missing_fields"], [])

    async def test_agent_executor_can_build_draft_from_follow_up_state(self):
        from app.services.agent_executor import build_draft_from_follow_up_state

        draft = build_draft_from_follow_up_state({
            "type": "组队",
            "title": "黑客松前端搭子",
            "description": "需要一起完成黑客松前端和演示。",
            "requirements": "需要会 Vue、接口联调和路演展示",
            "selection_mode": "multi",
        })

        self.assertEqual(draft["type"], "组队")
        self.assertEqual(draft["title"], "黑客松前端搭子")
        self.assertEqual(draft["selection_mode"], "multi")
        self.assertIn("Vue", draft["description"])

    async def test_semantic_router_skill_routes_existing_vs_publish_needs(self):
        from app.skills.semantic_router import SemanticRouterSkill

        skill = SemanticRouterSkill()

        discover = await skill.execute({
            "message": "我想打算法比赛，帮我看看有没有这方面的组队需求",
            "user_context": "用户会 C++ 和算法",
        })
        self.assertEqual(discover["intent"], "discover_needs")
        self.assertEqual(discover["next_action"], "recommend_existing_needs")
        self.assertTrue(discover["semantic_frame"]["wants_existing"])

        publish = await skill.execute({
            "message": "帮我发布一个蓝桥杯组队需求",
            "user_context": "用户想参加比赛",
        })
        self.assertEqual(publish["intent"], "publish_need")
        self.assertEqual(publish["next_action"], "start_publish_follow_up")
        self.assertTrue(publish["semantic_frame"]["wants_create"])

    async def test_single_selection_description_alignment_removes_multi_person_phrasing(self):
        from app.routers.needs import _align_description_with_selection_mode

        text = "想找2-3个志同道合的队友一起冲大创，最好多个方向互补。"
        aligned = _align_description_with_selection_mode(text, "single")

        self.assertIn("1位", aligned)
        self.assertNotIn("2-3个", aligned)
        self.assertNotIn("多个", aligned)

    async def test_semantic_search_lazily_embeds_new_candidates_without_profile_embedding(self):
        from unittest.mock import patch

        from app.agents.semantic_search_agent import SemanticSearchAgent
        from app.models.user import User
        from app.skills.match_skill import MatchSkill

        class FakeEmbeddingSkill:
            async def execute(self, input_data: dict) -> dict:
                return {"embedding": [1.0, 0.0]}

        def fake_get_skill(name: str):
            if name == "embedding":
                return FakeEmbeddingSkill()
            if name == "vector_match":
                return MatchSkill()
            raise KeyError(name)

        async with self.Session() as db:
            candidate = User(
                username="fresh-candidate",
                password_hash="x",
                bio="Vue 前端和路演页面",
                skill_tags=["Vue", "前端", "路演"],
                profile_embedding=None,
            )
            db.add(candidate)
            await db.commit()
            candidate_id = candidate.id

            with patch("app.skills.registry.SkillRegistry.get", side_effect=fake_get_skill), patch(
                "app.knowledge.match_memory.MatchMemoryStore.retrieve_similar",
                return_value=[],
            ):
                result = await SemanticSearchAgent().execute({
                    "embedding": [1.0, 0.0],
                    "tags": ["Vue", "前端"],
                    "db": db,
                    "exclude_user_id": 999,
                })

            self.assertTrue(any(item["id"] == candidate_id for item in result["candidates"]), result)
            await db.refresh(candidate)
            self.assertEqual(candidate.profile_embedding, [1.0, 0.0])


if __name__ == "__main__":
    unittest.main()
