export interface User {
  id: number
  username: string
  avatar?: string
  bio?: string
  skill_tags?: string[]
  school?: string
  extra?: Record<string, unknown> | string
  rating_score: number
  created_at: string
}

export interface Need {
  id: number
  user_id: number
  username: string
  type: string
  title: string
  description: string
  req_tags?: string[]
  selection_mode: 'single' | 'multi'
  selected_user_ids?: number[]
  status: string
  application_count?: number
  can_apply?: boolean | null
  my_application_status?: string | null
  created_at: string
}

export interface NeedApplication {
  id: number
  need_id: number
  applicant_user_id: number
  owner_user_id?: number | null
  applicant_username: string
  applicant_skill_tags?: string[] | null
  message: string
  status: 'pending' | 'accepted' | 'rejected' | 'withdrawn'
  owner_reply?: string | null
  owner_username?: string | null
  need_title?: string | null
  need_status?: string | null
  created_at: string
  updated_at: string
}

export interface NeedRecommendation {
  need_id: number
  title: string
  type: string
  owner_id: number
  owner_name: string
  selection_mode: 'single' | 'multi'
  req_tags?: string[]
  score: number
  reason: string
}

export interface AgentSession {
  id: number
  user_id: number
  title: string
  summary?: string
  planning_state?: Record<string, unknown>
  status: string
  created_at: string
  updated_at: string
}

export interface AgentMessage {
  id: number
  session_id: number
  role: string
  content: string
  token_count?: number
  extra_metadata?: Record<string, unknown>
  created_at: string
}

export interface AgentQuickOption {
  label: string
  value: string
}

export interface AgentSuggestion {
  id: string
  text: string
  action_type: 'prefill' | 'navigate' | 'refresh_tasks'
  payload?: Record<string, unknown>
}

export interface AgentTask {
  id: number
  session_id: number
  parent_task_id?: number
  task_type?: string
  goal: string
  status: string
  assigned_agent?: string
  input_data?: Record<string, unknown>
  result?: Record<string, unknown>
  error?: string
  error_code?: string
  retry_count: number
  need_id?: number
  match_id?: number
  file_id?: number
  children?: AgentTask[]
  created_at: string
  updated_at?: string
}

export interface NeedDraft {
  type: string
  title: string
  description: string
  selection_mode?: string
}

export interface AgentWorkspaceFile {
  id: number
  filename: string
  file_type: string
  extracted_info?: Record<string, unknown>
  created_at: string
}

export interface AgentWorkspace {
  memory: {
    summary?: string
    follow_up?: Record<string, unknown> | null
  }
  files: AgentWorkspaceFile[]
}

export interface AgentChatResponse {
  reply: string
  intent?: string
  drafts?: NeedDraft[]
  need_recommendations?: NeedRecommendation[]
  needs?: { id: number; title: string; type: string }[]
  message_role?: string
  message_metadata?: Record<string, unknown> | null
}

export interface MatchResult {
  user_id: number
  score: number
  reason: string
  complementarity?: string
  username: string
  school: string
  bio?: string
  extra?: Record<string, unknown>
  skill_tags: string[]
}

export interface MatchProgress {
  stage: 'tag_extraction' | 'semantic_search' | 'rerank' | 'done' | 'error'
  message: string
  data?: Record<string, unknown>
}

export interface MessageItem {
  id: number
  need_id: number
  sender_id: number
  receiver_id: number
  content: string
  created_at: string
}

export interface ConversationPreview {
  other_user_id: number
  other_username: string
  need_id: number
  last_message: string
  last_time: string
}

export interface TokenResponse {
  access_token: string
  token_type: string
  user: User
}
