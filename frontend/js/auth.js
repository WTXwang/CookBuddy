/* ============================================
   今晚吃什么 — 登录/注册（localStorage Mock）
   ============================================ */

const Auth = {

  currentUser: null,   // { username } or null

  /* ======== 初始化 ======== */
  init() {
    // 恢复 session
    const saved = localStorage.getItem('chef_current_user');
    if (saved) {
      try { this.currentUser = JSON.parse(saved); } catch (e) { this.currentUser = null; }
    }
    this._updateUI();

    // 事件
    document.getElementById('loginBtn').addEventListener('click', () => this.openModal());
    document.getElementById('authModalClose').addEventListener('click', () => this.closeModal());
    document.getElementById('authModal').addEventListener('click', (e) => {
      if (e.target === e.currentTarget) this.closeModal();
    });

    // Tab 切换
    document.querySelectorAll('.auth-tab').forEach(tab => {
      tab.addEventListener('click', () => this._switchTab(tab.dataset.tab));
    });

    // 登录提交
    document.getElementById('loginForm').addEventListener('submit', (e) => {
      e.preventDefault();
      this._login();
    });

    // 注册提交
    document.getElementById('registerForm').addEventListener('submit', (e) => {
      e.preventDefault();
      this._register();
    });
  },

  /* ======== API ======== */
  isLoggedIn() {
    return !!this.currentUser;
  },

  getUsername() {
    return this.currentUser ? this.currentUser.username : null;
  },

  logout() {
    this.currentUser = null;
    localStorage.removeItem('chef_current_user');
    this._updateUI();
    if (typeof App !== 'undefined' && App._onLogout) {
      App._onLogout();
    }
  },

  /* ======== Modal ======== */
  openModal() {
    if (this.isLoggedIn()) {
      if (confirm('确定要退出登录吗？')) this.logout();
      return;
    }
    document.getElementById('authModal').classList.add('show');
    this._switchTab('login');
    document.getElementById('loginForm').reset();
    document.getElementById('registerForm').reset();
  },

  closeModal() {
    document.getElementById('authModal').classList.remove('show');
  },

  /* ======== Internal ======== */
  _switchTab(tab) {
    document.querySelectorAll('.auth-tab').forEach(t => t.classList.remove('active'));
    document.querySelector(`.auth-tab[data-tab="${tab}"]`).classList.add('active');
    document.getElementById('loginForm').classList.toggle('hidden', tab !== 'login');
    document.getElementById('registerForm').classList.toggle('hidden', tab !== 'register');
    document.getElementById('loginError').textContent = '';
    document.getElementById('registerError').textContent = '';
  },

  _getUsers() {
    try {
      return JSON.parse(localStorage.getItem('chef_users') || '{}');
    } catch (e) { return {}; }
  },

  _saveUsers(users) {
    localStorage.setItem('chef_users', JSON.stringify(users));
  },

  _login() {
    const form = document.getElementById('loginForm');
    const username = form.loginUser.value.trim();
    const password = form.loginPass.value;
    const errorEl = document.getElementById('loginError');

    if (!username || !password) {
      errorEl.textContent = '请填写用户名和密码';
      return;
    }

    const users = this._getUsers();
    if (!users[username]) {
      errorEl.textContent = '用户不存在，请先注册';
      return;
    }
    if (users[username] !== password) {
      errorEl.textContent = '密码错误';
      return;
    }

    // 登录成功
    this.currentUser = { username };
    localStorage.setItem('chef_current_user', JSON.stringify(this.currentUser));
    this._updateUI();
    this.closeModal();

    // 同步用户对话
    if (typeof App !== 'undefined' && App._onLogin) {
      App._onLogin(username);
    }
  },

  _register() {
    const form = document.getElementById('registerForm');
    const username = form.regUser.value.trim();
    const password = form.regPass.value;
    const password2 = form.regPass2.value;
    const errorEl = document.getElementById('registerError');

    if (!username || !password) {
      errorEl.textContent = '请填写用户名和密码';
      return;
    }
    if (username.length < 2) {
      errorEl.textContent = '用户名至少2个字符';
      return;
    }
    if (password.length < 6) {
      errorEl.textContent = '密码至少6位';
      return;
    }
    if (password !== password2) {
      errorEl.textContent = '两次密码不一致';
      return;
    }

    const users = this._getUsers();
    if (users[username]) {
      errorEl.textContent = '用户名已存在，请直接登录';
      return;
    }

    // 注册成功
    users[username] = password;
    this._saveUsers(users);
    this.currentUser = { username };
    localStorage.setItem('chef_current_user', JSON.stringify(this.currentUser));
    this._updateUI();
    this.closeModal();

    // 同步用户对话
    if (typeof App !== 'undefined' && App._onLogin) {
      App._onLogin(username);
    }
  },

  _updateUI() {
    const btn = document.getElementById('loginBtn');
    if (!btn) return;
    if (this.isLoggedIn()) {
      btn.classList.add('logged-in');
      btn.querySelector('.login-btn-icon').textContent = '👨‍🍳';
      btn.querySelector('.login-btn-text').textContent = this.getUsername();
    } else {
      btn.classList.remove('logged-in');
      btn.querySelector('.login-btn-icon').textContent = '👤';
      btn.querySelector('.login-btn-text').textContent = '登录';
    }
  }
};
