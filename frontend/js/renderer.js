/* ============================================
   今晚吃什么 — 渲染器
   负责 DOM 创建、动画控制、卡片渲染
   ============================================ */

const Renderer = {

  messagesEl: document.getElementById('messages'),
  emptyStateEl: document.getElementById('emptyState'),
  chatAreaEl: document.getElementById('chatArea'),
  cardTemplate: document.getElementById('recipeCardTemplate'),

  /* ======== 消息管理 ======== */

  /** 清空所有消息，隐藏空状态 */
  clear() {
    this.messagesEl.innerHTML = '';
    this.emptyStateEl.style.display = 'none';
  },

  /** 添加用户消息气泡 */
  addUserMessage(text, tags) {
    const div = document.createElement('div');
    div.className = 'message msg-user';
    div.innerHTML = `<div>${this._esc(text)}</div>`;
    if (tags && tags.length) {
      const tagHtml = tags.map(t => `<span class="user-tag">${this._esc(t)}</span>`).join('');
      div.innerHTML += `<div class="user-tags">${tagHtml}</div>`;
    }
    this.messagesEl.appendChild(div);
    this._scrollBottom();
  },

  /** 添加 AI 消息容器，返回该容器 DOM */
  addAIMessage() {
    const div = document.createElement('div');
    div.className = 'message msg-ai';
    div.id = 'currentAI';
    this.messagesEl.appendChild(div);
    this._scrollBottom();
    return div;
  },

  /* ======== 加载动画 ======== */

  /** 在容器中创建加载动画 */
  createLoadingBox(container) {
    const box = document.createElement('div');
    box.className = 'loading-box';
    box.id = 'loadingBox';
    box.innerHTML = `
      <div class="chef-animation">
        <div class="chef-body">🧑‍🍳</div>
        <div class="chef-pan">🍳</div>
        <div class="chef-spatula">🥄</div>
        <div class="steam-container">
          <span class="steam">💨</span>
          <span class="steam">💨</span>
          <span class="steam">💨</span>
        </div>
        <span class="spark">✨</span>
        <span class="spark">✨</span>
        <span class="spark">✨</span>
      </div>
      <div class="chef-text" id="chefText">
        <span id="chefStageIcon">🥚🔪</span>
        <span id="chefStageText">正在整理食材</span>
        <span class="dot-anim"></span>
      </div>
      <div class="progress-bar">
        <div class="progress-fill active" id="progressFill" style="width:0%"></div>
      </div>
    `;
    container.appendChild(box);
    this._scrollBottom();
  },

  /** 更新加载动画的阶段 */
  updateStage(stageIndex, stage) {
    const iconEl = document.getElementById('chefStageIcon');
    const textEl = document.getElementById('chefStageText');
    const progressEl = document.getElementById('progressFill');
    if (iconEl) iconEl.textContent = stage.icon;
    if (textEl) {
      textEl.textContent = stage.text;
      textEl.style.animation = 'none';
      textEl.offsetHeight; // reflow
      textEl.style.animation = '';
    }
  },

  /** 更新进度条 */
  updateProgress(percent) {
    const bar = document.getElementById('progressFill');
    if (bar) bar.style.width = percent + '%';
  },

  /** 移除加载动画 */
  removeLoading() {
    const box = document.getElementById('loadingBox');
    if (box) box.remove();
  },

  /* ======== 结果渲染 ======== */

  /** 渲染完整推荐结果 */
  renderResult(container, data) {
    const summary = data.request_summary;
    const ingNames = (summary && summary.ingredients)
      ? summary.ingredients.map(i => i.name || i).join('、')
      : '未知食材';
    const recCount = (data.recommendations && data.recommendations.length) || 0;

    // 结果统计头
    const header = document.createElement('div');
    header.className = 'result-header';
    header.innerHTML = `找到 <strong>${recCount}</strong> 道菜，基于你的食材：<span class="ing-badge">${this._esc(ingNames)}</span>`;
    container.appendChild(header);

    // 菜谱卡片
    data.recommendations.forEach((r, i) => {
      const card = this.createRecipeCard(r, i);
      container.appendChild(card);
    });

    // 追问
    if (data.follow_up_question) {
      const fq = document.createElement('p');
      fq.style.cssText = 'font-size:14px;color:#78716c;margin-top:12px;text-align:center;';
      fq.textContent = '💡 ' + data.follow_up_question;
      container.appendChild(fq);
    }

    // 拦截信息
    if (data.blocked_recipes && data.blocked_recipes.length) {
      const blocked = document.createElement('div');
      blocked.style.cssText = 'margin-top:12px;padding:10px 14px;background:#fef2f2;border-radius:10px;font-size:13px;color:#b91c1c;';
      data.blocked_recipes.forEach(b => {
        blocked.innerHTML += `<div>🚫 <strong>${this._esc(b.title)}</strong>：${this._esc(b.block_reason)}</div>`;
      });
      container.appendChild(blocked);
    }

    // 撒花
    this._confetti(container);
    this._scrollBottom();
  },

  /** 无结果状态 */
  renderNoResult(container, text) {
    const box = document.createElement('div');
    box.className = 'status-box';
    box.innerHTML = `
      <div class="status-icon">🤷‍♂️</div>
      <div class="status-title">没找到合适的菜</div>
      <div class="status-desc">${this._esc(text || '试试放宽时间、减少限制条件，或者补充一些食材？')}</div>
    `;
    container.appendChild(box);
    this._scrollBottom();
  },

  /** 聊天回复气泡 */
  renderChatReply(container, text) {
    const bubble = document.createElement('div');
    bubble.className = 'chat-bubble';
    bubble.innerHTML = `<span class="chat-bubble-icon">🍳</span><span>${this._esc(text)}</span>`;
    container.appendChild(bubble);
    this._scrollBottom();
  },

  /** 错误状态 */
  renderError(container, message) {
    const box = document.createElement('div');
    box.className = 'status-box error';
    box.innerHTML = `
      <div class="status-icon">🔥</div>
      <div class="status-title">锅烧糊了！</div>
      <div class="status-desc">${this._esc(message || '服务出了点问题，请稍后再试')}</div>
      <button class="retry-btn" onclick="App.retry()">🔄 重试</button>
    `;
    container.appendChild(box);
    this._scrollBottom();
  },

  /* ======== 单张菜谱卡片 ======== */

  createRecipeCard(recipe, index) {
    const tmpl = this.cardTemplate.content.cloneNode(true);
    const card = tmpl.querySelector('.recipe-card');

    // 图片
    const img = card.querySelector('.card-img');
    if (recipe.image_url) {
      img.src = recipe.image_url;
      img.alt = recipe.title;
      img.onload = () => img.classList.add('loaded');
      img.onerror = () => { /* 保持占位 */ };
    }

    // 匹配分标签
    const badge = card.querySelector('.card-match-badge');
    badge.textContent = recipe.match_label || (recipe.match_score + '分');
    if (recipe.match_score < 80) badge.classList.add('warn');

    // 标题
    card.querySelector('.card-title').textContent = recipe.title;

    // 元信息
    card.querySelector('.meta-time').textContent   = '⏱ ' + recipe.estimated_time_min + '分钟';
    card.querySelector('.meta-diff').textContent   = '📊 ' + recipe.difficulty;
    card.querySelector('.meta-servings').textContent = '👥 ' + (recipe.servings || 2) + '人';

    // 已用食材
    const usedTags = card.querySelector('.ingredient-tags.used');
    recipe.used_ingredients.forEach(ing => {
      const span = document.createElement('span');
      span.className = 'ing-tag';
      span.textContent = '✅ ' + ing;
      usedTags.appendChild(span);
    });

    // 缺失食材
    const missingTags = card.querySelector('.ingredient-tags.missing');
    recipe.missing_core.forEach(ing => {
      const span = document.createElement('span');
      span.className = 'ing-tag';
      span.textContent = '❌ ' + ing;
      missingTags.appendChild(span);
    });
    recipe.missing_optional.forEach(ing => {
      const span = document.createElement('span');
      span.className = 'ing-tag optional';
      span.textContent = '➕ ' + ing + '（可选）';
      missingTags.appendChild(span);
    });

    // 推荐理由
    card.querySelector('.card-reason').textContent = '💬 ' + recipe.reason;

    // 准备
    const prepDiv = card.querySelector('.card-prep');
    if (recipe.prep && recipe.prep.length) {
      prepDiv.innerHTML = '<h4>🥬 准备工作</h4><ul>' +
        recipe.prep.map(p => `<li>${this._esc(p)}</li>`).join('') + '</ul>';
    }

    // 步骤
    const stepsOl = card.querySelector('.card-steps');
    recipe.steps.forEach((step, i) => {
      const li = document.createElement('li');
      li.textContent = step;
      stepsOl.appendChild(li);
    });
    // 火候提示
    if (recipe.heat_tips) {
      const tip = document.createElement('li');
      tip.style.cssText = 'color:#f97316;font-weight:600;list-style:"🔥 ";';
      tip.textContent = recipe.heat_tips;
      stepsOl.appendChild(tip);
    }

    // 替代建议
    if (recipe.substitutions && recipe.substitutions.length) {
      const subP = document.createElement('p');
      subP.style.cssText = 'font-size:13px;color:#78716c;margin-top:8px;';
      subP.textContent = '💡 ' + recipe.substitutions.join('；');
      card.querySelector('.card-details').appendChild(subP);
    }

    // 安全提醒
    const safetyDiv = card.querySelector('.card-safety');
    if (recipe.safety_notes && recipe.safety_notes.length) {
      safetyDiv.innerHTML = '<h4>⚠️ 安全提醒</h4><ul>' +
        recipe.safety_notes.map(n => `<li>${this._esc(n)}</li>`).join('') + '</ul>';
    }

    return card;
  },

  /* ======== 辅助 ======== */

  buildUserTags(constraints) {
    const tags = [];
    if (constraints.servings && constraints.servings !== 2) tags.push(constraints.servings + '人');
    if (constraints.time_limit_min) tags.push(constraints.time_limit_min + '分钟');
    if (constraints.difficulty && constraints.difficulty !== '任意') tags.push(constraints.difficulty);
    if (constraints.flavor && constraints.flavor !== '不限') tags.push(constraints.flavor);
    return tags;
  },

  _esc(s) {
    if (!s) return '';
    const div = document.createElement('div');
    div.textContent = s;
    return div.innerHTML;
  },

  _scrollBottom() {
    setTimeout(() => {
      this.chatAreaEl.scrollTop = this.chatAreaEl.scrollHeight;
    }, 100);
  },

  _confetti(container) {
    const emojis = ['🎉', '✨', '🍳', '🥘', '🍽️', '👨‍🍳', '💯', '🌟'];
    for (let i = 0; i < 8; i++) {
      const el = document.createElement('span');
      el.className = 'confetti';
      el.textContent = emojis[i];
      el.style.left = (10 + i * 10) + '%';
      el.style.animationDelay = (i * 0.12) + 's';
      container.appendChild(el);
      setTimeout(() => el.remove(), 2200);
    }
  }
};
