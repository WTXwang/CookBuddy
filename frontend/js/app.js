/* ============================================
   今晚吃什么 — 主逻辑（侧边栏 + 历史记录）
   ============================================ */

const App = {

  state: 'idle',
  lastInput: null,
  lastConstraints: null,

  // 对话历史
  conversations: [],       // { id, title, messages: [], createdAt }
  currentConvId: null,

  // DOM
  inputEl: document.getElementById('ingredientInput'),
  sendBtn: document.getElementById('sendBtn'),
  messagesEl: document.getElementById('messages'),
  emptyStateEl: document.getElementById('emptyState'),
  chatAreaEl: document.getElementById('chatArea'),
  sidebarEl: document.getElementById('sidebar'),
  sidebarOverlay: document.getElementById('sidebarOverlay'),
  historyListEl: document.getElementById('historyList'),

  /* ======== 初始化 ======== */
  init() {
    // 初始化 Auth（登录状态）
    Auth.init();

    this._loadConversations();
    this._renderHistory();

    // 如果没有历史对话，创建一个空的
    if (this.conversations.length === 0) {
      this._newConversation();
    } else {
      this._loadConversation(this.conversations[0].id);
    }

    // 事件绑定
    this.sendBtn.addEventListener('click', () => this.submit());
    this.inputEl.addEventListener('keydown', (e) => {
      if (e.key === 'Enter' && !e.shiftKey) {
        e.preventDefault();
        this.submit();
      }
    });
    this.inputEl.addEventListener('input', () => {
      this.inputEl.style.height = 'auto';
      this.inputEl.style.height = Math.min(this.inputEl.scrollHeight, 120) + 'px';
    });

    // Chip 选择（同 key 互斥）
    document.querySelector('.constraint-scroll').addEventListener('click', (e) => {
      const chip = e.target.closest('.chip');
      if (!chip) return;
      const key = chip.dataset.key;
      document.querySelectorAll(`.chip[data-key="${key}"]`).forEach(c => c.classList.remove('active'));
      chip.classList.add('active');
    });

    // 示例卡片
    document.querySelectorAll('.example-card').forEach(card => {
      card.addEventListener('click', () => {
        this.inputEl.value = card.dataset.example;
        this.submit();
      });
    });

    // 新对话
    document.getElementById('newChatBtn').addEventListener('click', () => this._newConversation());

    // 清空历史
    document.getElementById('clearHistoryBtn').addEventListener('click', () => {
      if (!confirm('确定要清空所有对话记录吗？此操作不可撤销。')) return;
      localStorage.removeItem(this._getStorageKey());
      this.conversations = [];
      this._newConversation();
      this._renderHistory();
    });

    // 侧边栏切换
    document.getElementById('sidebarToggle').addEventListener('click', () => this._toggleSidebar());
    document.getElementById('sidebarExpandBtn').addEventListener('click', () => this._expandSidebar());
    document.getElementById('menuBtn').addEventListener('click', () => this._openSidebar());
    this.sidebarOverlay.addEventListener('click', () => this._closeSidebar());

    // 窗口变大时关闭移动端侧边栏
    window.addEventListener('resize', () => {
      if (window.innerWidth > 768) {
        this._closeSidebar();
      }
    });
  },

  /* ======== 对话管理 ======== */
  _newConversation() {
    this.currentConvId = 'conv_' + Date.now();
    const conv = {
      id: this.currentConvId,
      title: '新对话',
      messages: [],    // 存储消息的序列化数据
      createdAt: Date.now()
    };
    this.conversations.unshift(conv);
    this._saveConversations();
    this._renderHistory();
    this._clearChat();
    this._closeSidebar();
  },

  _loadConversation(id) {
    const conv = this.conversations.find(c => c.id === id);
    if (!conv) return;
    this.currentConvId = id;
    this._renderHistory();
    this._clearChat();

    // 还原消息
    if (conv.messages && conv.messages.length > 0) {
      this.emptyStateEl.style.display = 'none';
      conv.messages.forEach(msg => {
        if (msg.role === 'user') {
          Renderer.addUserMessage(msg.text, msg.tags);
        } else if (msg.role === 'ai' && msg.data) {
          const container = Renderer.addAIMessage();
          // 区分闲聊和推荐：chat 回复没有 request_summary
          if (msg.data.intent === 'chat' && msg.data.reply) {
            Renderer.renderNoResult(container, msg.data.reply);
          } else if (msg.data.request_summary) {
            Renderer.renderResult(container, msg.data);
          } else {
            Renderer.renderNoResult(container, '历史记录格式已过期');
          }
        }
      });
      this._scrollBottom();
    }
    this._closeSidebar();
  },

  _deleteConversation(id) {
    this.conversations = this.conversations.filter(c => c.id !== id);
    this._saveConversations();
    if (this.currentConvId === id) {
      if (this.conversations.length > 0) {
        this._loadConversation(this.conversations[0].id);
      } else {
        this._newConversation();
      }
    } else {
      this._renderHistory();
    }
  },

  _getStorageKey() {
    const user = Auth.getUsername();
    return user ? 'chef_conv_' + user : 'chef_conversations';
  },

  _saveConversations() {
    const toSave = this.conversations.slice(0, 50).map(c => ({
      ...c,
      messages: (c.messages || []).slice(-20)
    }));
    try {
      localStorage.setItem(this._getStorageKey(), JSON.stringify(toSave));
    } catch (e) {
      const half = toSave.slice(0, 25);
      localStorage.setItem(this._getStorageKey(), JSON.stringify(half));
    }
  },

  _loadConversations() {
    try {
      const raw = localStorage.getItem(this._getStorageKey());
      if (raw) this.conversations = JSON.parse(raw);
    } catch (e) {
      this.conversations = [];
    }
  },

  /** 登录后重载该用户的对话 */
  _onLogin(username) {
    this._loadConversations();
    this._renderHistory();
    if (this.conversations.length > 0) {
      this._loadConversation(this.conversations[0].id);
    } else {
      this._newConversation();
    }
  },

  /** 登出后回到匿名对话 */
  _onLogout() {
    this._loadConversations();
    this._renderHistory();
    if (this.conversations.length > 0) {
      this._loadConversation(this.conversations[0].id);
    } else {
      this._newConversation();
    }
  },

  _renderHistory() {
    const list = this.historyListEl;
    list.innerHTML = '';

    this.conversations.forEach(conv => {
      const item = document.createElement('div');
      item.className = 'history-item' + (conv.id === this.currentConvId ? ' active' : '');
      item.innerHTML = `
        <span class="history-item-icon">💬</span>
        <span class="history-item-text">${Renderer._esc(conv.title)}</span>
      `;
      item.title = conv.title;

      // 点击加载
      item.addEventListener('click', (e) => {
        // 右键删除
        if (e.button === 2) {
          e.preventDefault();
          if (confirm('删除这个对话？')) this._deleteConversation(conv.id);
          return;
        }
        this._loadConversation(conv.id);
      });
      item.addEventListener('contextmenu', (e) => {
        e.preventDefault();
        if (confirm('删除这个对话？')) this._deleteConversation(conv.id);
      });

      list.appendChild(item);
    });
  },

  _clearChat() {
    this.messagesEl.innerHTML = '';
    this.emptyStateEl.style.display = '';
    this.state = 'idle';
    this.lastInput = null;
    this.lastConstraints = null;
    this.inputEl.value = '';
    this.inputEl.style.height = '';
    this.inputEl.focus();
  },

  /* ======== 侧边栏 ======== */
  _toggleSidebar() {
    if (window.innerWidth <= 768) {
      this.sidebarEl.classList.contains('open') ? this._closeSidebar() : this._openSidebar();
    } else {
      this.sidebarEl.classList.toggle('collapsed');
    }
  },
  _openSidebar() {
    this.sidebarEl.classList.add('open');
    this.sidebarEl.classList.remove('collapsed');
    this.sidebarOverlay.classList.add('show');
  },
  _expandSidebar() {
    this.sidebarEl.classList.remove('collapsed');
  },
  _closeSidebar() {
    this.sidebarEl.classList.remove('open');
    this.sidebarOverlay.classList.remove('show');
  },

  /* ======== 提交 ======== */
  submit() {
    const text = this.inputEl.value.trim();
    if (!text || this.state === 'loading') return;

    this.state = 'loading';
    this.sendBtn.disabled = true;

    const constraints = this._readConstraints();
    this.lastInput = text;
    this.lastConstraints = constraints;

    // 更新对话标题（用第一条用户输入）
    const conv = this.conversations.find(c => c.id === this.currentConvId);
    if (conv && conv.title === '新对话') {
      conv.title = text.length > 30 ? text.slice(0, 30) + '...' : text;
    }

    const tags = Renderer.buildUserTags(constraints);
    if (constraints.allergens && constraints.allergens.length) {
      tags.push('过敏: ' + constraints.allergens.join('、'));
    }
    if (constraints.excluded && constraints.excluded.length) {
      tags.push('忌口: ' + constraints.excluded.join('、'));
    }

    // 渲染用户消息（不清理历史）
    Renderer.emptyStateEl.style.display = 'none';
    Renderer.addUserMessage(text, tags);

    // 记录到对话
    if (conv) {
      conv.messages.push({ role: 'user', text, tags });
    }

    const aiContainer = Renderer.addAIMessage();
    Renderer.createLoadingBox(aiContainer);

    // 进度条模拟动画 —— 真实 API 路径不会收到阶段回调，用定时器推进
    const stages = typeof STAGES !== 'undefined' ? STAGES : [
      { icon: '🥚🔪', text: '正在整理食材' },
      { icon: '📖🔍', text: '正在翻找菜谱' },
      { icon: '🧪✨', text: '正在匹配搭配' },
      { icon: '🍳🔥', text: '正在烹饪做法' },
      { icon: '🔒✅', text: '正在安全检查' }
    ];
    let stageIdx = 0;
    this._progressTimer = setInterval(() => {
      if (stageIdx < stages.length) {
        Renderer.updateStage(stageIdx, stages[stageIdx]);
        const pct = Math.round(((stageIdx + 1) / (stages.length + 1)) * 90);
        Renderer.updateProgress(pct);
        stageIdx++;
      } else {
        clearInterval(this._progressTimer);
        this._progressTimer = null;
      }
    }, 1500);

    const apiUrl = (window.API_BASE || 'http://localhost:8001') + '/api/recommend';

    fetch(apiUrl, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        ingredients_text: text,
        servings: constraints.servings,
        time_limit_min: constraints.time_limit_min,
        difficulty: constraints.difficulty,
        flavor: constraints.flavor,
        excluded: constraints.excluded,
        allergens: constraints.allergens,
        equipment: constraints.equipment,
        conversation_context: conv ? (conv.conversationContext || '') : '',
      }),
    })
      .then(res => {
        if (!res.ok) return res.json().then(e => { throw new Error(e.detail || '服务器错误'); });
        return res.json();
      })
      .then(data => {
        if (data.intent === 'chat' && data.reply) {
          this._onChatReply(aiContainer, data.reply);
        } else {
          this._onSuccess(aiContainer, data);
        }
        if (conv) {
          conv.messages.push({ role: 'ai', data });
          if (data.conversation_context) {
            conv.conversationContext = data.conversation_context;
          }
          this._saveConversations();
          this._renderHistory();
        }
      })
      .catch(err => {
        this._onError(aiContainer, err.message || '请求失败，请检查后端是否启动');
      });
  },

  retry() {
    if (!this.lastInput) return;
    this.inputEl.value = this.lastInput;
    this.submit();
  },

  _onSuccess(container, data) {
    this.state = 'done';
    this.sendBtn.disabled = false;
    if (this._progressTimer) { clearInterval(this._progressTimer); this._progressTimer = null; }
    Renderer.updateProgress(100);
    setTimeout(() => Renderer.removeLoading(), 300);
    if (!data.recommendations || data.recommendations.length === 0) {
      Renderer.renderNoResult(container, data.follow_up_question);
    } else {
      Renderer.renderResult(container, data);
    }
  },

  _onChatReply(container, text) {
    this.state = 'done';
    this.sendBtn.disabled = false;
    if (this._progressTimer) { clearInterval(this._progressTimer); this._progressTimer = null; }
    Renderer.updateProgress(100);
    setTimeout(() => Renderer.removeLoading(), 300);
    Renderer.renderChatReply(container, text);
  },

  _onError(container, message) {
    this.state = 'done';
    this.sendBtn.disabled = false;
    if (this._progressTimer) { clearInterval(this._progressTimer); this._progressTimer = null; }
    Renderer.updateProgress(100);
    setTimeout(() => Renderer.removeLoading(), 300);
    Renderer.renderError(container, message);
  },

  /* ======== 约束读取 ======== */
  _readConstraints() {
    const constraints = {
      servings: 2,
      time_limit_min: 20,
      difficulty: '简单',
      flavor: '',
      excluded: [],
      allergens: [],
      equipment: []
    };
    document.querySelectorAll('.chip.active').forEach(chip => {
      const key = chip.dataset.key;
      const val = chip.dataset.val;
      if (key === 'servings' || key === 'time_limit_min') {
        constraints[key] = parseInt(val);
      } else if (key === 'flavor') {
        constraints.flavor = val;
      } else if (key === 'difficulty') {
        constraints.difficulty = val;
      }
    });
    const excludedRaw = document.getElementById('excludedInput').value.trim();
    if (excludedRaw) constraints.excluded = excludedRaw.split(/[,，、\s]+/).filter(Boolean);
    const allergenRaw = document.getElementById('allergenInput').value.trim();
    if (allergenRaw) constraints.allergens = allergenRaw.split(/[,，、\s]+/).filter(Boolean);
    const equipRaw = document.getElementById('equipmentInput').value.trim();
    if (equipRaw) constraints.equipment = equipRaw.split(/[,，、\s]+/).filter(Boolean);
    return constraints;
  },

  _scrollBottom() {
    setTimeout(() => {
      this.chatAreaEl.scrollTop = this.chatAreaEl.scrollHeight;
    }, 100);
  }
};

document.addEventListener('DOMContentLoaded', () => App.init());
