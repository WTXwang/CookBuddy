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
          Renderer.renderResult(container, msg.data);
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

  _saveConversations() {
    // 只保存最近 50 条对话，每条最多存 20 条消息
    const toSave = this.conversations.slice(0, 50).map(c => ({
      ...c,
      messages: (c.messages || []).slice(-20)
    }));
    try {
      localStorage.setItem('chef_conversations', JSON.stringify(toSave));
    } catch (e) {
      // localStorage 满了就清掉旧的
      const half = toSave.slice(0, 25);
      localStorage.setItem('chef_conversations', JSON.stringify(half));
    }
  },

  _loadConversations() {
    try {
      const raw = localStorage.getItem('chef_conversations');
      if (raw) this.conversations = JSON.parse(raw);
    } catch (e) {
      this.conversations = [];
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

    // 渲染用户消息
    Renderer.clear();
    Renderer.addUserMessage(text, tags);

    // 记录到对话
    if (conv) {
      conv.messages.push({ role: 'user', text, tags });
    }

    const aiContainer = Renderer.addAIMessage();
    Renderer.createLoadingBox(aiContainer);

    mockRecommend(
      text,
      constraints,
      (stageIndex, stage) => Renderer.updateStage(stageIndex, stage),
      (percent) => Renderer.updateProgress(percent)
    ).then(data => {
      this._onSuccess(aiContainer, data);
      // 记录 AI 回复
      if (conv) {
        conv.messages.push({ role: 'ai', data });
        this._saveConversations();
        this._renderHistory();  // 更新标题
      }
    }).catch(err => {
      this._onError(aiContainer, err.message);
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
    Renderer.removeLoading();
    if (!data.recommendations || data.recommendations.length === 0) {
      Renderer.renderNoResult(container, data.follow_up_question);
    } else {
      Renderer.renderResult(container, data);
    }
  },

  _onError(container, message) {
    this.state = 'done';
    this.sendBtn.disabled = false;
    Renderer.removeLoading();
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
